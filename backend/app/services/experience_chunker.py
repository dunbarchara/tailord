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

import re
import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy.orm import Session

from app.models.database import ExperienceClaim, ExperienceGroup, ExperienceSource
from app.services.profile_formatter import parse_duration_date

logger = structlog.get_logger(__name__)

_DURATION_SPLIT = re.compile(r"\s*[-–—]\s*|\s+to\s+")
_MULTI_SPACE = re.compile(r" {2,}")


def normalize_claim_text(text: str) -> str:
    """Normalize claim content for storage: collapse whitespace, strip newlines/tabs.

    Newlines and tabs indicate multi-statement content or formatting noise — neither
    belongs in an atomic ExperienceClaim. Collapse them to single spaces.
    """
    normalized = re.sub(r"[\n\r\t]+", " ", text)
    normalized = _MULTI_SPACE.sub(" ", normalized)
    return normalized.strip()


def _parse_date_to_iso(token: str | None) -> str | None:
    """Normalize a human-readable date token (e.g. 'Jan 2020', '2020', '01/2020') to YYYY-MM.

    Returns None for ongoing markers ('Present', 'Current', etc.) and unparseable inputs.
    """
    if not token:
        return None
    t = token.strip().lower()
    if t in ("present", "current", "now", "today"):
        return None  # ongoing — caller should store end_date as NULL
    d = parse_duration_date(token)
    if d is None:
        return None
    return f"{d.year:04d}-{d.month:02d}"


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
            bullet = normalize_claim_text(bullet)
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
        skill = normalize_claim_text(skill)
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
        desc = normalize_claim_text(project.get("description") or "")
        name = normalize_claim_text(project.get("name") or "") or None
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
        degree = normalize_claim_text(edu.get("degree") or "")
        institution = normalize_claim_text(edu.get("institution") or "")
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
        cert = normalize_claim_text(cert)
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
        item = normalize_claim_text(item)
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
        claim = normalize_claim_text(claim)
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


def chunk_resume(db: Session, resume_source: ExperienceSource, *, destructive: bool = False) -> int:
    """Create ExperienceGroup rows and ExperienceClaim rows from resume source data.

    Reads from resume_source.source_data['extracted']. No-ops if that key is absent.
    Also creates/reuses ExperienceGroup rows and sets group_id on each claim.
    After creating role groups, updates any existing repository groups with
    heuristic parent suggestions.
    Does NOT commit — caller is responsible.
    Returns number of chunks created.

    destructive=False (default): additive — existing resume claims are preserved alongside
        the new ones. Use for fresh uploads where no prior source row existed, or when the
        user explicitly chose to keep their existing claims.
    destructive=True: replaces existing resume claims before inserting new ones.
        Use only when the user has explicitly confirmed they want old claims removed.
    """
    profile = (resume_source.source_data or {}).get("extracted") or {}
    if not profile:
        logger.debug("chunk_resume_skipped_no_profile")
        return 0

    if destructive:
        logger.info("chunk_resume_destructive_delete", user_id=str(resume_source.user_id))
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
        # Prefer LLM-normalised dates; fall back to deterministic parse of year string.
        # completion_date is the new neutral field; graduation_date kept as fallback for
        # profiles extracted before the schema change.
        enrollment_date = edu.get("enrollment_date") or None
        completion_date = edu.get("completion_date") or edu.get("graduation_date") or None
        ed_status = edu.get("status") or None
        if enrollment_date:
            group.start_date = enrollment_date
        if completion_date:
            group.end_date = completion_date
        elif year:
            group.end_date = _parse_date_to_iso(year) or year
        if location:
            group.location = location
        meta = dict(group.type_meta or {})
        if degree:
            meta["degree"] = degree
        if institution:
            meta["institution"] = institution
        if ed_status:
            meta["status"] = ed_status
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
        # Prefer LLM-normalised ISO dates (new extractions); fall back to parsing free-text duration
        if job.get("start_date") or job.get("end_date") is not None:
            group.start_date = job.get("start_date") or None
            group.end_date = job.get("end_date")  # None = ongoing
        elif duration:
            parts = _DURATION_SPLIT.split(duration, maxsplit=1)
            if len(parts) == 2:
                group.start_date = _parse_date_to_iso(parts[0])
                group.end_date = _parse_date_to_iso(parts[1])  # None = ongoing (Present)
            else:
                group.start_date = _parse_date_to_iso(duration)
        if location:
            group.location = location
        if title:
            meta = dict(group.type_meta or {})
            meta["title"] = title
            group.type_meta = meta

    for project in profile.get("projects") or []:
        pname = (project.get("name") or "").strip() or None
        if not pname:
            continue
        group = group_cache.get(("project", pname))
        if group is None:
            continue
        if project.get("start_date"):
            group.start_date = project["start_date"]
        if project.get("end_date") is not None:
            group.end_date = project.get("end_date")  # None = ongoing

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


def chunk_github_repo(
    db: Session,
    github_source: ExperienceSource,
    repo_name: str,
    *,
    destructive: bool = False,
) -> int:
    """Create an ExperienceGroup and ExperienceClaim rows for a single GitHub repo.

    Reads from github_source.source_data with enriched details merged in.
    Also creates/reuses an ExperienceGroup for the repo and stores a parent
    suggestion in type_meta if a matching role group is found.
    Does NOT commit — caller is responsible.
    Returns number of chunks created.

    destructive=False (default): additive — existing claims for this repo are preserved.
        Use for fresh connects and additions so kept claims are not silently removed.
    destructive=True: deletes existing claims for this repo before inserting new ones.
        Use only for explicit user-initiated rescans of a specific repo.
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

    # Backfill ISO dates onto the repo group directly from raw API timestamps
    repo_created_at = enriched_repo.get("created_at")
    repo_pushed_at = enriched_repo.get("last_pushed_at")
    if repo_created_at:
        dt = datetime.fromisoformat(repo_created_at.replace("Z", "+00:00"))
        repo_group.start_date = f"{dt.year:04d}-{dt.month:02d}"
    if repo_pushed_at:
        dt = datetime.fromisoformat(repo_pushed_at.replace("Z", "+00:00"))
        is_recent = datetime.now(timezone.utc) - dt <= timedelta(days=180)
        repo_group.end_date = None if is_recent else f"{dt.year:04d}-{dt.month:02d}"

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

    if destructive:
        logger.info(
            "chunk_github_repo_destructive_delete",
            user_id=str(github_source.user_id),
            repo_name=repo_name,
        )
        _delete_chunks(db, github_source.user_id, "github", source_ref=repo_name)

    from app.services.claim_dedup import is_duplicate_by_source_ref, is_duplicate_claim

    # Layer 1: pre-loop guard — if any claim already exists for this repo, skip entirely.
    # Must run before the loop: autoflush would make the first inserted claim visible to
    # subsequent iterations, causing all but the first chunk to be dropped.
    if is_duplicate_by_source_ref(github_source.user_id, "github", repo_name, db):
        logger.debug(
            "chunk_github_repo_dedup_source_ref",
            user_id=str(github_source.user_id),
            repo_name=repo_name,
        )
        return 0

    raw = _github_repo_chunks(enriched_repo)
    now = datetime.now(timezone.utc)
    inserted = 0
    for position, chunk_data in enumerate(raw):
        content = chunk_data.get("content", "")

        # Layer 2: semantic dedup — skip if content is near-identical to an existing active claim.
        if content:
            try:
                if is_duplicate_claim(github_source.user_id, content, db):
                    logger.debug(
                        "chunk_github_repo_dedup_semantic",
                        user_id=str(github_source.user_id),
                        repo_name=repo_name,
                    )
                    continue
            except Exception:
                logger.warning(
                    "chunk_github_repo_dedup_embed_failed",
                    user_id=str(github_source.user_id),
                    repo_name=repo_name,
                    exc_info=True,
                )
                # Embedding failure is non-fatal — insert the claim anyway

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
        inserted += 1

    logger.debug("chunk_github_repo_complete", chunk_count=inserted, repo_name=repo_name)
    return inserted


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
