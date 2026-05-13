import json
import logging
import random
import re
import string
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.auth import require_api_key
from app.config import settings
from app.core.deps_database import get_db
from app.core.deps_user import require_approved_user
from app.core.extract import extract_markdown_content, validate_job_content
from app.core.playwright_helper import get_rendered_content
from app.core.token_utils import truncate_to_tokens
from app.models.database import (
    Experience,
    Job,
    JobChunk,
    LlmTriggerLog,
    Tailoring,
    TailoringDebugLog,
    User,
)
from app.models.mvp_schemas import TailoringCreate, _validate_job_url
from app.services.chunk_display import SOURCE_LABELS, is_display_ready
from app.services.chunk_matcher import enrich_job_chunks, re_enrich_single_chunk
from app.services.gap_analyzer import run_gap_analysis
from app.services.job_extractor import extract_job
from app.services.tailoring_generator import (
    _build_ranked_matches_from_chunks,
    _format_sourced_profile,
    generate_tailoring,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Combined limit: tailoring creates + regens share one pool per user per hour.
# Each trigger costs ~4 LLM calls (job extraction, req matching, generation, chunk scoring).
_TAILORING_HOURLY_LIMIT = 10
_TAILORING_WARN_THRESHOLD = 8


def _get_tailoring_trigger_count(user_id, db: Session) -> int:
    """Return the number of tailoring LLM triggers in the last hour for a user."""
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    return (
        db.query(LlmTriggerLog)
        .filter(
            LlmTriggerLog.user_id == user_id,
            LlmTriggerLog.event_type.in_(["tailoring_create", "tailoring_regen"]),
            LlmTriggerLog.created_at >= one_hour_ago,
        )
        .count()
    )


def _check_tailoring_rate_limit(user_id, db: Session) -> None:
    """Raise 429 if the user has hit the combined create+regen limit in the last hour."""
    count = _get_tailoring_trigger_count(user_id, db)
    if count >= _TAILORING_HOURLY_LIMIT:
        logger.warning("Rate limit hit: user=%s tailoring triggers in last hour=%d", user_id, count)
        raise HTTPException(
            status_code=429,
            detail="You've created too many tailorings in the last hour. Please wait before trying again.",
        )


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
        "experience_sources": c.experience_sources or [],
        "source_label": SOURCE_LABELS.get(c.experience_source) if c.experience_source else None,
        "should_render": c.should_render,
        "is_requirement": c.is_requirement,
        "display_ready": is_display_ready(c),
        "scored_content": c.scored_content,
    }


async def _scrape_job_url(url: str) -> tuple[str, str, bool, str]:
    """Fetch a URL and return (html, job_markdown, valid, reason).

    Tries Greenhouse/Lever public APIs first. Falls through to Playwright
    on no ATS match or API failure. Raises HTTPException only on hard
    Playwright failures. Soft validation failures are returned as
    (html, job_markdown, False, reason).
    """
    from app.core.ats_client import try_ats_fetch

    ats_markdown = try_ats_fetch(url)
    if ats_markdown:
        job_markdown = truncate_to_tokens(ats_markdown, max_tokens=12_000, model=settings.llm_model)
        logger.info("_scrape_job_url: ATS direct fetch succeeded for %s", url)
        return "", job_markdown, True, ""

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
    # Cap before validation so the validator sees the same text the LLM would.
    job_markdown = truncate_to_tokens(job_markdown, max_tokens=12_000, model=settings.llm_model)
    valid, reason = validate_job_content(job_markdown, html=html)
    if not valid:
        logger.warning("validate_job_content failed for %s: %s", url, reason)
    return html, job_markdown, valid, reason or ""


def _finalize_tailoring(
    tailoring_id: str,
    job_id: str,
    job_markdown: str,
    html: str,
    extracted_profile: dict,
    candidate_name: str,
    job_url: str | None,
    pronouns: str | None = None,
    experience_id: uuid.UUID | None = None,
    is_manual: bool = False,
) -> None:
    """
    Background task: extract the job, enrich chunks, derive ranked matches from chunk
    scores, generate the tailoring letter, then run gap analysis.

    Creates its own DB session (request session is closed by the time this runs).
    Updates generation_stage as each step starts so the frontend can poll progress.
    Stages: extracting → enriching → generating

    When is_manual=True, job extraction is skipped — extracted_job is already
    pre-seeded on the Job record from company/title/description fields.
    """
    from app.clients.database import SessionLocal

    # Phase 1: job extraction (extracting stage)
    extracted_job: dict = {}
    db = SessionLocal()
    try:
        tailoring = db.get(Tailoring, tailoring_id)
        if not tailoring:
            logger.error("_finalize_tailoring: tailoring %s not found", tailoring_id)
            return

        tailoring.generation_started_at = datetime.now(timezone.utc)
        tailoring.generation_stage = "extracting"
        # Snapshot the exact formatted profile passed to the LLM so the debug panel
        # always shows what the model actually saw, regardless of later experience edits.
        tailoring.profile_snapshot = _format_sourced_profile(
            extracted_profile, candidate_name=candidate_name, pronouns=pronouns
        )
        db.commit()

        if is_manual:
            # Manual path: company/title were pre-seeded; skip LLM extraction.
            job = db.get(Job, job_id)
            extracted_job = (job.extracted_job or {}) if job else {}
        else:
            try:
                extracted_job = extract_job(job_markdown, html=html)
            except Exception:
                logger.exception("Job extraction failed for tailoring %s", tailoring_id)
                tailoring.generation_status = "error"
                tailoring.generation_stage = None
                tailoring.generation_error = (
                    "We couldn't extract the job description. Try regenerating."
                )
                db.commit()
                return

            job = db.get(Job, job_id)
            if job:
                job.extracted_job = extracted_job
                db.commit()

        tailoring.generation_stage = "enriching"
        db.commit()

    except Exception:
        logger.exception(
            "Unexpected error in _finalize_tailoring (extraction) for tailoring %s", tailoring_id
        )
        try:
            tailoring = db.get(Tailoring, tailoring_id)
            if tailoring:
                tailoring.generation_status = "error"
                tailoring.generation_stage = None
                tailoring.generation_error = "An unexpected error occurred."
                db.commit()
        except Exception:
            pass
        return
    finally:
        db.close()

    # Phase 2: chunk enrichment (uses its own session)
    try:
        enrich_job_chunks(
            job_id,
            job_markdown,
            extracted_profile,
            pronouns=pronouns,
            experience_id=experience_id,
            candidate_name=candidate_name,
        )
    except Exception:
        logger.exception("Chunk enrichment failed for job %s", job_id)

    # Phase 3: read chunk scores → build ranked matches for the letter
    ranked_matches: list[dict] = []
    try:
        with SessionLocal() as chunk_db:
            ranked_matches = _build_ranked_matches_from_chunks(uuid.UUID(job_id), chunk_db)
    except Exception:
        logger.exception(
            "Failed to build ranked matches from chunks for job %s — proceeding without", job_id
        )

    # Phase 4: letter generation (generating stage)
    db = SessionLocal()
    try:
        tailoring = db.get(Tailoring, tailoring_id)
        if not tailoring:
            logger.error(
                "_finalize_tailoring: tailoring %s not found after enrichment", tailoring_id
            )
            return

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
            tailoring.generation_error = (
                "Tailoring generation failed. You can retry by regenerating."
            )
            db.commit()
            return

        now = datetime.now(timezone.utc)
        tailoring.generated_output = generated_output
        tailoring.model = settings.llm_model
        tailoring.generation_status = "ready"
        tailoring.generation_stage = None
        tailoring.generated_at = now
        tailoring.enrichment_status = "complete"  # backward compat — enrichment ran inline
        tailoring.matching_mode = settings.matching_mode
        if tailoring.generation_started_at:
            delta_ms = (now - tailoring.generation_started_at).total_seconds() * 1000
            tailoring.generation_duration_ms = int(delta_ms)
        db.commit()
        logger.info("_finalize_tailoring: tailoring %s ready", tailoring_id)

        try:
            debug_log = TailoringDebugLog(
                tailoring_id=tailoring.id,
                event_type="generation_complete",
                payload={
                    "matching_mode": settings.matching_mode,
                    "embedding_model": settings.embedding_model,
                    "llm_model": settings.llm_model,
                    "generation_duration_ms": tailoring.generation_duration_ms,
                },
            )
            db.add(debug_log)
            db.commit()
        except Exception:
            logger.warning("Failed to write TailoringDebugLog for tailoring %s", tailoring_id)

    except Exception:
        logger.exception(
            "Unexpected error in _finalize_tailoring (generation) for tailoring %s", tailoring_id
        )
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

    # Gap analysis runs after generation succeeds so chunk_ids are resolvable.
    # Non-fatal: a failure here must never affect the tailoring itself.
    try:
        run_gap_analysis(tailoring_id)
    except Exception:
        logger.exception("Gap analysis failed for tailoring %s — non-fatal", tailoring_id)


async def _stream_tailoring(
    request: TailoringCreate,
    user: User,
    db: Session,
    background_tasks: BackgroundTasks,
    existing_tailoring: Tailoring | None = None,
) -> AsyncGenerator[str, None]:
    """
    SSE generator: scrapes (URL path) or uses manual input, creates DB records,
    emits a `ready` event (so the frontend can redirect immediately), then schedules
    matching + generation as a background task.

    Stage events: scraping (URL path only) → ready
    parse_warning: emitted when URL content fails validation but skip_validation=False.
                   No DB records are created; frontend can retry with skip_validation=True
                   or fill in manual fields.
    Error events: on any hard failure before the background task is scheduled.
    """
    is_manual = bool(request.description and request.description.strip())
    tailoring: Tailoring | None = None
    try:
        experience = (
            db.query(Experience)
            .filter(
                Experience.user_id == user.id,
                Experience.status == "ready",
            )
            .first()
        )
        if not experience or not experience.extracted_profile:
            yield _sse(
                "error",
                json.dumps(
                    {
                        "detail": "No experience found — upload a resume or add a GitHub profile first."
                    }
                ),
            )
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
        experience_id = experience.id
        preferred = " ".join(
            filter(None, [user.preferred_first_name, user.preferred_last_name])
        ).strip()
        candidate_name = preferred or user.name or user.email
        candidate_pronouns = user.pronouns or None
        if existing_tailoring:
            existing_tailoring_id = str(existing_tailoring.id)
            existing_job_id = str(existing_tailoring.job_id)
        db.commit()

        if is_manual:
            # Manual path: use provided description directly, no scraping.
            html = ""
            job_markdown = truncate_to_tokens(
                request.description, max_tokens=12_000, model=settings.llm_model
            )
        else:
            # URL path: scrape and optionally validate.
            yield _sse("stage", "scraping")
            try:
                html, job_markdown, valid, reason = await _scrape_job_url(request.job_url)
            except HTTPException as exc:
                yield _sse("error", json.dumps({"detail": exc.detail}))
                return

            if not valid and not request.skip_validation:
                # Soft failure — surface warning to the user. No DB records created.
                yield _sse("parse_warning", json.dumps({"reason": reason}))
                return
            # If not valid but skip_validation=True, continue with partial content.

        # Create or reset DB records, then redirect immediately.
        # Extraction, matching, and generation all run in the background task.
        if existing_tailoring:
            # Re-fetch after commit so ORM attributes aren't expired
            tailoring = db.get(Tailoring, existing_tailoring_id)
            tailoring.generated_output = None
            tailoring.generation_status = "generating"
            tailoring.generation_stage = "extracting"
            tailoring.generation_error = None
            tailoring.enrichment_status = "pending"
            tailoring.gap_analysis_status = "pending"
            db.commit()
            job_record = db.get(Job, existing_job_id)
        else:
            job_record = Job(
                user_id=user.id,
                job_url=request.job_url or None,
                raw_description=request.description or None,
            )
            if is_manual:
                job_record.extracted_job = {
                    "title": request.title,
                    "company": request.company,
                    "requirements": [],
                }
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
            request.job_url,
            candidate_pronouns,
            experience_id,
            is_manual,
        )

        yield _sse("ready", json.dumps({"id": str(tailoring.id)}))

    except Exception:
        logger.exception("Unexpected error in _stream_tailoring")
        if tailoring is not None and tailoring.generation_status == "generating":
            try:
                tailoring.generation_status = "error"
                tailoring.generation_error = "An unexpected error occurred."
                db.commit()
            except Exception:
                logger.exception(
                    "Failed to mark tailoring %s as error after unexpected failure", tailoring.id
                )
        yield _sse(
            "error", json.dumps({"detail": "An unexpected error occurred. Please try again."})
        )


def _generate_slug(company: str | None, title: str | None) -> str:
    def slugify(s: str) -> str:
        s = s.lower().strip()
        s = re.sub(r"[^\w\s-]", "", s)
        s = re.sub(r"[\s_-]+", "-", s).strip("-")
        return s[:20]

    parts = [p for p in [slugify(company or ""), slugify(title or "")] if p]
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return "-".join(parts + [suffix])


@router.post("/tailorings")
async def create_tailoring(
    body: TailoringCreate,
    background_tasks: BackgroundTasks,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    if body.job_url:
        try:
            _validate_job_url(body.job_url, is_local=settings.environment == "local")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
    _check_tailoring_rate_limit(user.id, db)
    db.add(LlmTriggerLog(user_id=user.id, event_type="tailoring_create"))
    db.commit()
    return StreamingResponse(
        _stream_tailoring(body, user, db, background_tasks),
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

    _check_tailoring_rate_limit(user.id, db)
    tailoring.last_regenerated_at = datetime.now(timezone.utc)
    db.add(LlmTriggerLog(user_id=user.id, event_type="tailoring_regen"))
    db.commit()

    # Reconstruct a request from stored job data.
    # If raw_description is set it's a manual tailoring — skip re-scraping.
    job = tailoring.job
    regen_req = TailoringCreate.model_construct(
        job_url=job.job_url if job else None,
        description=job.raw_description if job else None,
        company=job.extracted_job.get("company") if job and job.extracted_job else None,
        title=job.extracted_job.get("title") if job and job.extracted_job else None,
        skip_validation=True,
    )

    return StreamingResponse(
        _stream_tailoring(regen_req, user, db, background_tasks, existing_tailoring=tailoring),
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
        "generation_started_at": tailoring.generation_started_at.isoformat()
        if tailoring.generation_started_at
        else None,
        "letter_public": tailoring.letter_public,
        "posting_public": tailoring.posting_public,
        "is_public": tailoring.is_public,
        "public_slug": tailoring.public_slug,
        "author_username_slug": tailoring.user.username_slug if tailoring.user else None,
        "notion_page_url": tailoring.notion_page_url,
        "notion_posting_page_url": tailoring.notion_posting_page_url,
        "gap_analysis": tailoring.gap_analysis,
        "gap_analysis_status": tailoring.gap_analysis_status,
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


class PatchChunkRequest(BaseModel):
    content: str | None = None
    should_render: bool | None = None
    is_requirement: bool | None = None
    section: str | None = None
    position: int | None = None
    chunk_type: str | None = None  # "bullet" | "paragraph" (header not user-editable)


class CreateChunkRequest(BaseModel):
    content: str
    section: str
    chunk_type: str = "bullet"


class MergeChunksRequest(BaseModel):
    primary_chunk_id: str
    secondary_chunk_id: str


class RenameGroupRequest(BaseModel):
    old_section: str
    new_section: str | None = None  # None = ungroup (sets section to null)


def _get_tailoring_chunk(
    tailoring_id: str, chunk_id: str, user: User, db: Session
) -> tuple[Tailoring, JobChunk]:
    """Return (tailoring, chunk) or raise 404. Verifies ownership."""
    tailoring = (
        db.query(Tailoring)
        .filter(Tailoring.id == tailoring_id, Tailoring.user_id == user.id)
        .first()
    )
    if not tailoring:
        raise HTTPException(status_code=404, detail="Tailoring not found")
    chunk = (
        db.query(JobChunk)
        .filter(JobChunk.id == chunk_id, JobChunk.job_id == tailoring.job_id)
        .first()
    )
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")
    return tailoring, chunk


@router.patch("/tailorings/{tailoring_id}/chunks/{chunk_id}")
def patch_chunk(
    tailoring_id: str,
    chunk_id: str,
    body: PatchChunkRequest,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    tailoring, chunk = _get_tailoring_chunk(tailoring_id, chunk_id, user, db)
    if body.content is not None:
        chunk.content = body.content
    if body.should_render is not None:
        chunk.should_render = body.should_render
    if body.is_requirement is not None:
        chunk.is_requirement = body.is_requirement
    if body.section is not None:
        chunk.section = body.section
    if body.position is not None:
        chunk.position = body.position
    if body.chunk_type is not None and body.chunk_type in ("bullet", "paragraph"):
        chunk.chunk_type = body.chunk_type
    db.commit()
    db.refresh(chunk)
    return _serialize_chunk(chunk)


@router.delete("/tailorings/{tailoring_id}/chunks/{chunk_id}")
def delete_chunk(
    tailoring_id: str,
    chunk_id: str,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    tailoring, chunk = _get_tailoring_chunk(tailoring_id, chunk_id, user, db)
    db.delete(chunk)
    db.commit()
    return {"deleted": chunk_id}


@router.post("/tailorings/{tailoring_id}/chunks")
def create_chunk(
    tailoring_id: str,
    body: CreateChunkRequest,
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

    from sqlalchemy import func as sqlfunc

    max_pos = (
        db.query(sqlfunc.max(JobChunk.position))
        .filter(JobChunk.job_id == tailoring.job_id)
        .scalar()
    ) or 0

    chunk = JobChunk(
        job_id=tailoring.job_id,
        chunk_type=body.chunk_type,
        content=body.content,
        section=body.section,
        position=max_pos + 1,
        is_requirement=True,
        should_render=True,
    )
    db.add(chunk)
    db.commit()
    db.refresh(chunk)
    return _serialize_chunk(chunk)


@router.post("/tailorings/{tailoring_id}/chunks/merge")
def merge_chunks(
    tailoring_id: str,
    body: MergeChunksRequest,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    tailoring, primary = _get_tailoring_chunk(tailoring_id, body.primary_chunk_id, user, db)
    secondary = (
        db.query(JobChunk)
        .filter(JobChunk.id == body.secondary_chunk_id, JobChunk.job_id == tailoring.job_id)
        .first()
    )
    if not secondary:
        raise HTTPException(status_code=404, detail="Secondary chunk not found")

    primary.content = f"{primary.content}\n{secondary.content}"
    db.delete(secondary)
    db.commit()
    db.refresh(primary)
    return _serialize_chunk(primary)


@router.post("/tailorings/{tailoring_id}/chunks/rename-group")
def rename_group(
    tailoring_id: str,
    body: RenameGroupRequest,
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

    updated = (
        db.query(JobChunk)
        .filter(JobChunk.job_id == tailoring.job_id, JobChunk.section == body.old_section)
        .update({"section": body.new_section})
    )
    db.commit()
    return {"updated": updated, "new_section": body.new_section}


@router.post("/tailorings/{tailoring_id}/refresh")
def refresh_tailoring_chunks(
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

    experience = db.query(Experience).filter(Experience.user_id == user.id).first()
    if not experience:
        raise HTTPException(status_code=422, detail="No experience found")

    preferred = " ".join(
        filter(None, [user.preferred_first_name, user.preferred_last_name])
    ).strip()
    candidate_name = preferred or user.name or user.email

    tailoring.enrichment_status = "pending"
    db.commit()

    from app.services.chunk_matcher import refresh_job_chunks

    background_tasks.add_task(
        refresh_job_chunks,
        tailoring.job_id,
        tailoring_id,
        experience.extracted_profile or {},
        user.pronouns,
        experience.id,
        candidate_name,
    )

    return {"status": "refreshing"}


class GapAnswerRequest(BaseModel):
    gap_index: int
    answer: str


@router.post("/tailorings/{tailoring_id}/gap-answer")
def submit_gap_answer(
    tailoring_id: str,
    body: GapAnswerRequest,
    background_tasks: BackgroundTasks,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    """
    Accept an answer to a gap question.
    Appends the answer to experience.user_input_text, then re-scores only the
    specific JobChunk linked to that gap — the full tailoring is not regenerated.
    """
    tailoring = (
        db.query(Tailoring)
        .filter(Tailoring.id == tailoring_id, Tailoring.user_id == user.id)
        .first()
    )
    if not tailoring:
        raise HTTPException(status_code=404, detail="Tailoring not found")

    gap_analysis = tailoring.gap_analysis
    if not gap_analysis or not gap_analysis.get("gaps"):
        raise HTTPException(status_code=404, detail="No gap analysis found for this tailoring")

    gaps = gap_analysis["gaps"]
    if body.gap_index < 0 or body.gap_index >= len(gaps):
        raise HTTPException(
            status_code=422,
            detail=f"gap_index {body.gap_index} is out of range (0–{len(gaps) - 1})",
        )

    gap = gaps[body.gap_index]
    chunk_id: str | None = gap.get("chunk_id")

    # Load the user's experience record
    experience = db.query(Experience).filter(Experience.user_id == user.id).first()
    if not experience:
        raise HTTPException(status_code=404, detail="Experience not found")

    # Append the answer to user_input_text with a labeled prefix so it reads clearly
    # in the profile formatter and is distinguishable from freeform notes.
    requirement_label = gap.get("job_requirement", "")[:60]
    answer_entry = f"[Gap answer — {requirement_label}]: {body.answer.strip()}"
    existing = experience.user_input_text or ""
    new_user_input_text = (existing + "\n\n" + answer_entry).strip()
    experience.user_input_text = new_user_input_text

    # Keep extracted_profile["user_input"] in sync with user_input_text so the
    # profile formatter always renders the latest direct-input text.
    base_profile = experience.extracted_profile or {}
    updated_profile = {**base_profile, "user_input": {"text": new_user_input_text}}
    experience.extracted_profile = updated_profile
    db.commit()

    # Re-score the specific chunk in the background using the updated profile.
    # If chunk_id is None (no match found during gap analysis), skip re-enrichment.
    chunk_reenrichment_queued = False
    if chunk_id:
        preferred = " ".join(
            filter(None, [user.preferred_first_name, user.preferred_last_name])
        ).strip()
        gap_candidate_name = preferred or user.name or user.email
        background_tasks.add_task(
            re_enrich_single_chunk,
            chunk_id,
            updated_profile,
            user.pronouns,
            experience.id,
            gap_candidate_name,
        )
        chunk_reenrichment_queued = True

    return {
        "status": "saved",
        "chunk_reenrichment_queued": chunk_reenrichment_queued,
    }


@router.post("/tailorings/{tailoring_id}/chunks/{chunk_id}/rescore")
def rescore_chunk(
    tailoring_id: str,
    chunk_id: str,
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

    chunk = (
        db.query(JobChunk)
        .filter(JobChunk.id == chunk_id, JobChunk.job_id == tailoring.job_id)
        .first()
    )
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")

    experience = db.query(Experience).filter(Experience.user_id == user.id).first()
    if not experience:
        raise HTTPException(status_code=422, detail="No experience found")

    preferred = " ".join(
        filter(None, [user.preferred_first_name, user.preferred_last_name])
    ).strip()
    candidate_name = preferred or user.name or user.email

    re_enrich_single_chunk(
        str(chunk.id),
        experience.extracted_profile or {},
        user.pronouns,
        experience.id,
        candidate_name,
    )

    # re_enrich_single_chunk commits via its own session — re-query for fresh data
    db.expire(chunk)
    db.refresh(chunk)

    return {
        "id": str(chunk.id),
        "match_score": chunk.match_score,
        "match_rationale": chunk.match_rationale,
        "advocacy_blurb": chunk.advocacy_blurb,
        "experience_source": chunk.experience_source,
        "experience_sources": chunk.experience_sources or [],
        "source_label": SOURCE_LABELS.get(chunk.experience_source)
        if chunk.experience_source
        else None,
    }


@router.get("/tailorings/{tailoring_id}/debug-info")
def get_tailoring_debug_info(
    tailoring_id: str,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    from app.prompts import chunk_matching as chunk_prompt
    from app.prompts import tailoring as tailoring_prompt

    tailoring = (
        db.query(Tailoring)
        .filter(Tailoring.id == tailoring_id, Tailoring.user_id == user.id)
        .first()
    )
    if not tailoring:
        raise HTTPException(status_code=404, detail="Tailoring not found")

    if tailoring.profile_snapshot is not None:
        formatted_profile = tailoring.profile_snapshot
        profile_snapshot_source = "snapshot"
    else:
        experience = db.query(Experience).filter(Experience.user_id == user.id).first()
        extracted_profile = (experience.extracted_profile if experience else None) or {}
        formatted_profile = _format_sourced_profile(
            extracted_profile,
            candidate_name=user.name,
            pronouns=user.pronouns if hasattr(user, "pronouns") else None,
        )
        profile_snapshot_source = "reconstructed"

    # Build a sample chunk-matching user message.
    # Mode is detected from stored rationale prefix so historical tailorings
    # reflect the mode that actually ran, regardless of current settings.
    chunks = (
        db.query(JobChunk)
        .filter(JobChunk.job_id == tailoring.job_id)
        .order_by(JobChunk.position)
        .all()
    )
    scored_chunks = [c for c in chunks if c.chunk_type != "header" and c.match_score is not None]
    if tailoring.matching_mode is not None:
        used_vector = tailoring.matching_mode == "vector"
    else:
        # Historical tailoring — infer from rationale prefix (pre-migration data only)
        used_vector = any(
            c.match_rationale and c.match_rationale.startswith("[vector") for c in scored_chunks
        )

    if used_vector and scored_chunks:
        from app.services.chunk_matcher import _build_candidate_header

        first = scored_chunks[0]
        # Extract candidate_name from profile_snapshot or user record
        _cname = (
            " ".join(filter(None, [user.preferred_first_name, user.preferred_last_name])).strip()
            or user.name
            or user.email
        )
        candidate_header = _build_candidate_header(
            _cname, user.pronouns if hasattr(user, "pronouns") else None
        )
        sample_user_message = chunk_prompt.USER_TEMPLATE_VECTOR.format(
            candidate_header=candidate_header,
            job_requirement=f"[{first.chunk_type.upper()}] {first.content}",
            grouped_context=(
                "(top-8 ExperienceChunks retrieved by cosine similarity at scoring time —\n"
                " content varies per job chunk; not stored)"
            ),
            k=settings.vector_top_k,
        )
        matching_mode = "vector"
    elif chunks:
        batch = chunks[:3]
        sample_chunks_block = "\n".join(
            f"{i}. [{c.chunk_type.upper()}] {c.content}" for i, c in enumerate(batch, start=1)
        )
        first_section = batch[0].section or "General"
        sample_user_message = chunk_prompt.USER_TEMPLATE.format(
            extracted_profile=formatted_profile,
            section=first_section,
            chunks_block=sample_chunks_block,
        )
        matching_mode = "llm"
    else:
        sample_user_message = "(No chunks available)"
        matching_mode = settings.matching_mode

    from app.prompts import gap_analysis as gap_prompt
    from app.prompts import job_extraction as prompt_job_extraction
    from app.prompts import requirement_matching as prompt_req_matching

    return {
        "model": tailoring.model or settings.llm_model,
        "generation_duration_ms": tailoring.generation_duration_ms,
        "chunk_batch_count": tailoring.chunk_batch_count,
        "chunk_error_count": tailoring.chunk_error_count,
        "formatted_profile": formatted_profile,
        "profile_snapshot_source": profile_snapshot_source,
        "matching_mode": matching_mode,
        "job_extraction_system_prompt": prompt_job_extraction.SYSTEM,
        "requirement_matching_system_prompt": prompt_req_matching.SYSTEM,
        "chunk_matching_system_prompt": chunk_prompt.SYSTEM,
        "sample_chunk_user_message": sample_user_message,
        "tailoring_system_prompt": tailoring_prompt.SYSTEM
        if hasattr(tailoring_prompt, "SYSTEM")
        else None,
        "gap_analysis": tailoring.gap_analysis,
        "gap_analysis_system_prompt": gap_prompt.SYSTEM,
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
            " ".join(
                p for p in [author.preferred_first_name, author.preferred_last_name] if p
            ).strip()
            or author.name
        )
        if author
        else None,
    }

    if author:
        exp = db.query(Experience).filter(Experience.user_id == author.id).first()
        has_resume = bool(exp and exp.s3_key)
        github_repos_with_url = []
        if exp and exp.github_repo_details and isinstance(exp.github_repo_details, dict):
            for r in exp.github_repo_details.get("repos") or []:
                if r.get("url"):
                    github_repos_with_url.append({"name": r.get("name"), "url": r.get("url")})
        response["sources"] = {
            "has_resume": has_resume,
            "github_repos": github_repos_with_url,
        }
        resume_data = (exp.extracted_profile or {}).get("resume") or {} if exp else {}
        response["author_title"] = resume_data.get("title") or None
        response["author_email"] = resume_data.get("email") or None
        response["author_linkedin"] = resume_data.get("linkedin") or None
        response["author_profile_public"] = bool(author.profile_public)

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
        .options(joinedload(Tailoring.job))
        .filter(Tailoring.user_id == user.id)
        .order_by(Tailoring.created_at.desc())
        .all()
    )

    trigger_count = _get_tailoring_trigger_count(user.id, db)
    rate_limit_warning = (
        {"triggers_used": trigger_count, "limit": _TAILORING_HOURLY_LIMIT}
        if trigger_count >= _TAILORING_WARN_THRESHOLD
        else None
    )

    return {
        "tailorings": [
            {
                "id": str(t.id),
                "title": t.job.extracted_job.get("title")
                if t.job and t.job.extracted_job
                else None,
                "company": t.job.extracted_job.get("company")
                if t.job and t.job.extracted_job
                else None,
                "job_url": t.job.job_url if t.job else None,
                "generation_status": t.generation_status,
                "letter_public": t.letter_public,
                "posting_public": t.posting_public,
                "is_public": t.is_public,
                "public_slug": t.public_slug,
                "created_at": t.created_at.isoformat(),
            }
            for t in tailorings
        ],
        "rate_limit_warning": rate_limit_warning,
    }
