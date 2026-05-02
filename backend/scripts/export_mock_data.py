"""
Export real DB data for a user + tailoring set to frontend/src/mock/data.json.

Usage (from backend/):
    uv run python scripts/export_mock_data.py \\
        --user-id <uuid> \\
        --tailoring-id <uuid> [--tailoring-id <uuid> ...]

The script queries the local PostgreSQL database and writes the mock data file
used by the demo dashboard at /demo/dashboard.
"""

import argparse
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

# Make `app` importable when running from scripts/ or backend/
sys.path.insert(0, str(Path(__file__).parent.parent))

OUTPUT_PATH = Path(__file__).parent.parent.parent / "frontend" / "src" / "mock" / "data.json"


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _clean(obj: object) -> object:
    """Recursively convert SQLAlchemy row dicts to JSON-safe values."""
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items() if k != "_sa_instance_state"}
    if isinstance(obj, list):
        return [_clean(i) for i in obj]
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


def row_to_dict(row: object) -> dict:
    d = {c.key: getattr(row, c.key) for c in row.__table__.columns}  # type: ignore[attr-defined]
    return _clean(d)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# ExperienceChunks builder
# ---------------------------------------------------------------------------


def build_experience_chunks(chunks: list) -> dict:
    """
    Group ExperienceChunk rows into the ExperienceChunksResponse shape the
    frontend expects.
    """
    resume_we: dict[str, dict] = {}  # group_key → {group_key, date_range, chunks[]}
    resume_skills: list = []
    resume_projects: dict[str, dict] = {}
    resume_education: list = []
    resume_other: list = []

    github_repos: dict[str, dict] = {}  # source_ref → {group_key, chunks[]}
    user_input: list = []
    gap_response: list = []

    for chunk in chunks:
        d = row_to_dict(chunk)
        # Drop embedding fields — not needed in mock data
        d.pop("embedding", None)
        d.pop("embedding_model", None)
        d.pop("experience_id", None)

        st = chunk.source_type
        ct = chunk.claim_type

        if st == "resume":
            if ct == "work_experience":
                gk = chunk.group_key or "Unknown"
                if gk not in resume_we:
                    resume_we[gk] = {
                        "group_key": gk,
                        "date_range": chunk.date_range,
                        "chunks": [],
                    }
                resume_we[gk]["chunks"].append(d)
            elif ct == "skill":
                resume_skills.append(d)
            elif ct == "project":
                gk = chunk.group_key or "Project"
                if gk not in resume_projects:
                    resume_projects[gk] = {"group_key": gk, "chunks": []}
                resume_projects[gk]["chunks"].append(d)
            elif ct == "education":
                resume_education.append(d)
            else:
                resume_other.append(d)

        elif st == "github":
            ref = chunk.source_ref or chunk.group_key or "unknown"
            if ref not in github_repos:
                github_repos[ref] = {"group_key": ref, "chunks": []}
            github_repos[ref]["chunks"].append(d)

        elif st == "user_input":
            user_input.append(d)

        elif st == "gap_response":
            gap_response.append(d)

    resume = {
        "work_experience": sorted(
            resume_we.values(), key=lambda g: g["chunks"][0].get("position", 0)
        ),
        "skills": sorted(resume_skills, key=lambda c: c.get("position", 0)),
        "projects": sorted(
            resume_projects.values(), key=lambda g: g["chunks"][0].get("position", 0)
        ),
        "education": sorted(resume_education, key=lambda c: c.get("position", 0)),
        "other": sorted(resume_other, key=lambda c: c.get("position", 0)),
    }

    has_resume = any(
        [
            resume["work_experience"],
            resume["skills"],
            resume["projects"],
            resume["education"],
            resume["other"],
        ]
    )

    return {
        "resume": resume if has_resume else None,
        "github": {"repos": list(github_repos.values())} if github_repos else None,
        "user_input": user_input if user_input else None,
        "gap_response": gap_response if gap_response else None,
    }


# ---------------------------------------------------------------------------
# JobChunks builder
# ---------------------------------------------------------------------------


def build_chunks_response(job_chunks: list, enrichment_status: str) -> dict:
    chunks = []
    for jc in sorted(job_chunks, key=lambda c: c.position):
        d = row_to_dict(jc)
        d.pop("job_id", None)
        d.pop("enriched_at", None)
        d.pop("embedding", None)
        d.pop("embedding_model", None)
        # Compute display_ready: bullet/paragraph with a section, not a noise chunk
        d["display_ready"] = (
            jc.chunk_type in ("bullet", "paragraph") and jc.section is not None and jc.should_render
        )
        # Add source_label
        source_map = {"resume": "Resume", "github": "GitHub", "user_input": "Manual"}
        d["source_label"] = (
            source_map.get(jc.experience_source or "", None) if jc.experience_source else None
        )
        chunks.append(d)
    return {"enrichment_status": enrichment_status, "chunks": chunks}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export real DB data to frontend/src/mock/data.json"
    )
    parser.add_argument("--user-id", required=True, help="UUID of the user to export")
    parser.add_argument(
        "--tailoring-id",
        action="append",
        dest="tailoring_ids",
        required=True,
        metavar="UUID",
        help="UUID of a tailoring to include (repeat for multiple)",
    )
    args = parser.parse_args()

    from app.clients.database import SessionLocal
    from app.models.database import (
        Experience,
        ExperienceChunk,
        Job,
        JobChunk,
        Tailoring,
        User,
    )

    db = SessionLocal()
    try:
        # ── User ──────────────────────────────────────────────────────────────
        user = db.query(User).filter(User.id == args.user_id).first()
        if not user:
            print(f"[ERROR] User {args.user_id} not found.")
            sys.exit(1)

        user_dict = row_to_dict(user)
        # Strip sensitive/internal fields
        for field in (
            "google_sub",
            "notion_access_token",
            "notion_bot_id",
            "notion_workspace_id",
            "notion_parent_page_id",
            "is_admin",
            "status",
        ):
            user_dict.pop(field, None)

        display_name = user.preferred_first_name or (user.name or "").split()[0] or user.email

        # ── Experience ────────────────────────────────────────────────────────
        experience = db.query(Experience).filter(Experience.user_id == args.user_id).first()
        if not experience:
            print(f"[ERROR] No experience found for user {args.user_id}.")
            sys.exit(1)

        exp_dict = row_to_dict(experience)
        exp_dict.pop("user_id", None)
        exp_dict.pop("s3_key", None)

        # ── ExperienceChunks ──────────────────────────────────────────────────
        exp_chunks = (
            db.query(ExperienceChunk)
            .filter(ExperienceChunk.experience_id == experience.id)
            .order_by(ExperienceChunk.source_type, ExperienceChunk.position)
            .all()
        )
        experience_chunks = build_experience_chunks(exp_chunks)

        # ── Tailorings ────────────────────────────────────────────────────────
        tailorings_list = []
        tailoring_details = {}
        chunks_map = {}

        for tid in args.tailoring_ids:
            tailoring = db.query(Tailoring).filter(Tailoring.id == tid).first()
            if not tailoring:
                print(f"[WARN] Tailoring {tid} not found, skipping.")
                continue

            job = db.query(Job).filter(Job.id == tailoring.job_id).first()
            job_dict = row_to_dict(job) if job else {}

            # List item shape
            title = (
                job_dict.get("extracted_job", {}).get("title")
                if job_dict.get("extracted_job")
                else None
            )
            company = (
                job_dict.get("extracted_job", {}).get("company")
                if job_dict.get("extracted_job")
                else None
            )
            tailorings_list.append(
                {
                    "id": str(tailoring.id),
                    "title": title,
                    "company": company,
                    "job_url": job.job_url if job else None,
                    "generation_status": tailoring.generation_status,
                    "letter_public": tailoring.letter_public,
                    "posting_public": tailoring.posting_public,
                    "is_public": tailoring.is_public,
                    "public_slug": tailoring.public_slug,
                    "created_at": tailoring.created_at.isoformat(),
                }
            )

            # Detail shape
            detail = row_to_dict(tailoring)
            detail.pop("user_id", None)
            detail.pop("job_id", None)
            detail.pop("model", None)
            detail.pop("profile_snapshot", None)
            detail["title"] = title
            detail["company"] = company
            detail["job_url"] = job.job_url if job else None
            detail["author_username_slug"] = user.username_slug
            tailoring_details[str(tailoring.id)] = detail

            # JobChunks
            job_chunks = db.query(JobChunk).filter(JobChunk.job_id == tailoring.job_id).all()
            chunks_map[str(tailoring.id)] = build_chunks_response(
                job_chunks, tailoring.enrichment_status
            )

        # ── Assemble output ───────────────────────────────────────────────────
        output = {
            "displayName": display_name,
            "user": user_dict,
            "experience": exp_dict,
            "experienceChunks": experience_chunks,
            "tailorings": tailorings_list,
            "tailoringDetails": tailoring_details,
            "chunks": chunks_map,
        }

        OUTPUT_PATH.write_text(json.dumps(output, indent=2, default=str))
        print(f"[OK] Written to {OUTPUT_PATH}")
        print(f"     {len(tailorings_list)} tailoring(s) exported")
        print(f"     {len(exp_chunks)} experience chunks")

    finally:
        db.close()


if __name__ == "__main__":
    main()
