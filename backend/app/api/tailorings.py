import logging
import re
import random
import string
from functools import partial

import anyio
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from playwright.async_api import TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.config import settings
from app.core.deps_database import get_db
from app.core.deps_user import require_approved_user
from app.core.extract import extract_markdown_content, validate_job_content
from app.services.job_extractor import extract_job
from app.services.tailoring_generator import generate_tailoring
from app.services.requirement_matcher import match_requirements
from app.services.chunk_matcher import enrich_job_chunks
from app.core.playwright_helper import get_rendered_content
from app.models.database import Experience, Job, JobChunk, Tailoring, User
from app.models.mvp_schemas import TailoringCreate
from app.services.chunk_display import SOURCE_LABELS, is_display_ready

router = APIRouter()
logger = logging.getLogger(__name__)


def _serialize_chunk(c: JobChunk) -> dict:
    return {
        "id": str(c.id),
        "chunk_type": c.chunk_type,
        "content": c.content,
        "position": c.position,
        "section": c.section,
        "match_score": c.match_score,
        "match_rationale": c.match_rationale,
        "experience_source": c.experience_source,
        "source_label": SOURCE_LABELS.get(c.experience_source) if c.experience_source else None,
        "should_render": c.should_render,
        "display_ready": is_display_ready(c),
    }


async def _fetch_and_extract_job(url: str) -> tuple[dict, str]:
    """Scrape a job posting URL and return (structured extracted_job data, raw job_markdown)."""
    try:
        html = await get_rendered_content(url)
        job_markdown = extract_markdown_content(html)
    except PlaywrightTimeoutError:
        logger.exception("Playwright timeout for %s", url)
        raise HTTPException(
            status_code=422,
            detail="That job URL took too long to load. Try again, or check that the URL is publicly accessible.",
        )
    except (PlaywrightError, Exception):
        logger.exception("Playwright scrape failed for %s", url)
        raise HTTPException(
            status_code=422,
            detail="Couldn't fetch that job posting. The URL may be behind a login or bot protection.",
        )

    valid, reason = validate_job_content(job_markdown, html=html)
    if not valid:
        logger.warning("validate_job_content failed for %s: %s", url, reason)
        raise HTTPException(status_code=422, detail=reason)

    try:
        extracted_job = extract_job(job_markdown, html=html)
        return extracted_job, job_markdown
    except Exception:
        logger.exception("Job extraction LLM failed for %s", url)
        raise HTTPException(
            status_code=502,
            detail="We scraped the page but couldn't extract a job description. The posting may be in an unsupported format.",
        )


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
    background_tasks: BackgroundTasks,
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

    extracted_job, job_markdown = await _fetch_and_extract_job(body.job_url)

    job_record = Job(
        user_id=user.id,
        job_url=body.job_url,
        extracted_job=extracted_job,
    )
    db.add(job_record)
    db.commit()
    db.refresh(job_record)

    # Score requirements before generating — offloaded to thread so the event loop
    # stays free during the LLM call (llm_parse/llm_generate are synchronous).
    try:
        ranked_matches = await anyio.to_thread.run_sync(
            partial(match_requirements, extracted_job, experience.extracted_profile)
        )
    except Exception:
        logger.exception("Requirement matching failed — proceeding without ranked matches")
        ranked_matches = []

    # Generate the tailoring document
    preferred = " ".join(filter(None, [user.preferred_first_name, user.preferred_last_name])).strip()
    candidate_name = preferred or user.name or user.email
    try:
        generated_output = await anyio.to_thread.run_sync(
            partial(generate_tailoring,
                    experience.extracted_profile,
                    extracted_job,
                    candidate_name,
                    ranked_matches=ranked_matches,
                    job_url=body.job_url)
        )
    except Exception:
        logger.exception("Tailoring generation LLM failed")
        raise HTTPException(status_code=502, detail="Tailoring generation failed. Please try again.")

    tailoring = Tailoring(
        user_id=user.id,
        job_id=job_record.id,
        generated_output=generated_output,
        model=settings.llm_model,
    )
    db.add(tailoring)
    db.commit()
    db.refresh(tailoring)

    background_tasks.add_task(enrich_job_chunks, job_record.id, job_markdown, experience.extracted_profile)

    return {
        "id": str(tailoring.id),
        "title": extracted_job.get("title"),
        "company": extracted_job.get("company"),
        "created_at": tailoring.created_at.isoformat(),
    }


@router.post("/tailorings/{tailoring_id}/regenerate")
async def regenerate_tailoring(
    tailoring_id: str,
    background_tasks: BackgroundTasks,
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

    job = tailoring.job
    job_url = job.job_url

    # Re-scrape and re-extract so title, company, and requirements reflect the
    # latest data — only the job URL is preserved across regenerations.
    extracted_job, job_markdown = await _fetch_and_extract_job(job_url)

    job.extracted_job = extracted_job
    db.commit()

    # Score requirements — offloaded to thread (sync LLM call)
    try:
        ranked_matches = await anyio.to_thread.run_sync(
            partial(match_requirements, extracted_job, experience.extracted_profile)
        )
    except Exception:
        logger.exception("Requirement matching failed — proceeding without ranked matches")
        ranked_matches = []

    preferred = " ".join(filter(None, [user.preferred_first_name, user.preferred_last_name])).strip()
    candidate_name = preferred or user.name or user.email
    try:
        generated_output = await anyio.to_thread.run_sync(
            partial(generate_tailoring,
                    experience.extracted_profile,
                    extracted_job,
                    candidate_name,
                    ranked_matches=ranked_matches,
                    job_url=job_url)
        )
    except Exception:
        logger.exception("Tailoring regeneration LLM failed")
        raise HTTPException(status_code=502, detail="Tailoring generation failed. Please try again.")

    tailoring.generated_output = generated_output
    tailoring.model = settings.llm_model
    tailoring.enrichment_status = "pending"
    db.commit()
    db.refresh(tailoring)

    background_tasks.add_task(enrich_job_chunks, job.id, job_markdown, experience.extracted_profile)

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
        "letter_public": tailoring.letter_public,
        "posting_public": tailoring.posting_public,
        "is_public": tailoring.is_public,
        "public_slug": tailoring.public_slug,
        "notion_page_url": tailoring.notion_page_url,
        "notion_posting_page_url": tailoring.notion_posting_page_url,
        "created_at": tailoring.created_at.isoformat(),
    }


@router.get("/tailorings/{tailoring_id}/chunks")
def get_tailoring_chunks(
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

    chunks = (
        db.query(JobChunk)
        .filter(JobChunk.job_id == tailoring.job_id)
        .order_by(JobChunk.position)
        .all()
    )

    return {
        "enrichment_status": tailoring.enrichment_status,
        "chunks": [_serialize_chunk(c) for c in chunks],
    }


class ShareRequest(BaseModel):
    letter: bool = False
    posting: bool = False


@router.post("/tailorings/{tailoring_id}/share")
def share_tailoring(
    tailoring_id: str,
    body: ShareRequest,
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

    tailoring.letter_public = body.letter
    tailoring.posting_public = body.posting

    if not tailoring.public_slug and (body.letter or body.posting):
        job = tailoring.job
        company = job.extracted_job.get("company") if job and job.extracted_job else None
        title = job.extracted_job.get("title") if job and job.extracted_job else None
        tailoring.public_slug = _generate_slug(company, title)

    db.commit()
    db.refresh(tailoring)

    return {
        "public_slug": tailoring.public_slug,
        "letter_public": tailoring.letter_public,
        "posting_public": tailoring.posting_public,
    }


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

    tailoring.letter_public = False
    tailoring.posting_public = False
    db.commit()


@router.get("/tailorings/public/{slug}")
def get_public_tailoring(
    slug: str,
    _: str = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    tailoring = (
        db.query(Tailoring)
        .filter(
            Tailoring.public_slug == slug,
            (Tailoring.letter_public.is_(True) | Tailoring.posting_public.is_(True)),
        )
        .first()
    )
    if not tailoring:
        raise HTTPException(status_code=404, detail="Tailoring not found")

    job = tailoring.job
    response = {
        "title": job.extracted_job.get("title") if job and job.extracted_job else None,
        "company": job.extracted_job.get("company") if job and job.extracted_job else None,
        "job_url": job.job_url if job else None,
        "generated_output": tailoring.generated_output,
        "letter_public": tailoring.letter_public,
        "posting_public": tailoring.posting_public,
        "created_at": tailoring.created_at.isoformat(),
    }

    if tailoring.posting_public:
        chunks = (
            db.query(JobChunk)
            .filter(
                JobChunk.job_id == tailoring.job_id,
                JobChunk.should_render.is_(True),
            )
            .order_by(JobChunk.position)
            .all()
        )
        response["chunks"] = [_serialize_chunk(c) for c in chunks]

    return response


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
            "job_url": t.job.job_url if t.job else None,
            "letter_public": t.letter_public,
            "posting_public": t.posting_public,
            "is_public": t.is_public,
            "public_slug": t.public_slug,
            "created_at": t.created_at.isoformat(),
        }
        for t in tailorings
    ]
