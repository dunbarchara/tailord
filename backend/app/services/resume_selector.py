import calendar as _cal
import re
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy.orm import Session

from app.models.database import (
    ExperienceClaim,
    ExperienceGroup,
    ExperienceSource,
    JobChunk,
    Tailoring,
)
from app.schemas.resume import EducationEntry, ResumeContactOverride, ResumeDraft, ResumeSection
from app.services.chunk_matcher import _retrieve_top_k_experience_chunks

logger = structlog.get_logger(__name__)

SECTION_WEIGHTS = {
    "must_have": 2.0,
    "nice_to_have": 1.0,
    "unclassified": 1.5,
}

MUST_HAVE_KEYWORDS = {
    "required",
    "requirements",
    "must have",
    "minimum qualifications",
    "basic qualifications",
    "you must",
    "we require",
}
NICE_TO_HAVE_KEYWORDS = {
    "preferred",
    "nice to have",
    "bonus",
    "ideal",
    "desired",
    "optionally",
    "a plus",
    "beneficial",
}

MAX_BULLETS_PER_ROLE = 5
MAX_ROLES = 4
MAX_SKILLS = 15


def _classify_section(section: str | None) -> float:
    if not section:
        return SECTION_WEIGHTS["unclassified"]
    s = section.lower()
    if any(k in s for k in MUST_HAVE_KEYWORDS):
        return SECTION_WEIGHTS["must_have"]
    if any(k in s for k in NICE_TO_HAVE_KEYWORDS):
        return SECTION_WEIGHTS["nice_to_have"]
    return SECTION_WEIGHTS["unclassified"]


def _is_yoe_only(content: str) -> bool:
    """True if claim is purely a years-of-experience assertion with no other substance."""
    cleaned = re.sub(r"\b\d+\+?\s+years?\b", "", content, flags=re.IGNORECASE).strip()
    return len(cleaned) < 20


_MONTH_ABBRS = {m: i for i, m in enumerate(_cal.month_abbr) if m}


def _parse_date_for_sort(date_str: str | None) -> tuple[int, int]:
    """Convert 'Mon YYYY' to sortable (year, month). None/Present → (9999, 12) = most recent."""
    if not date_str or date_str.strip().lower() in ("present", "current", "now"):
        return (9999, 12)
    parts = date_str.strip().split()
    try:
        if len(parts) == 2:
            return (int(parts[1]), _MONTH_ABBRS.get(parts[0], 0))
        if len(parts) == 1:
            return (int(parts[0]), 0)
    except (ValueError, IndexError):
        pass
    return (0, 0)


def _parse_group_name_from_key(group_key: str) -> str:
    """'ACME Corp | Software Engineer' → 'ACME Corp'. Falls back to the full key."""
    return group_key.split("|")[0].strip() if "|" in group_key else group_key


def _parse_job_title_from_key(group_key: str) -> str | None:
    """'ACME Corp | Software Engineer' → 'Software Engineer'. Returns None if no title part."""
    if "|" not in group_key:
        return None
    return group_key.split("|", 1)[1].strip() or None


def check_resume_prerequisites(user_id: uuid.UUID, db: Session) -> dict:
    """Returns {"can_generate": bool, "warnings": list[str]}"""
    active_claims = (
        db.query(ExperienceClaim)
        .filter(
            ExperienceClaim.user_id == user_id,
            ExperienceClaim.status == "active",
        )
        .count()
    )
    if active_claims == 0:
        return {"can_generate": False, "warnings": ["no_active_claims"]}

    warnings = []
    resume_source = (
        db.query(ExperienceSource)
        .filter(
            ExperienceSource.user_id == user_id,
            ExperienceSource.source_type == "resume",
            ExperienceSource.connection_status == "connected",
        )
        .first()
    )
    if not resume_source:
        warnings.append("no_resume_source")
    return {"can_generate": True, "warnings": warnings}


def _get_contact_info(user_id: uuid.UUID, db: Session) -> dict:
    """Extract linkedin/location from resume source_data.extracted + corrections."""
    source = (
        db.query(ExperienceSource)
        .filter(
            ExperienceSource.user_id == user_id,
            ExperienceSource.source_type == "resume",
        )
        .first()
    )
    if not source or not source.source_data:
        return {"linkedin": None, "location": None}
    extracted = source.source_data.get("extracted") or {}
    corrections = source.source_data.get("corrections") or {}
    return {
        "linkedin": extracted.get("linkedin"),
        "location": corrections.get("location") or extracted.get("location"),
    }


def generate_resume_selection(tailoring: Tailoring, user_id: uuid.UUID, db: Session) -> ResumeDraft:
    """Phase 1: mechanical claim selection. No LLM calls."""
    prereqs = check_resume_prerequisites(user_id, db)
    warnings = prereqs["warnings"]

    job_id = tailoring.job_id
    scored_chunks = (
        db.query(JobChunk)
        .filter(
            JobChunk.job_id == job_id,
            JobChunk.match_score >= 1,
            JobChunk.embedding.isnot(None),
        )
        .all()
    )
    logger.info(
        "resume_selector_start",
        tailoring_id=str(tailoring.id),
        user_id=str(user_id),
        scored_chunks_with_embedding=len(scored_chunks),
    )

    # Build claim_relevance_scores: {claim_id: float}
    claim_relevance: dict[str, float] = {}
    for chunk in scored_chunks:
        weight = _classify_section(chunk.section)
        top_claims = _retrieve_top_k_experience_chunks(
            job_chunk_embedding=list(chunk.embedding),
            user_id=user_id,
            db=db,
            k=8,
        )
        for claim in top_claims:
            cid = str(claim.id)
            claim_relevance[cid] = claim_relevance.get(cid, 0.0) + chunk.match_score * weight

    # Always include gap-response claims tied to this tailoring
    gap_claims = (
        db.query(ExperienceClaim)
        .filter(
            ExperienceClaim.user_id == user_id,
            ExperienceClaim.status == "active",
            ExperienceClaim.provenance_metadata["tailoring_id"].astext == str(tailoring.id),
        )
        .all()
    )
    for gc in gap_claims:
        cid = str(gc.id)
        if cid not in claim_relevance:
            claim_relevance[cid] = 1.0
    logger.debug(
        "resume_selector_relevance",
        claims_with_relevance=len(claim_relevance),
        gap_claims_pinned=len(gap_claims),
    )

    # Load all active claims and groups
    all_claims: dict[str, ExperienceClaim] = {
        str(c.id): c
        for c in db.query(ExperienceClaim)
        .filter(
            ExperienceClaim.user_id == user_id,
            ExperienceClaim.status == "active",
        )
        .all()
    }
    all_groups: dict[str, ExperienceGroup] = {
        str(g.id): g
        for g in db.query(ExperienceGroup)
        .filter(ExperienceGroup.user_id == user_id)
        .order_by(ExperienceGroup.position)
        .all()
    }
    logger.debug(
        "resume_selector_loaded",
        total_claims=len(all_claims),
        total_groups=len(all_groups),
    )

    # ── Location lookup: build "Company | Title" → location map from resume extracted profile ──
    location_lookup: dict[str, str] = {}
    resume_source = (
        db.query(ExperienceSource)
        .filter(
            ExperienceSource.user_id == user_id,
            ExperienceSource.source_type == "resume",
        )
        .first()
    )
    if resume_source and resume_source.source_data:
        extracted = resume_source.source_data.get("extracted") or {}
        for job in extracted.get("work_experience") or []:
            company = (job.get("company") or "").strip()
            title = (job.get("title") or "").strip()
            loc = (job.get("location") or "").strip() or None
            if loc:
                parts = [p for p in [company, title] if p]
                key = " | ".join(parts) or None
                if key:
                    location_lookup[key] = loc
        for edu in extracted.get("education") or []:
            degree = (edu.get("degree") or "").strip()
            institution = (edu.get("institution") or "").strip()
            loc = (edu.get("location") or "").strip() or None
            if loc:
                parts = [p for p in [degree, institution] if p]
                key = " | ".join(parts) or None
                if key:
                    location_lookup[key] = loc

    # ── Classify claims ────────────────────────────────────────────────────
    skill_claim_ids_raw: list[str] = []
    # Groups from ExperienceGroup FK: key = group UUID string
    role_groups: dict[str, dict] = {}
    # Groups synthesised from deprecated group_key: key = "ungrouped:<group_key>"
    ungrouped_work: dict[str, dict] = {}
    # Ungrouped education claims keyed by group_key
    ungrouped_edu: dict[str, dict] = {}

    claims_with_group_id = 0
    claims_without_group_id = 0

    for cid, claim in all_claims.items():
        if claim.claim_type == "skill":
            skill_claim_ids_raw.append(cid)
            continue

        if claim.group_id:
            claims_with_group_id += 1
            gid = str(claim.group_id)
            group = all_groups.get(gid)
            if not group:
                logger.debug("resume_selector_missing_group", claim_id=cid, group_id=gid)
                continue
            if group.group_type == "education":
                # Handled separately — skip here
                continue
            if gid not in role_groups:
                role_groups[gid] = {
                    "id": gid,
                    "name": group.name,
                    "start_date": group.start_date,
                    "end_date": group.end_date,
                    "location": group.location,
                    "type_meta": group.type_meta,
                    "group_type": group.group_type,
                    "claims": [],
                    "relevance": 0.0,
                }
            role_groups[gid]["claims"].append(cid)
            role_groups[gid]["relevance"] += claim_relevance.get(cid, 0.0)

        else:
            # Fallback: group by deprecated group_key
            claims_without_group_id += 1
            gkey = claim.group_key or ""
            if not gkey:
                continue  # truly orphan — no grouping available

            if claim.claim_type == "education":
                # group_key = "Degree | Institution" (from experience_chunker)
                parts = gkey.split("|", 1)
                institution = parts[1].strip() if len(parts) > 1 else parts[0].strip()
                degree = parts[0].strip() if len(parts) > 1 else None
                if gkey not in ungrouped_edu:
                    ungrouped_edu[gkey] = {
                        "name": institution,
                        "degree": degree,
                        "end_date": claim.date_range,
                        "location": location_lookup.get(gkey),
                    }
                continue

            if claim.claim_type not in ("work_experience", "project", "other"):
                continue

            synthetic_id = f"ungrouped:{gkey}"
            job_title = _parse_job_title_from_key(gkey)
            is_github = claim.source_type == "github"
            if synthetic_id not in ungrouped_work:
                start_date = (
                    claim.date_range.split("–")[0].strip()
                    if claim.date_range and "–" in claim.date_range
                    else claim.date_range
                )
                end_date = (
                    claim.date_range.split("–")[-1].strip()
                    if claim.date_range and "–" in claim.date_range
                    else None
                )
                ungrouped_work[synthetic_id] = {
                    "id": synthetic_id,
                    "name": _parse_group_name_from_key(gkey),
                    "start_date": start_date,
                    "end_date": end_date,
                    "location": location_lookup.get(gkey),
                    "type_meta": {"title": job_title} if job_title else None,
                    "group_type": "repository" if is_github else "role",
                    "claims": [],
                    "relevance": 0.0,
                }
            ungrouped_work[synthetic_id]["claims"].append(cid)
            ungrouped_work[synthetic_id]["relevance"] += claim_relevance.get(cid, 0.0)

    logger.info(
        "resume_selector_classified",
        claims_with_group_id=claims_with_group_id,
        claims_without_group_id=claims_without_group_id,
        skill_claims=len(skill_claim_ids_raw),
        role_groups_from_db=len(role_groups),
        role_groups_from_key=len(ungrouped_work),
        ungrouped_edu=len(ungrouped_edu),
    )

    # Merge both group sources and rank by relevance
    all_role_groups = {**role_groups, **ungrouped_work}
    ranked_groups = sorted(all_role_groups.values(), key=lambda g: g["relevance"], reverse=True)

    # ── Build sections ─────────────────────────────────────────────────────
    sections: list[ResumeSection] = []
    for g_data in ranked_groups[:MAX_ROLES]:

        def claim_sort_key(
            cid: str, _claims: dict = all_claims, _rel: dict = claim_relevance
        ) -> tuple:
            claim = _claims[cid]
            return (-_rel.get(cid, 0.0), _is_yoe_only(claim.content), claim.position)

        sorted_claim_ids = sorted(g_data["claims"], key=claim_sort_key)
        good_bullets = [c for c in sorted_claim_ids if not _is_yoe_only(all_claims[c].content)]
        yoe_bullets = [c for c in sorted_claim_ids if _is_yoe_only(all_claims[c].content)]
        final_bullets = good_bullets[:MAX_BULLETS_PER_ROLE]
        if len(final_bullets) < 3:
            final_bullets += yoe_bullets[: 3 - len(final_bullets)]

        sections.append(
            ResumeSection(
                group_id=g_data["id"],
                group_type=g_data["group_type"],
                group_name=g_data["name"],
                group_start_date=g_data["start_date"],
                group_end_date=g_data["end_date"],
                group_location=g_data["location"],
                group_type_meta=g_data["type_meta"],
                included=True,
                claim_ids=final_bullets,
            )
        )

    # ── Sort sections by end_date desc (most recent first) ─────────────────
    sections.sort(key=lambda s: _parse_date_for_sort(s.group_end_date), reverse=True)

    # ── Skills: deduplicate by content, order by relevance, cap at MAX_SKILLS ──
    skill_claim_ids_raw.sort(
        key=lambda cid: (-claim_relevance.get(cid, 0.0), all_claims[cid].position)
    )
    seen_skill_content: set[str] = set()
    skill_claim_ids: list[str] = []
    for cid in skill_claim_ids_raw:
        normalized = all_claims[cid].content.lower().strip()
        if normalized not in seen_skill_content:
            seen_skill_content.add(normalized)
            skill_claim_ids.append(cid)
            if len(skill_claim_ids) >= MAX_SKILLS:
                break

    # ── Education: merge ungrouped claims + real ExperienceGroup rows ──────
    education_data: list[EducationEntry] = []

    # 1. Ungrouped education claims (the common case — group_key = "Degree | Institution")
    for edu in ungrouped_edu.values():
        education_data.append(EducationEntry(**edu))

    # 2. Real ExperienceGroup education rows (future path / ExperienceGroup backfill)
    for gid, group in all_groups.items():
        if group.group_type == "education":
            education_data.append(
                EducationEntry(
                    name=group.name,
                    degree=(group.type_meta or {}).get("degree"),
                    end_date=group.end_date,
                    location=group.location,
                )
            )

    # Sort by end_date descending (most recent first)
    education_data.sort(key=lambda e: e.end_date or "", reverse=True)

    logger.info(
        "resume_selector_done",
        sections=len(sections),
        skills=len(skill_claim_ids),
        education=len(education_data),
        warnings=warnings,
    )

    contact = _get_contact_info(user_id, db)
    return ResumeDraft(
        generated_at=datetime.now(timezone.utc).isoformat(),
        sections=sections,
        skills_claim_ids=skill_claim_ids,
        education_data=education_data,
        education_group_ids=[],  # legacy — education_data is now the source of truth
        warnings=warnings,
        contact_override=ResumeContactOverride(
            linkedin_url=contact["linkedin"],
            location=contact["location"],
        ),
    )
