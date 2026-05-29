import re
import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.core.deps_database import get_db
from app.core.deps_user import require_approved_user
from app.models.database import (
    ExperienceClaim,
    Tailoring,
    User,
)
from app.schemas.resume import (
    BulletPolishResponse,
    PolishRequest,
    ResumeDraft,
    ResumePatchRequest,
)
from app.services.resume_polisher import polish_bullets
from app.services.resume_renderer import render_resume_html, render_resume_pdf
from app.services.resume_selector import check_resume_prerequisites, generate_resume_selection

router = APIRouter(prefix="/tailorings", tags=["resume"])
logger = structlog.get_logger(__name__)


def _candidate_email(user: User) -> str:
    """Resolve contact email using the same priority as render_resume_html."""
    if user.profile and user.profile.communication_email:
        return user.profile.communication_email
    if user.auth_identities:
        return user.auth_identities[0].email or ""
    return user.email or ""


def _get_tailoring_or_404(tailoring_id: uuid.UUID, user_id: uuid.UUID, db: Session) -> Tailoring:
    tailoring = (
        db.query(Tailoring)
        .filter(Tailoring.id == tailoring_id, Tailoring.user_id == user_id)
        .first()
    )
    if not tailoring:
        raise HTTPException(status_code=404, detail="Tailoring not found")
    return tailoring


def _resolve_draft_entities(draft: ResumeDraft, user_id: uuid.UUID, db: Session) -> dict:
    """
    Load claims referenced in the draft.
    Section metadata and education data are embedded in the draft — no group DB lookups needed.
    Returns {claim_id: ExperienceClaim}.
    """
    claim_ids = (
        {cid for s in draft.sections for cid in s.claim_ids}
        | set(draft.skills_claim_ids)
        | {cid for s in draft.sections for cid in s.rewrites}
    )
    if not claim_ids:
        return {}
    rows = (
        db.query(ExperienceClaim)
        .filter(
            ExperienceClaim.id.in_(claim_ids),
            ExperienceClaim.user_id == user_id,
        )
        .all()
    )
    return {str(c.id): c for c in rows}


def _safe_filename(tailoring: Tailoring) -> str:
    job = tailoring.job
    parts = []
    if job and job.extracted_job:
        title = job.extracted_job.get("title", "")
        company = job.extracted_job.get("company", "")
        if title:
            parts.append(title)
        if company:
            parts.append(company)
    name = "_".join(parts) or "resume"
    name = re.sub(r"[^\w\-]+", "_", name).strip("_")
    return f"resume_{name}.pdf"


def _apply_patch(draft: ResumeDraft, body: ResumePatchRequest) -> ResumeDraft:
    data = draft.model_dump()

    if body.sections is not None:
        # Build a map of existing sections by group_id for merging
        existing = {s["group_id"]: s for s in data["sections"]}
        for patched in body.sections:
            pd = patched.model_dump()
            gid = pd["group_id"]
            if gid in existing:
                existing[gid].update(pd)
            else:
                existing[gid] = pd
        data["sections"] = list(existing.values())

    if body.skills_claim_ids is not None:
        data["skills_claim_ids"] = body.skills_claim_ids

    if body.education_group_ids is not None:
        data["education_group_ids"] = body.education_group_ids

    if body.contact_override is not None:
        data["contact_override"] = body.contact_override.model_dump()

    if body.rewrites is not None:
        # Merge rewrites into the matching sections by claim_id
        for s in data["sections"]:
            for cid, rewrite in body.rewrites.items():
                if cid in s["claim_ids"]:
                    s["rewrites"][cid] = rewrite

    if body.skills_rewrites is not None:
        data["skills_rewrites"] = {**data.get("skills_rewrites", {}), **body.skills_rewrites}

    if body.education_data is not None:
        data["education_data"] = [e.model_dump() for e in body.education_data]

    return ResumeDraft(**data)


@router.post("/{tailoring_id}/resume/generate")
def generate_resume(
    tailoring_id: uuid.UUID,
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_api_key),
) -> ResumeDraft:
    tailoring = _get_tailoring_or_404(tailoring_id, user.id, db)
    prereqs = check_resume_prerequisites(user.id, db)
    if not prereqs["can_generate"]:
        raise HTTPException(status_code=422, detail="no_active_claims")
    draft = generate_resume_selection(tailoring, user.id, db)
    # Snapshot identity fields so the canvas matches what the PDF renders
    draft_data = draft.model_dump()
    draft_data["candidate_name"] = user.candidate_name
    draft_data["candidate_email"] = _candidate_email(user)
    draft = ResumeDraft(**draft_data)
    tailoring.resume_draft = draft.model_dump()
    db.commit()
    logger.info("resume_draft_generated", tailoring_id=str(tailoring_id), user_id=str(user.id))
    return draft


@router.get("/{tailoring_id}/resume")
def get_resume(
    tailoring_id: uuid.UUID,
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_api_key),
) -> ResumeDraft:
    tailoring = _get_tailoring_or_404(tailoring_id, user.id, db)
    if not tailoring.resume_draft:
        raise HTTPException(status_code=404, detail="not_generated")
    return ResumeDraft(**tailoring.resume_draft)


@router.patch("/{tailoring_id}/resume")
def patch_resume(
    tailoring_id: uuid.UUID,
    body: ResumePatchRequest,
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_api_key),
) -> ResumeDraft:
    tailoring = _get_tailoring_or_404(tailoring_id, user.id, db)
    if not tailoring.resume_draft:
        raise HTTPException(status_code=404, detail="not_generated")
    draft = ResumeDraft(**tailoring.resume_draft)
    draft = _apply_patch(draft, body)
    tailoring.resume_draft = draft.model_dump()
    db.commit()
    return draft


@router.post("/{tailoring_id}/resume/polish")
def polish_resume(
    tailoring_id: uuid.UUID,
    body: PolishRequest,
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_api_key),
) -> BulletPolishResponse:
    tailoring = _get_tailoring_or_404(tailoring_id, user.id, db)
    claims = (
        db.query(ExperienceClaim)
        .filter(
            ExperienceClaim.id.in_(body.claim_ids),
            ExperienceClaim.user_id == user.id,
        )
        .all()
    )
    job = tailoring.job
    job_title = job.extracted_job.get("title", "") if job and job.extracted_job else ""
    company = job.extracted_job.get("company", "") if job and job.extracted_job else ""
    return polish_bullets(
        claim_ids=body.claim_ids,
        claims=claims,
        job_title=job_title,
        company=company,
    )


@router.get("/{tailoring_id}/resume/html")
async def get_resume_html(
    tailoring_id: uuid.UUID,
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_api_key),
) -> Response:
    tailoring = _get_tailoring_or_404(tailoring_id, user.id, db)
    if not tailoring.resume_draft:
        raise HTTPException(status_code=404, detail="not_generated")
    draft = ResumeDraft(**tailoring.resume_draft)
    claims = _resolve_draft_entities(draft, user.id, db)
    html = render_resume_html(draft, user, tailoring, claims)
    return Response(content=html, media_type="text/html")


@router.post("/{tailoring_id}/resume/pdf")
async def export_resume_pdf(
    tailoring_id: uuid.UUID,
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
    _: None = Depends(require_api_key),
) -> Response:
    tailoring = _get_tailoring_or_404(tailoring_id, user.id, db)
    if not tailoring.resume_draft:
        raise HTTPException(status_code=404, detail="not_generated")
    draft = ResumeDraft(**tailoring.resume_draft)
    claims = _resolve_draft_entities(draft, user.id, db)
    html = render_resume_html(draft, user, tailoring, claims)
    pdf_bytes = await render_resume_pdf(html)
    filename = _safe_filename(tailoring)
    logger.info("resume_pdf_exported", tailoring_id=str(tailoring_id), user_id=str(user.id))
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
