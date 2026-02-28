import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.core.deps_database import get_db
from app.core.deps_user import get_current_user
from app.core.extract import extract_markdown_content
from app.core.mvp_llm import extract_job, generate_tailoring
from app.core.playwright_helper import get_rendered_content
from app.models.database import Job, Tailoring, User
from app.models.mvp_schemas import TailoringCreate, TailoringListItem, TailoringResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/tailorings")
async def create_tailoring(
    body: TailoringCreate,
    _: str = Depends(require_api_key),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resume = user.resume
    if not resume or resume.status != "ready" or not resume.extracted_profile:
        raise HTTPException(
            status_code=422,
            detail="No resume found — upload and process a resume first.",
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
    candidate_name = user.name or user.email
    try:
        generated_output = generate_tailoring(
            resume.extracted_profile,
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


@router.get("/tailorings/{tailoring_id}")
def get_tailoring(
    tailoring_id: str,
    _: str = Depends(require_api_key),
    user: User = Depends(get_current_user),
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
        "created_at": tailoring.created_at.isoformat(),
    }


@router.get("/tailorings")
def list_tailorings(
    _: str = Depends(require_api_key),
    user: User = Depends(get_current_user),
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
            "created_at": t.created_at.isoformat(),
        }
        for t in tailorings
    ]
