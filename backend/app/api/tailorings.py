import logging
import re
import random
import string

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.config import settings
from app.core.deps_database import get_db
from app.core.deps_user import require_approved_user
from app.core.extract import extract_markdown_content
from app.services.job_extractor import extract_job
from app.services.tailoring_generator import generate_tailoring
from app.core.playwright_helper import get_rendered_content
from app.models.database import Experience, Job, Tailoring, User
from app.models.mvp_schemas import TailoringCreate, TailoringListItem, TailoringResponse

router = APIRouter()
logger = logging.getLogger(__name__)


def _generate_slug(company: str | None, title: str | None) -> str:
    def slugify(s: str) -> str:
        s = s.lower().strip()
        s = re.sub(r'[^\w\s-]', '', s)
        s = re.sub(r'[\s_-]+', '-', s).strip('-')
        return s[:20]
    parts = [p for p in [slugify(company or ""), slugify(title or "")] if p]
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return '-'.join(parts + [suffix])


@router.post("/tailorings")
async def create_tailoring(
    body: TailoringCreate,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    experience = db.query(Experience).filter(
        Experience.user_id == user.id,
        Experience.status == "ready",
    ).first()
    if not experience or not experience.extracted_profile:
        raise HTTPException(
            status_code=422,
            detail="No experience found — upload a resume or add a GitHub profile first.",
        )

    # Scrape and extract job data
    try:
        html = await get_rendered_content(body.job_url)
        job_markdown = extract_markdown_content(html)
    except Exception as e:
        logger.exception("Playwright scrape failed for %s", body.job_url)
        raise HTTPException(status_code=422, detail=f"Could not fetch that URL: {e}")

    try:
        extracted_job = extract_job(job_markdown)
    except Exception as e:
        logger.exception("Job extraction LLM failed")
        raise HTTPException(status_code=502, detail=f"Job extraction failed: {e}")

    job_record = Job(
        user_id=user.id,
        job_url=body.job_url,
        extracted_job=extracted_job,
    )
    db.add(job_record)
    db.commit()
    db.refresh(job_record)

    # Generate the tailoring document
    preferred = " ".join(filter(None, [user.preferred_first_name, user.preferred_last_name])).strip()
    candidate_name = preferred or user.name or user.email
    try:
        generated_output = generate_tailoring(
            experience.extracted_profile,
            extracted_job,
            candidate_name,
        )
    except Exception as e:
        logger.exception("Tailoring generation LLM failed")
        raise HTTPException(status_code=502, detail=f"Tailoring generation failed: {e}")

    tailoring = Tailoring(
        user_id=user.id,
        job_id=job_record.id,
        generated_output=generated_output,
        model=settings.llm_model,
    )
    db.add(tailoring)
    db.commit()
    db.refresh(tailoring)

    return {
        "id": str(tailoring.id),
        "title": extracted_job.get("title"),
        "company": extracted_job.get("company"),
        "created_at": tailoring.created_at.isoformat(),
    }


@router.post("/tailorings/{tailoring_id}/regenerate")
def regenerate_tailoring(
    tailoring_id: str,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    tailoring = (
        db.query(Tailoring)
        .filter(Tailoring.id == tailoring_id, Tailoring.user_id == user.id)
        .first()
    )
    if not tailoring:
        raise HTTPException(status_code=404, detail="Tailoring not found")

    experience = db.query(Experience).filter(
        Experience.user_id == user.id,
        Experience.status == "ready",
    ).first()
    if not experience or not experience.extracted_profile:
        raise HTTPException(status_code=422, detail="No experience found.")

    preferred = " ".join(filter(None, [user.preferred_first_name, user.preferred_last_name])).strip()
    candidate_name = preferred or user.name or user.email
    try:
        generated_output = generate_tailoring(
            experience.extracted_profile,
            tailoring.job.extracted_job,
            candidate_name,
        )
    except Exception as e:
        logger.exception("Tailoring regeneration LLM failed")
        raise HTTPException(status_code=502, detail=f"Tailoring generation failed: {e}")

    tailoring.generated_output = generated_output
    tailoring.model = settings.llm_model
    db.commit()
    db.refresh(tailoring)

    return {"id": str(tailoring.id), "generated_output": tailoring.generated_output}


@router.delete("/tailorings/{tailoring_id}", status_code=204)
def delete_tailoring(
    tailoring_id: str,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    tailoring = (
        db.query(Tailoring)
        .filter(Tailoring.id == tailoring_id, Tailoring.user_id == user.id)
        .first()
    )
    if not tailoring:
        raise HTTPException(status_code=404, detail="Tailoring not found")

    job_id = tailoring.job_id
    db.delete(tailoring)
    db.flush()  # satisfy FK before deleting job

    job = db.query(Job).filter(Job.id == job_id).first()
    if job:
        db.delete(job)

    db.commit()


@router.get("/tailorings/{tailoring_id}")
def get_tailoring(
    tailoring_id: str,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    tailoring = (
        db.query(Tailoring)
        .filter(Tailoring.id == tailoring_id, Tailoring.user_id == user.id)
        .first()
    )
    if not tailoring:
        raise HTTPException(status_code=404, detail="Tailoring not found")

    job = tailoring.job
    return {
        "id": str(tailoring.id),
        "title": job.extracted_job.get("title") if job.extracted_job else None,
        "company": job.extracted_job.get("company") if job.extracted_job else None,
        "job_url": job.job_url if job else None,
        "generated_output": tailoring.generated_output,
        "model": tailoring.model,
        "is_public": tailoring.is_public,
        "public_slug": tailoring.public_slug,
        "created_at": tailoring.created_at.isoformat(),
    }


@router.post("/tailorings/{tailoring_id}/share")
def share_tailoring(
    tailoring_id: str,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    tailoring = (
        db.query(Tailoring)
        .filter(Tailoring.id == tailoring_id, Tailoring.user_id == user.id)
        .first()
    )
    if not tailoring:
        raise HTTPException(status_code=404, detail="Tailoring not found")

    if not tailoring.public_slug:
        job = tailoring.job
        company = job.extracted_job.get("company") if job and job.extracted_job else None
        title = job.extracted_job.get("title") if job and job.extracted_job else None
        tailoring.public_slug = _generate_slug(company, title)

    tailoring.is_public = True
    db.commit()
    db.refresh(tailoring)

    return {"public_slug": tailoring.public_slug}


@router.delete("/tailorings/{tailoring_id}/share", status_code=204)
def unshare_tailoring(
    tailoring_id: str,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    tailoring = (
        db.query(Tailoring)
        .filter(Tailoring.id == tailoring_id, Tailoring.user_id == user.id)
        .first()
    )
    if not tailoring:
        raise HTTPException(status_code=404, detail="Tailoring not found")

    tailoring.is_public = False
    db.commit()


@router.get("/tailorings/public/{slug}")
def get_public_tailoring(
    slug: str,
    _: str = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    tailoring = (
        db.query(Tailoring)
        .filter(Tailoring.public_slug == slug, Tailoring.is_public.is_(True))
        .first()
    )
    if not tailoring:
        raise HTTPException(status_code=404, detail="Tailoring not found")

    job = tailoring.job
    return {
        "title": job.extracted_job.get("title") if job and job.extracted_job else None,
        "company": job.extracted_job.get("company") if job and job.extracted_job else None,
        "job_url": job.job_url if job else None,
        "generated_output": tailoring.generated_output,
        "created_at": tailoring.created_at.isoformat(),
    }


@router.get("/tailorings")
def list_tailorings(
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    tailorings = (
        db.query(Tailoring)
        .filter(Tailoring.user_id == user.id)
        .order_by(Tailoring.created_at.desc())
        .all()
    )

    return [
        {
            "id": str(t.id),
            "title": t.job.extracted_job.get("title") if t.job and t.job.extracted_job else None,
            "company": t.job.extracted_job.get("company") if t.job and t.job.extracted_job else None,
            "is_public": t.is_public,
            "public_slug": t.public_slug,
            "created_at": t.created_at.isoformat(),
        }
        for t in tailorings
    ]
