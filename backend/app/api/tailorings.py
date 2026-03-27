import json
import logging
import re
import random
import string
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
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

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",  # disable nginx buffering
}


def _sse(event: str | None, data: str) -> str:
    """Format a single SSE message."""
    if event:
        return f"event: {event}\ndata: {data}\n\n"
    return f"data: {data}\n\n"


def _validate_profile(profile: dict) -> None:
    """
    Raise HTTPException 422 if the extracted profile is too thin to generate a useful tailoring.
    Checks that at least one of: resume work experience, resume summary, or GitHub repos is present.
    """
    resume = profile.get("resume") or {}
    has_work = bool(resume.get("work_experience"))
    has_summary = bool((resume.get("summary") or "").strip())
    has_github = bool(profile.get("github_repos"))
    if not (has_work or has_summary or has_github):
        raise HTTPException(
            status_code=422,
            detail=(
                "Your profile doesn't have enough information to generate a tailoring. "
                "Make sure your resume includes a summary or work experience, or add GitHub repos."
            ),
        )


def _serialize_chunk(c: JobChunk) -> dict:
    return {
        "id": str(c.id),
        "chunk_type": c.chunk_type,
        "content": c.content,
        "position": c.position,
        "section": c.section,
        "match_score": c.match_score,
        "match_rationale": c.match_rationale,
        "advocacy_blurb": c.advocacy_blurb,
        "experience_source": c.experience_source,
        "source_label": SOURCE_LABELS.get(c.experience_source) if c.experience_source else None,
        "should_render": c.should_render,
        "display_ready": is_display_ready(c),
    }


async def _scrape_job_url(url: str) -> tuple[str, str]:
    """Playwright-fetch a URL and return (html, job_markdown). Raises HTTPException on failure."""
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
    return html, job_markdown



def _finalize_tailoring(
    tailoring_id: str,
    job_id: str,
    job_markdown: str,
    html: str,
    extracted_profile: dict,
    candidate_name: str,
    job_url: str,
    pronouns: str | None = None,
) -> None:
    """
    Background task: extract the job, run requirement matching + tailoring generation,
    then persist the result and trigger chunk enrichment.

    Creates its own DB session (request session is closed by the time this runs).
    Updates generation_stage as each step starts so the frontend can poll progress.
    Stages: extracting → matching → generating
    """
    from app.clients.database import SessionLocal
    db = SessionLocal()
    try:
        tailoring = db.get(Tailoring, tailoring_id)
        if not tailoring:
            logger.error("_finalize_tailoring: tailoring %s not found", tailoring_id)
            return

        tailoring.generation_started_at = datetime.now(timezone.utc)
        tailoring.generation_stage = "extracting"
        db.commit()

        # Step 1: Extract structured job data from scraped markdown
        try:
            extracted_job = extract_job(job_markdown, html=html)
        except Exception:
            logger.exception("Job extraction failed for tailoring %s", tailoring_id)
            tailoring.generation_status = "error"
            tailoring.generation_stage = None
            tailoring.generation_error = "We couldn't extract the job description. Try regenerating."
            db.commit()
            return

        job = db.get(Job, job_id)
        if job:
            job.extracted_job = extracted_job
            db.commit()

        tailoring.generation_stage = "matching"
        db.commit()

        try:
            ranked_matches = match_requirements(extracted_job, extracted_profile, pronouns=pronouns)
        except Exception:
            logger.exception("Requirement matching failed — proceeding without ranked matches")
            ranked_matches = []

        tailoring.generation_stage = "generating"
        db.commit()

        try:
            generated_output = generate_tailoring(
                extracted_profile,
                extracted_job,
                candidate_name,
                ranked_matches=ranked_matches,
                job_url=job_url,
                pronouns=pronouns,
            )
        except Exception:
            logger.exception("Tailoring generation failed for tailoring %s", tailoring_id)
            tailoring.generation_status = "error"
            tailoring.generation_stage = None
            tailoring.generation_error = "Tailoring generation failed. You can retry by regenerating."
            db.commit()
            return

        tailoring.generated_output = generated_output
        tailoring.model = settings.llm_model
        tailoring.generation_status = "ready"
        tailoring.generation_stage = None
        tailoring.enrichment_status = "pending"
        db.commit()
        logger.info("_finalize_tailoring: tailoring %s ready", tailoring_id)

    except Exception:
        logger.exception("Unexpected error in _finalize_tailoring for tailoring %s", tailoring_id)
        try:
            tailoring = db.get(Tailoring, tailoring_id)
            if tailoring:
                tailoring.generation_status = "error"
                tailoring.generation_stage = None
                tailoring.generation_error = "An unexpected error occurred."
                db.commit()
        except Exception:
            pass
    finally:
        db.close()

    # Chunk enrichment runs after generation succeeds
    try:
        enrich_job_chunks(job_id, job_markdown, extracted_profile, pronouns=pronouns)
    except Exception:
        logger.exception("Chunk enrichment failed for job %s", job_id)


async def _stream_tailoring(
    job_url: str,
    user: User,
    db: Session,
    background_tasks: BackgroundTasks,
    existing_tailoring: Tailoring | None = None,
) -> AsyncGenerator[str, None]:
    """
    SSE generator: scrapes and extracts the job, creates DB records, emits a
    `ready` event (so the frontend can redirect immediately), then schedules
    matching + generation as a background task.

    Stage events: scraping → extracting → ready
    Error events: on any failure before the background task is scheduled.
    """
    try:
        experience = db.query(Experience).filter(
            Experience.user_id == user.id,
            Experience.status == "ready",
        ).first()
        if not experience or not experience.extracted_profile:
            yield _sse("error", json.dumps({"detail": "No experience found — upload a resume or add a GitHub profile first."}))
            return
        try:
            _validate_profile(experience.extracted_profile)
        except HTTPException as exc:
            yield _sse("error", json.dumps({"detail": exc.detail}))
            return

        # Capture what we need from the session before the long async scrape.
        # db.commit() closes the implicit read transaction so the connection doesn't
        # sit idle-in-transaction for the entire scraping duration (5–15s).
        extracted_profile = experience.extracted_profile
        preferred = " ".join(filter(None, [user.preferred_first_name, user.preferred_last_name])).strip()
        candidate_name = preferred or user.name or user.email
        candidate_pronouns = user.pronouns or None
        if existing_tailoring:
            existing_tailoring_id = str(existing_tailoring.id)
            existing_job_id = str(existing_tailoring.job_id)
        db.commit()

        # Stage: scraping — only synchronous phase before redirect
        yield _sse("stage", "scraping")
        try:
            html, job_markdown = await _scrape_job_url(job_url)
        except HTTPException as exc:
            yield _sse("error", json.dumps({"detail": exc.detail}))
            return

        # Job is valid — create DB records and redirect immediately.
        # Extraction, matching, and generation all run in the background task.
        if existing_tailoring:
            # Re-fetch after commit so ORM attributes aren't expired
            tailoring = db.get(Tailoring, existing_tailoring_id)
            tailoring.generated_output = None
            tailoring.generation_status = "generating"
            tailoring.generation_stage = "extracting"
            tailoring.generation_error = None
            tailoring.enrichment_status = "pending"
            db.commit()
            job_record = db.get(Job, existing_job_id)
        else:
            job_record = Job(user_id=user.id, job_url=job_url)
            db.add(job_record)
            db.commit()
            db.refresh(job_record)

            tailoring = Tailoring(
                user_id=user.id,
                job_id=job_record.id,
                generated_output=None,
                generation_status="generating",
                generation_stage="extracting",
            )
            db.add(tailoring)
            db.commit()
            db.refresh(tailoring)

        background_tasks.add_task(
            _finalize_tailoring,
            str(tailoring.id),
            str(job_record.id),
            job_markdown,
            html,
            extracted_profile,
            candidate_name,
            job_url,
            candidate_pronouns,
        )

        yield _sse("ready", json.dumps({"id": str(tailoring.id)}))

    except Exception:
        logger.exception("Unexpected error in _stream_tailoring")
        yield _sse("error", json.dumps({"detail": "An unexpected error occurred. Please try again."}))


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
    return StreamingResponse(
        _stream_tailoring(body.job_url, user, db, background_tasks),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


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

    return StreamingResponse(
        _stream_tailoring(tailoring.job.job_url, user, db, background_tasks, existing_tailoring=tailoring),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


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
        "generation_status": tailoring.generation_status,
        "generation_stage": tailoring.generation_stage,
        "generation_error": tailoring.generation_error,
        "generation_started_at": tailoring.generation_started_at.isoformat() if tailoring.generation_started_at else None,
        "letter_public": tailoring.letter_public,
        "posting_public": tailoring.posting_public,
        "is_public": tailoring.is_public,
        "public_slug": tailoring.public_slug,
        "author_username_slug": tailoring.user.username_slug if tailoring.user else None,
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


@router.get("/tailorings/public/{username_slug}/{tailoring_slug}")
def get_public_tailoring(
    username_slug: str,
    tailoring_slug: str,
    _: str = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    author = db.query(User).filter(User.username_slug == username_slug).first()
    if not author:
        raise HTTPException(status_code=404, detail="Tailoring not found")

    tailoring = (
        db.query(Tailoring)
        .filter(
            Tailoring.user_id == author.id,
            Tailoring.public_slug == tailoring_slug,
            (Tailoring.letter_public.is_(True) | Tailoring.posting_public.is_(True)),
        )
        .first()
    )
    if not tailoring:
        raise HTTPException(status_code=404, detail="Tailoring not found")

    job = tailoring.job
    author = tailoring.user
    response = {
        "title": job.extracted_job.get("title") if job and job.extracted_job else None,
        "company": job.extracted_job.get("company") if job and job.extracted_job else None,
        "job_url": job.job_url if job else None,
        "generated_output": tailoring.generated_output,
        "letter_public": tailoring.letter_public,
        "posting_public": tailoring.posting_public,
        "created_at": tailoring.created_at.isoformat(),
        "author_slug": author.username_slug if author else None,
        "author_name": (
            " ".join(p for p in [author.preferred_first_name, author.preferred_last_name] if p).strip()
            or author.name
        ) if author else None,
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
            "generation_status": t.generation_status,
            "letter_public": t.letter_public,
            "posting_public": t.posting_public,
            "is_public": t.is_public,
            "public_slug": t.public_slug,
            "created_at": t.created_at.isoformat(),
        }
        for t in tailorings
    ]
