"""
experience_chunker.py — deterministic chunking of extracted_profile into ExperienceChunk rows.

No LLM involved. Each public function takes an already-loaded Experience (or its extracted_profile
dict) and a SQLAlchemy session, deletes existing chunks for the specified source, then inserts new
ones. The caller is responsible for committing.

Chunking strategy
-----------------
resume      → walk extracted_profile["resume"]:
              summary          → 1 chunk (claim_type=other)
              work_experience  → 1 chunk per bullet (claim_type=work_experience, date_range=duration)
              skills.technical → 1 chunk per skill (claim_type=skill)
              skills.soft      → 1 chunk per skill (claim_type=skill)
              projects         → 1 chunk per project (claim_type=project, technologies=project.technologies)
              education        → 1 chunk per entry (claim_type=education)
              certifications   → 1 chunk per cert (claim_type=other)

github      → walk enriched repo in extracted_profile["github"]["repos"]:
              readme_summary   → 1 chunk (claim_type=project, source_ref=repo_name)
              detected_stack[] → 1 chunk per item (claim_type=skill, source_ref=repo_name)
              (call once per repo, passing source_ref=repo_name)

user_input  → entire user_input_text as one chunk (claim_type=other)
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.database import Experience, ExperienceChunk

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers — build raw chunk dicts before DB insert
# ---------------------------------------------------------------------------


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

    summary = (profile.get("summary") or "").strip()
    if summary:
        chunks.append(
            {
                "claim_type": "other",
                "content": summary,
                "group_key": None,
                "date_range": None,
                "technologies": None,
            }
        )

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
                        "technologies": None,
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
                    "technologies": None,
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
                    "technologies": techs if techs else None,
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
                    "technologies": None,
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
                    "technologies": None,
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

    summary = (repo.get("readme_summary") or "").strip()
    if summary:
        chunks.append(
            {
                "claim_type": "project",
                "content": summary,
                "group_key": repo_name,
                "date_range": None,
                "technologies": None,
            }
        )

    for item in repo.get("detected_stack") or []:
        item = item.strip()
        if item:
            chunks.append(
                {
                    "claim_type": "skill",
                    "content": item,
                    "group_key": repo_name,
                    "date_range": None,
                    "technologies": None,
                }
            )

    return chunks


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _delete_chunks(
    db: Session,
    experience_id: uuid.UUID,
    source_type: str,
    source_ref: str | None = None,
) -> int:
    """Delete existing chunks matching (experience_id, source_type[, source_ref]).

    source_ref=None deletes ALL chunks for that source_type when source_ref is None
    on the row (i.e. resume / user_input). For github, pass the specific repo name
    to limit deletion to that repo; pass None to delete all github chunks.
    """
    q = db.query(ExperienceChunk).filter(
        ExperienceChunk.experience_id == experience_id,
        ExperienceChunk.source_type == source_type,
    )
    if source_ref is not None:
        q = q.filter(ExperienceChunk.source_ref == source_ref)
    deleted = q.delete(synchronize_session=False)
    return deleted


def chunk_resume(db: Session, experience: Experience) -> int:
    """Delete existing resume chunks and replace with freshly derived ones.

    Reads from experience.extracted_profile['resume']. No-ops if that key is absent.
    Does NOT commit — caller is responsible.
    Returns number of chunks created.
    """
    profile = (experience.extracted_profile or {}).get("resume") or {}
    if not profile:
        logger.debug("chunk_resume: no resume profile for experience=%s — skipping", experience.id)
        return 0

    _delete_chunks(db, experience.id, "resume")

    raw = _resume_chunks(profile)
    now = datetime.now(timezone.utc)
    for position, chunk_data in enumerate(raw):
        db.add(
            ExperienceChunk(
                experience_id=experience.id,
                source_type="resume",
                source_ref=None,
                position=position,
                created_at=now,
                updated_at=now,
                **chunk_data,
            )
        )

    logger.debug("chunk_resume: created %d chunks for experience=%s", len(raw), experience.id)
    return len(raw)


def chunk_github_repo(db: Session, experience: Experience, repo_name: str) -> int:
    """Delete existing chunks for a single GitHub repo and replace with freshly derived ones.

    Reads from experience.extracted_profile['github']['repos'] for the named repo.
    Does NOT commit — caller is responsible.
    Returns number of chunks created.
    """
    github_profile = (experience.extracted_profile or {}).get("github") or {}
    repos = github_profile.get("repos") or []
    repo = next((r for r in repos if r.get("name") == repo_name), None)
    if not repo:
        logger.debug(
            "chunk_github_repo: repo=%s not found in profile for experience=%s",
            repo_name,
            experience.id,
        )
        return 0

    _delete_chunks(db, experience.id, "github", source_ref=repo_name)

    raw = _github_repo_chunks(repo)
    now = datetime.now(timezone.utc)
    for position, chunk_data in enumerate(raw):
        db.add(
            ExperienceChunk(
                experience_id=experience.id,
                source_type="github",
                source_ref=repo_name,
                position=position,
                created_at=now,
                updated_at=now,
                **chunk_data,
            )
        )

    logger.debug(
        "chunk_github_repo: created %d chunks for experience=%s repo=%s",
        len(raw),
        experience.id,
        repo_name,
    )
    return len(raw)


def delete_github_chunks(
    db: Session, experience_id: uuid.UUID, repo_name: str | None = None
) -> int:
    """Delete GitHub chunks for the given experience.

    repo_name=None → delete ALL github chunks (used when disconnecting all GitHub).
    repo_name='foo' → delete only that repo's chunks.
    Does NOT commit — caller is responsible.
    """
    return _delete_chunks(db, experience_id, "github", source_ref=repo_name)


def delete_resume_chunks(db: Session, experience_id: uuid.UUID) -> int:
    """Delete all resume chunks for the given experience. Does NOT commit."""
    return _delete_chunks(db, experience_id, "resume")


def delete_user_input_chunks(db: Session, experience_id: uuid.UUID) -> int:
    """Delete all user_input chunks for the given experience. Does NOT commit."""
    return _delete_chunks(db, experience_id, "user_input")
