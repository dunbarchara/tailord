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

from app.models.database import ExperienceClaim, ExperienceGroup, ExperienceSource

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# ExperienceGroup helpers
# ---------------------------------------------------------------------------


def _get_or_create_group(
    *,
    user_id: uuid.UUID,
    group_type: str,
    name: str,
    source_type: str,
    source_ref: str | None,
    db: Session,
) -> ExperienceGroup:
    """Return an existing ExperienceGroup or create one.

    Looks up by (user_id, source_type, name). Returns the first match when
    multiple rows share the same name (edge case — same role at same company
    twice). Caller must commit.
    """
    existing = (
        db.query(ExperienceGroup)
        .filter(
            ExperienceGroup.user_id == user_id,
            ExperienceGroup.source_type == source_type,
            ExperienceGroup.name == name,
        )
        .first()
    )
    if existing:
        return existing

    group = ExperienceGroup(
        user_id=user_id,
        group_type=group_type,
        name=name,
        source_type=source_type,
        source_ref=source_ref,
    )
    db.add(group)
    db.flush()  # populate group.id without a full commit
    return group


def _store_suggestion(
    repo_group: ExperienceGroup,
    role_groups: list[ExperienceGroup],
) -> None:
    """Run heuristic parent suggestion and write result into repo_group.type_meta.

    Does NOT commit — caller is responsible. No-ops if no match is found.
    """
    from app.services.group_linker import suggest_repo_parent

    result = suggest_repo_parent(repo_group, role_groups)
    if result is None:
        return

    parent, confidence = result
    meta = dict(repo_group.type_meta or {})
    meta["suggested_parent_id"] = str(parent.id)
    meta["suggestion_confidence"] = confidence
    repo_group.type_meta = meta


def delete_github_groups(
    db: Session,
    user_id: uuid.UUID,
    repo_name: str | None = None,
) -> int:
    """Delete ExperienceGroup rows for GitHub repos.

    repo_name=None → delete ALL github groups for this user.
    repo_name='foo' → delete only that repo's group.
    Does NOT commit — caller is responsible.
    """
    q = db.query(ExperienceGroup).filter(
        ExperienceGroup.user_id == user_id,
        ExperienceGroup.source_type == "github",
    )
    if repo_name is not None:
        q = q.filter(ExperienceGroup.name == repo_name)
    deleted = q.delete(synchronize_session=False)
    return deleted


def delete_resume_groups(db: Session, user_id: uuid.UUID) -> int:
    """Delete all resume ExperienceGroup rows for the user. Does NOT commit."""
    deleted = (
        db.query(ExperienceGroup)
        .filter(
            ExperienceGroup.user_id == user_id,
            ExperienceGroup.source_type == "resume",
        )
        .delete(synchronize_session=False)
    )
    return deleted


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


_CLAIM_TYPE_TO_GROUP_TYPE = {
    "work_experience": "role",
    "project": "project",
    "education": "education",
}


def chunk_resume(db: Session, resume_source: ExperienceSource) -> int:
    """Delete existing resume chunks and replace with freshly derived ones.

    Reads from resume_source.source_data['extracted']. No-ops if that key is absent.
    Also creates/reuses ExperienceGroup rows and sets group_id on each claim.
    After creating role groups, updates any existing repository groups with
    heuristic parent suggestions.
    Does NOT commit — caller is responsible.
    Returns number of chunks created.
    """
    profile = (resume_source.source_data or {}).get("extracted") or {}
    if not profile:
        logger.debug("chunk_resume_skipped_no_profile")
        return 0

    _delete_chunks(db, resume_source.user_id, "resume")

    raw = _resume_chunks(profile)

    # Build groups for distinct (group_type, group_key) pairs
    group_cache: dict[tuple[str, str], ExperienceGroup] = {}

    def _get_group(chunk_data: dict) -> ExperienceGroup | None:
        group_key = chunk_data.get("group_key")
        claim_type = chunk_data["claim_type"]
        group_type = _CLAIM_TYPE_TO_GROUP_TYPE.get(claim_type)
        if not group_key or not group_type:
            return None
        cache_key = (group_type, group_key)
        if cache_key not in group_cache:
            group_cache[cache_key] = _get_or_create_group(
                user_id=resume_source.user_id,
                group_type=group_type,
                name=group_key,
                source_type="resume",
                source_ref=None,
                db=db,
            )
        return group_cache[cache_key]

    now = datetime.now(timezone.utc)
    for position, chunk_data in enumerate(raw):
        group = _get_group(chunk_data)
        db.add(
            ExperienceClaim(
                user_id=resume_source.user_id,
                source_type="resume",
                source_ref=None,
                position=position,
                group_id=group.id if group else None,
                created_at=now,
                updated_at=now,
                **chunk_data,
            )
        )

    # Backfill dates, location, and job title onto role groups; degree/year/location onto
    # education groups.  _get_or_create_group only sets name/source fields — the authoritative
    # metadata lives in the original profile and must be written onto the group rows so that
    # resume_selector can read them without re-parsing source_data.
    for edu in profile.get("education") or []:
        degree = (edu.get("degree") or "").strip()
        institution = (edu.get("institution") or "").strip()
        year = (edu.get("year") or "").strip() or None
        location = (edu.get("location") or "").strip() or None
        edu_key_parts = [p for p in [degree, institution] if p]
        gkey = " | ".join(edu_key_parts) or None
        if not gkey:
            continue
        group = group_cache.get(("education", gkey))
        if group is None:
            continue
        if year:
            group.end_date = year
        if location:
            group.location = location
        if degree:
            meta = dict(group.type_meta or {})
            meta["degree"] = degree
            group.type_meta = meta

    for job in profile.get("work_experience") or []:
        gkey = _job_group_key(job)
        if not gkey:
            continue
        group = group_cache.get(("role", gkey))
        if group is None:
            continue
        duration = (job.get("duration") or "").strip() or None
        location = (job.get("location") or "").strip() or None
        title = (job.get("title") or "").strip() or None
        if duration and "\u2013" in duration:
            parts = duration.split("\u2013", 1)
            group.start_date = parts[0].strip() or None
            group.end_date = parts[1].strip() or None
        elif duration and "-" in duration:
            parts = duration.split("-", 1)
            group.start_date = parts[0].strip() or None
            group.end_date = parts[1].strip() or None
        elif duration:
            group.start_date = duration
        if location:
            group.location = location
        if title:
            meta = dict(group.type_meta or {})
            meta["title"] = title
            group.type_meta = meta

    # After creating role groups: refresh suggestions on any existing repo groups
    role_groups = [g for g in group_cache.values() if g.group_type == "role"]
    if role_groups:
        repo_groups = (
            db.query(ExperienceGroup)
            .filter(
                ExperienceGroup.user_id == resume_source.user_id,
                ExperienceGroup.source_type == "github",
            )
            .all()
        )
        for repo_group in repo_groups:
            _store_suggestion(repo_group, role_groups)

    logger.debug("chunk_resume_complete", chunk_count=len(raw))
    return len(raw)


def chunk_github_repo(db: Session, github_source: ExperienceSource, repo_name: str) -> int:
    """Delete existing chunks for a single GitHub repo and replace with freshly derived ones.

    Reads from github_source.source_data with enriched details merged in.
    Also creates/reuses an ExperienceGroup for the repo and stores a parent
    suggestion in type_meta if a matching role group is found.
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

    # Get or create a repository group (before deleting claims so the group survives rechunks)
    repo_group = _get_or_create_group(
        user_id=github_source.user_id,
        group_type="repository",
        name=repo_name,
        source_type="github",
        source_ref=repo_name,
        db=db,
    )

    # Backfill dates onto the repo group from the repo metadata
    date_range = _format_github_date_range(
        enriched_repo.get("created_at"),
        enriched_repo.get("last_pushed_at"),
    )
    if date_range and "\u2013" in date_range:
        parts = date_range.split("\u2013", 1)
        repo_group.start_date = parts[0].strip() or None
        repo_group.end_date = parts[1].strip() or None
    elif date_range:
        repo_group.start_date = date_range

    # Update parent suggestion if not already manually set
    if not repo_group.parent_group_id:
        role_groups = (
            db.query(ExperienceGroup)
            .filter(
                ExperienceGroup.user_id == github_source.user_id,
                ExperienceGroup.source_type == "resume",
                ExperienceGroup.group_type == "role",
            )
            .all()
        )
        _store_suggestion(repo_group, role_groups)

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
                group_id=repo_group.id,
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
