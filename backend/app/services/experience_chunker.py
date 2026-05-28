"""
experience_chunker.py — deterministic chunking of ExperienceSource data into ExperienceClaim rows.

No LLM involved. Each public function takes an ExperienceSource row and a SQLAlchemy session,
deletes existing chunks for the specified source, then inserts new ones. The caller is responsible
for committing.

Chunking strategy
-----------------
resume      → walk ExperienceSource.source_data["extracted"]:
              summary          → skipped (always present in _format_sourced_profile context; embedding would crowd top-K)
              work_experience  → 1 chunk per bullet (claim_type=work_experience, date_range=duration)
              skills.technical → 1 chunk per skill (claim_type=skill)
              skills.soft      → 1 chunk per skill (claim_type=skill)
              projects         → 1 chunk per project (claim_type=project, keywords=project.technologies)
              education        → 1 chunk per entry (claim_type=education)
              certifications   → 1 chunk per cert (claim_type=other)

github      → walk repos (with enriched details merged) from ExperienceSource.source_data:
              readme_summary   → skipped (always in _fmt_github_prose context; embedding would crowd top-K)
              detected_stack[] → 1 chunk per item (claim_type=skill, source_ref=repo_name)
              (call once per repo, passing source_ref=repo_name)
"""

import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy.orm import Session

from app.models.database import ExperienceClaim, ExperienceSource

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers — build raw chunk dicts before DB insert
# ---------------------------------------------------------------------------


def _format_github_date_range(created_at: str | None, last_pushed_at: str | None) -> str | None:
    """Format 'Jan 2024 – Present' or 'Jan 2024 – Mar 2025' from ISO8601 repo dates.
    Uses created_at (repo creation) as start, pushed_at as end. Treats pushed within
    the last 6 months as 'Present'.
    """

    def _fmt(iso: str) -> str:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%b %Y")

    start = _fmt(created_at) if created_at else None

    end_label = None
    if last_pushed_at:
        last_dt = datetime.fromisoformat(last_pushed_at.replace("Z", "+00:00"))
        if datetime.now(timezone.utc) - last_dt <= timedelta(days=180):
            end_label = "Present"
        else:
            end_label = _fmt(last_pushed_at)

    if start and end_label:
        return f"{start} – {end_label}"
    return start or end_label


def _job_group_key(job: dict) -> str | None:
    """Stable group key for a work_experience entry — 'Company | Title'."""
    company = (job.get("company") or "").strip()
    title = (job.get("title") or "").strip()
    parts = [p for p in [company, title] if p]
    return " | ".join(parts) or None


def _resume_chunks(profile: dict) -> list[dict]:
    """Return a flat list of chunk dicts from extracted_profile['resume'].

    Each dict includes a 'group_key' field for rendering hierarchy:
      work_experience → "Company | Title"
      project         → project name
      education       → "Degree | Institution"
      skill / other   → None
    """
    chunks: list[dict] = []

    # summary intentionally skipped — it is always present in _format_sourced_profile baseline
    # context and would crowd out specific bullets in cosine similarity top-K retrieval.

    for job in profile.get("work_experience") or []:
        date_range = (job.get("duration") or "").strip() or None
        group_key = _job_group_key(job)
        for bullet in job.get("bullets") or []:
            bullet = bullet.strip()
            if bullet:
                chunks.append(
                    {
                        "claim_type": "work_experience",
                        "content": bullet,
                        "group_key": group_key,
                        "date_range": date_range,
                        "keywords": None,
                    }
                )

    skills = profile.get("skills") or {}
    for skill in (skills.get("technical") or []) + (skills.get("soft") or []):
        skill = skill.strip()
        if skill:
            chunks.append(
                {
                    "claim_type": "skill",
                    "content": skill,
                    "group_key": None,
                    "date_range": None,
                    "keywords": None,
                }
            )

    for project in profile.get("projects") or []:
        desc = (project.get("description") or "").strip()
        name = (project.get("name") or "").strip() or None
        if desc:
            techs = project.get("technologies") or None
            chunks.append(
                {
                    "claim_type": "project",
                    "content": desc,
                    "group_key": name,
                    "date_range": None,
                    "keywords": techs if techs else None,
                }
            )

    for edu in profile.get("education") or []:
        degree = (edu.get("degree") or "").strip()
        institution = (edu.get("institution") or "").strip()
        year = (edu.get("year") or "").strip()
        parts = [p for p in [degree, institution, year] if p]
        edu_key_parts = [p for p in [degree, institution] if p]
        if parts:
            chunks.append(
                {
                    "claim_type": "education",
                    "content": ", ".join(parts),
                    "group_key": " | ".join(edu_key_parts) or None,
                    "date_range": year or None,
                    "keywords": None,
                }
            )

    for cert in profile.get("certifications") or []:
        cert = cert.strip()
        if cert:
            chunks.append(
                {
                    "claim_type": "other",
                    "content": cert,
                    "group_key": None,
                    "date_range": None,
                    "keywords": None,
                }
            )

    return chunks


def _github_repo_chunks(repo: dict) -> list[dict]:
    """Return chunk dicts for a single enriched GitHub repo dict.

    group_key = repo name for all chunks so the renderer can group
    the summary + stack items under the same repo heading.
    """
    chunks: list[dict] = []
    repo_name = (repo.get("name") or "").strip() or None
    date_range = _format_github_date_range(
        repo.get("created_at"),
        repo.get("last_pushed_at"),
    )

    # readme_summary intentionally skipped — always present in _fmt_github_prose baseline
    # context and would crowd out experience_claims in cosine similarity top-K retrieval.

    for item in repo.get("detected_stack") or []:
        item = item.strip()
        if item:
            chunks.append(
                {
                    "claim_type": "skill",
                    "content": item,
                    "group_key": repo_name,
                    "date_range": date_range,
                    "keywords": None,
                }
            )

    for claim in repo.get("experience_claims") or []:
        claim = claim.strip()
        if claim:
            chunks.append(
                {
                    "claim_type": "work_experience",
                    "content": claim,
                    "group_key": repo_name,
                    "date_range": date_range,
                    "keywords": None,
                }
            )

    return chunks


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _delete_chunks(
    db: Session,
    user_id: uuid.UUID,
    source_type: str,
    source_ref: str | None = None,
) -> int:
    """Delete existing chunks matching (user_id, source_type[, source_ref]).

    source_ref=None deletes ALL chunks for that source_type when source_ref is None
    on the row (i.e. resume / user_input). For github, pass the specific repo name
    to limit deletion to that repo; pass None to delete all github chunks.
    """
    q = db.query(ExperienceClaim).filter(
        ExperienceClaim.user_id == user_id,
        ExperienceClaim.source_type == source_type,
    )
    if source_ref is not None:
        q = q.filter(ExperienceClaim.source_ref == source_ref)
    deleted = q.delete(synchronize_session=False)
    return deleted


def chunk_resume(db: Session, resume_source: ExperienceSource) -> int:
    """Delete existing resume chunks and replace with freshly derived ones.

    Reads from resume_source.source_data['extracted']. No-ops if that key is absent.
    Does NOT commit — caller is responsible.
    Returns number of chunks created.
    """
    profile = (resume_source.source_data or {}).get("extracted") or {}
    if not profile:
        logger.debug("chunk_resume_skipped_no_profile")
        return 0

    _delete_chunks(db, resume_source.user_id, "resume")

    raw = _resume_chunks(profile)
    now = datetime.now(timezone.utc)
    for position, chunk_data in enumerate(raw):
        db.add(
            ExperienceClaim(
                user_id=resume_source.user_id,
                source_type="resume",
                source_ref=None,
                position=position,
                created_at=now,
                updated_at=now,
                **chunk_data,
            )
        )

    logger.debug("chunk_resume_complete", chunk_count=len(raw))
    return len(raw)


def chunk_github_repo(db: Session, github_source: ExperienceSource, repo_name: str) -> int:
    """Delete existing chunks for a single GitHub repo and replace with freshly derived ones.

    Reads from github_source.source_data with enriched details merged in.
    Does NOT commit — caller is responsible.
    Returns number of chunks created.
    """
    source_data = github_source.source_data or {}
    repos = source_data.get("repos") or []
    repo_details = source_data.get("repo_details") or {}
    repo = next((r for r in repos if r.get("name") == repo_name), None)
    if not repo:
        logger.debug("chunk_github_repo_not_found", repo_name=repo_name)
        return 0

    # Merge enriched details (detected_stack, experience_claims, etc.) into the repo dict
    detail = repo_details.get(repo_name) or {}
    enriched_repo = {**repo, **detail}

    _delete_chunks(db, github_source.user_id, "github", source_ref=repo_name)

    raw = _github_repo_chunks(enriched_repo)
    now = datetime.now(timezone.utc)
    for position, chunk_data in enumerate(raw):
        db.add(
            ExperienceClaim(
                user_id=github_source.user_id,
                source_type="github",
                source_ref=repo_name,
                position=position,
                created_at=now,
                updated_at=now,
                **chunk_data,
            )
        )

    logger.debug("chunk_github_repo_complete", chunk_count=len(raw), repo_name=repo_name)
    return len(raw)


def delete_github_chunks(db: Session, user_id: uuid.UUID, repo_name: str | None = None) -> int:
    """Delete GitHub chunks for the given user.

    repo_name=None → delete ALL github chunks (used when disconnecting all GitHub).
    repo_name='foo' → delete only that repo's chunks.
    Does NOT commit — caller is responsible.
    """
    return _delete_chunks(db, user_id, "github", source_ref=repo_name)


def delete_resume_chunks(db: Session, user_id: uuid.UUID) -> int:
    """Delete all resume chunks for the given user. Does NOT commit."""
    return _delete_chunks(db, user_id, "resume")


def delete_user_input_chunks(db: Session, user_id: uuid.UUID) -> int:
    """Delete all user_input chunks for the given user. Does NOT commit."""
    return _delete_chunks(db, user_id, "user_input")
