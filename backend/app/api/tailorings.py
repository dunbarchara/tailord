import json
import random
import re
import secrets
import string
import time
import uuid
from collections.abc import AsyncGenerator
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException
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
from app.core.playwright_helper import get_html_content, get_rendered_content
from app.core.token_utils import truncate_to_tokens
from app.core.url_validation import validate_job_url
from app.models.database import (
    ExperienceClaim,
    Job,
    JobChunk,
    LlmUsageLog,
    Tailoring,
    TailoringDebugLog,
    User,
)
from app.schemas.tailoring_schemas import TailoringCreate
from app.services.chunk_display import SOURCE_LABELS, is_display_ready
from app.services.chunk_matcher import enrich_job_chunks, re_enrich_single_chunk, refresh_job_chunks
from app.services.gap_analyzer import run_gap_analysis
from app.services.job_extractor import extract_job
from app.services.letter_generator import generate_letter
from app.services.profile_formatter import (
    build_ranked_matches_from_chunks,
    format_sourced_profile,
    sources_to_profile_dict,
)

router = APIRouter()
logger = structlog.get_logger(__name__)

# Combined limit: tailoring creates + regens share one pool per user per hour.
# Each trigger costs ~4 LLM calls (job extraction, req matching, generation, chunk scoring).
_TAILORING_HOURLY_LIMIT = 10
_TAILORING_WARN_THRESHOLD = 8
_GENERATION_PHASES_TIMEOUT_SECONDS = 600  # 10 min wall-clock for letter + gap phases


def _get_tailoring_trigger_count(user_id, db: Session) -> int:
    """Return the number of tailoring LLM triggers in the last hour for a user.
    Counts create + regen + letter_regen — all expensive enough to rate-limit.
    Note: letter_regen is excluded from monthly billing quota (see QUOTA_EVENT_TYPES)."""
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    return (
        db.query(LlmUsageLog)
        .filter(
            LlmUsageLog.user_id == user_id,
            LlmUsageLog.event_type.in_(["tailoring_create", "tailoring_regen", "letter_regen"]),
            LlmUsageLog.created_at >= one_hour_ago,
        )
        .count()
    )


def _cleanup_old_trigger_logs(db: Session) -> None:
    """Delete LlmUsageLog rows older than 90 days. 90 days covers 3 billing months
    for dispute resolution and analytics lookback. Amortized on tailoring create/regen."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    db.query(LlmUsageLog).filter(LlmUsageLog.created_at < cutoff).delete()
    db.commit()


def _check_tailoring_rate_limit(user_id, db: Session) -> None:
    """Raise 429 if the user has hit the combined create+regen limit in the last hour."""
    count = _get_tailoring_trigger_count(user_id, db)
    if count >= _TAILORING_HOURLY_LIMIT:
        logger.warning(
            "rate_limit_hit",
            user_id=str(user_id),
            trigger_count=count,
            limit=_TAILORING_HOURLY_LIMIT,
        )
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
    has_github = bool((profile.get("github") or {}).get("repos"))
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
        "experience_sources": c.experience_sources or [],
        "source_label": SOURCE_LABELS.get((c.experience_sources or [None])[0])
        if c.experience_sources
        else None,
        "should_render": c.should_render,
        "include_in_scoring": c.include_in_scoring,
        "semantic_type": c.semantic_type,
        "evaluation_status": c.evaluation_status,
        "display_ready": is_display_ready(c),
        "scored_content": c.scored_content,
        "excluded_reason": c.excluded_reason,
    }


async def _scrape_job_url(url: str) -> tuple[str, str, bool, str]:
    """Fetch a URL and return (html, job_markdown, valid, reason).

    Tries Greenhouse/Lever public APIs first. Falls through to Playwright
    on no ATS match or API failure. Raises HTTPException only on hard
    Playwright failures. Soft validation failures are returned as
    (html, job_markdown, False, reason).
    """
    from app.core.ats_client import try_ats_fetch
    from app.metrics import JOB_SCRAPE_TOTAL

    ats_markdown = try_ats_fetch(url)
    if ats_markdown:
        job_markdown = truncate_to_tokens(ats_markdown, max_tokens=12_000, model=settings.llm_model)
        logger.info("ats_fetch_success", url=url)
        JOB_SCRAPE_TOTAL.labels(method="ats", outcome="success").inc()
        return "", job_markdown, True, ""

    try:
        html, scrape_method = await get_html_content(url)
        job_markdown = extract_markdown_content(html)
        logger.debug(
            "job_content_extracted",
            url=url,
            scrape_method=scrape_method,
            html_len=len(html),
            markdown_len=len(job_markdown),
            markdown_preview=job_markdown[:300],
        )
    except PlaywrightTimeoutError:
        logger.exception("playwright_timeout", url=url)
        JOB_SCRAPE_TOTAL.labels(method="playwright", outcome="timeout").inc()
        raise HTTPException(
            status_code=422,
            detail="That job URL took too long to load. Try again, or check that the URL is publicly accessible.",
        )
    except (PlaywrightError, Exception):
        logger.exception("playwright_scrape_failed", url=url)
        JOB_SCRAPE_TOTAL.labels(method="playwright", outcome="error").inc()
        raise HTTPException(
            status_code=422,
            detail="Couldn't fetch that job posting. The URL may be behind a login or bot protection.",
        )
    # Cap before validation so the validator sees the same text the LLM would.
    job_markdown = truncate_to_tokens(job_markdown, max_tokens=12_000, model=settings.llm_model)
    valid, reason = validate_job_content(job_markdown, html=html)
    if not valid:
        logger.warning("job_content_invalid", url=url, reason=reason, scrape_method=scrape_method)

    # If httpx returned content that looked valid in raw form but stripped down to nothing
    # after extraction (e.g. application-form-heavy ATS pages like apply.careers.microsoft.com),
    # retry with Playwright to get the JS-rendered job description.
    if not valid and scrape_method == "httpx":
        logger.info("scrape_playwright_retry", url=url, reason=reason)
        try:
            html = await get_rendered_content(url)
            job_markdown = extract_markdown_content(html)
            logger.debug(
                "job_content_extracted",
                url=url,
                scrape_method="playwright_retry",
                html_len=len(html),
                markdown_len=len(job_markdown),
                markdown_preview=job_markdown[:300],
            )
            job_markdown = truncate_to_tokens(
                job_markdown, max_tokens=12_000, model=settings.llm_model
            )
            valid, reason = validate_job_content(job_markdown, html=html)
            if not valid:
                logger.warning("job_content_invalid_after_playwright_retry", url=url, reason=reason)
            else:
                scrape_method = "playwright_retry"
        except PlaywrightTimeoutError:
            logger.warning("playwright_retry_timeout", url=url)
        except (PlaywrightError, Exception):
            logger.warning("playwright_retry_failed", url=url, exc_info=True)

    return html, job_markdown, valid, reason or ""


def _write_debug_log(
    tailoring_id, event_type: str, payload: dict, *, user_id: uuid.UUID | None = None
) -> None:
    """
    Write a single TailoringDebugLog row using its own DB session.
    Non-fatal: logs a warning on failure and never raises.
    """
    from app.clients.database import SessionLocal

    try:
        with SessionLocal() as db:
            db.add(
                TailoringDebugLog(
                    tailoring_id=tailoring_id,
                    user_id=user_id,
                    event_type=event_type,
                    payload=payload,
                )
            )
            db.commit()
    except Exception:
        logger.exception(
            "debug_log_write_failed", tailoring_id=str(tailoring_id), event_type=event_type
        )


def _cleanup_old_debug_logs() -> None:
    """Delete tailoring_debug_logs rows older than 90 days. Non-fatal."""
    from app.clients.database import SessionLocal

    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    try:
        with SessionLocal() as db:
            db.query(TailoringDebugLog).filter(TailoringDebugLog.created_at < cutoff).delete()
            db.commit()
    except Exception:
        logger.warning("cleanup_debug_logs_failed")


def _finalize_tailoring(
    tailoring_id: str,
    job_id: str,
    job_markdown: str,
    html: str,
    extracted_profile: dict,
    candidate_name: str,
    job_url: str | None,
    pronouns: str | None = None,
    user_id: uuid.UUID | None = None,
    is_manual: bool = False,
    correlation_id: str = "",
    carrier: dict | None = None,
) -> None:
    """
    Background task: extract the job, enrich chunks, derive ranked matches from chunk
    scores, generate the tailoring letter, then run gap analysis.

    Creates its own DB session (request session is closed by the time this runs).
    Updates generation_stage as each step starts so the frontend can poll progress.
    Stages: extracting → enriching → generating

    When is_manual=True, job extraction is skipped — extracted_job is already
    pre-seeded on the Job record from company/title/description fields.

    carrier: serialized OTel span context from the HTTP handler so this background
    task's root span is parented to the originating HTTP request's trace.
    """
    from app.clients.database import SessionLocal

    # Re-establish the correlation ID and bind tailoring_id to the structlog context
    # so every log record in this background task carries both fields automatically.
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        correlation_id=correlation_id,
        tailoring_id=tailoring_id,
        user_id=str(user_id) if user_id else None,
    )

    # OTel: start a root span for the full background task, parented to the HTTP
    # handler span via the injected carrier dict.
    from opentelemetry import propagate as _otel_propagate

    from app.telemetry import get_tracer as _get_otel_tracer

    _tracer = _get_otel_tracer("tailord.tailoring")
    _parent_ctx = _otel_propagate.extract(carrier or {})

    with _tracer.start_as_current_span(
        "background_task.tailoring.generate",
        context=_parent_ctx,
        attributes={
            "tailoring.id": tailoring_id,
            "tailoring.matching_mode": settings.matching_mode,
        },
    ):
        from app.metrics import (
            TAILORING_ACTIVE_GENERATIONS,
            TAILORING_GENERATION_DURATION_MS,
            TAILORING_GENERATIONS_TOTAL,
            TAILORING_PHASE_DURATION_MS,
        )

        TAILORING_ACTIVE_GENERATIONS.inc()
        _generation_success = False

        overall_start = time.perf_counter()
        phase_durations: dict[str, int] = {}

        logger.info("generation_started", matching_mode=settings.matching_mode)

        # Phase 1: job extraction (extracting stage)
        extracted_job: dict = {}
        db = SessionLocal()
        phase_start = time.perf_counter()
        try:
            with _tracer.start_as_current_span("tailoring.phase.extract_job"):
                tailoring = db.get(Tailoring, tailoring_id)
                if not tailoring:
                    logger.error("tailoring_not_found")
                    TAILORING_ACTIVE_GENERATIONS.dec()
                    TAILORING_GENERATIONS_TOTAL.labels(
                        status="error", matching_mode=settings.matching_mode
                    ).inc()
                    return

                tailoring.generation_started_at = datetime.now(timezone.utc)
                tailoring.generation_stage = "extracting"
                # Snapshot the exact formatted profile passed to the LLM so the debug panel
                # always shows what the model actually saw, regardless of later experience edits.
                tailoring.profile_snapshot = format_sourced_profile(
                    extracted_profile, candidate_name=candidate_name, pronouns=pronouns
                )
                db.commit()

                _write_debug_log(
                    tailoring_id,
                    "generation_started",
                    {
                        "correlation_id": correlation_id,
                        "matching_mode": settings.matching_mode,
                        "llm_model": settings.llm_model,
                        "is_manual": is_manual,
                    },
                    user_id=user_id,
                )

                if is_manual:
                    # Manual path: company/title were pre-seeded; skip LLM extraction.
                    job = db.get(Job, job_id)
                    extracted_job = (job.extracted_job or {}) if job else {}
                else:
                    try:
                        extracted_job = extract_job(job_markdown, html=html)
                    except Exception:
                        logger.exception("phase_error", phase="extract_job")
                        _write_debug_log(
                            tailoring_id,
                            "phase_error",
                            {
                                "phase": "extract_job",
                                "error_message": "Job extraction failed",
                            },
                            user_id=user_id,
                        )
                        tailoring.generation_status = "error"
                        tailoring.generation_stage = None
                        tailoring.generation_error = (
                            "We couldn't extract the job description. Try regenerating."
                        )
                        db.commit()
                        TAILORING_ACTIVE_GENERATIONS.dec()
                        TAILORING_GENERATIONS_TOTAL.labels(
                            status="error", matching_mode=settings.matching_mode
                        ).inc()
                        return

                    job = db.get(Job, job_id)
                    if job:
                        job.extracted_job = extracted_job
                        db.commit()

                phase_durations["extract_job"] = int((time.perf_counter() - phase_start) * 1000)
                TAILORING_PHASE_DURATION_MS.labels(phase="extract_job").observe(
                    phase_durations["extract_job"]
                )
                _write_debug_log(
                    tailoring_id,
                    "phase_complete",
                    {
                        "phase": "extract_job",
                        "duration_ms": phase_durations["extract_job"],
                    },
                    user_id=user_id,
                )
                logger.info(
                    "phase_complete",
                    phase="extract_job",
                    duration_ms=phase_durations["extract_job"],
                )

                tailoring.generation_stage = "filtering"
                db.commit()

        except Exception:
            logger.exception("phase_error", phase="extract_job")
            _write_debug_log(
                tailoring_id,
                "phase_error",
                {
                    "phase": "extract_job",
                    "error_message": "Unexpected error in extraction phase",
                },
                user_id=user_id,
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
            TAILORING_ACTIVE_GENERATIONS.dec()
            TAILORING_GENERATIONS_TOTAL.labels(
                status="error", matching_mode=settings.matching_mode
            ).inc()
            return
        finally:
            db.close()

        # Phase 1.5: detect job content bounds (filtering stage)
        # Runs the bounds-detection LLM call as a named step so it's visible on the generation
        # page. Result is passed to enrich_job_chunks to avoid running the LLM call twice.
        phase_start = time.perf_counter()
        _bounds_error: str | None = None
        with _tracer.start_as_current_span("tailoring.phase.detect_bounds"):
            from app.services.job_bounds_detector import JobContentBounds, detect_job_content_bounds

            try:
                precomputed_bounds = detect_job_content_bounds(job_markdown)
            except Exception as _exc:
                logger.exception("phase_error", phase="detect_bounds")
                precomputed_bounds = JobContentBounds()
                _bounds_error = str(_exc)

        phase_durations["detect_bounds"] = int((time.perf_counter() - phase_start) * 1000)
        TAILORING_PHASE_DURATION_MS.labels(phase="detect_bounds").observe(
            phase_durations["detect_bounds"]
        )
        if _bounds_error:
            _write_debug_log(
                tailoring_id,
                "phase_error",
                {
                    "phase": "detect_bounds",
                    "duration_ms": phase_durations["detect_bounds"],
                    "error_message": _bounds_error,
                },
                user_id=user_id,
            )
        else:
            _write_debug_log(
                tailoring_id,
                "phase_complete",
                {"phase": "detect_bounds", "duration_ms": phase_durations["detect_bounds"]},
                user_id=user_id,
            )

        # Transition to enriching stage now that filtering/bounds detection is done.
        db = SessionLocal()
        try:
            tailoring = db.get(Tailoring, tailoring_id)
            if tailoring:
                tailoring.generation_stage = "enriching"
                db.commit()
        except Exception:
            logger.warning("filtering_stage_transition_failed")
        finally:
            db.close()

        # Phase 2: chunk enrichment (uses its own session)
        phase_start = time.perf_counter()
        enrich_error: str | None = None
        with _tracer.start_as_current_span("tailoring.phase.enrich_job_chunks"):
            try:
                enrich_job_chunks(
                    job_id,
                    job_markdown,
                    extracted_profile,
                    pronouns=pronouns,
                    user_id=user_id,
                    candidate_name=candidate_name,
                    precomputed_bounds=precomputed_bounds,
                )
            except Exception as exc:
                logger.exception("phase_error", phase="enrich_job_chunks")
                enrich_error = str(exc)

            phase_durations["enrich_job_chunks"] = int((time.perf_counter() - phase_start) * 1000)
            TAILORING_PHASE_DURATION_MS.labels(phase="enrich_job_chunks").observe(
                phase_durations["enrich_job_chunks"]
            )
            if enrich_error:
                _write_debug_log(
                    tailoring_id,
                    "phase_error",
                    {
                        "phase": "enrich_job_chunks",
                        "duration_ms": phase_durations["enrich_job_chunks"],
                        "error_message": enrich_error,
                    },
                    user_id=user_id,
                )
                # Enrich failure is fatal — abort; do not deliver partial tailorings.
                db = SessionLocal()
                try:
                    tailoring = db.get(Tailoring, tailoring_id)
                    if tailoring:
                        tailoring.generation_status = "error"
                        tailoring.generation_stage = None
                        tailoring.generation_error = (
                            "Requirement matching failed. Please regenerate."
                        )
                        db.commit()
                except Exception:
                    pass
                finally:
                    db.close()
                TAILORING_ACTIVE_GENERATIONS.dec()
                TAILORING_GENERATIONS_TOTAL.labels(
                    status="error", matching_mode=settings.matching_mode
                ).inc()
                return
            else:
                _write_debug_log(
                    tailoring_id,
                    "phase_complete",
                    {
                        "phase": "enrich_job_chunks",
                        "duration_ms": phase_durations["enrich_job_chunks"],
                    },
                    user_id=user_id,
                )
                logger.info(
                    "phase_complete",
                    phase="enrich_job_chunks",
                    duration_ms=phase_durations["enrich_job_chunks"],
                )

        # Phases 3 & 4 (parallel): generate_advocacy_letter + gap_analysis
        # Set the generating stage before dispatching threads.
        db = SessionLocal()
        try:
            tailoring = db.get(Tailoring, tailoring_id)
            if not tailoring:
                logger.error("tailoring_not_found_after_enrichment")
                TAILORING_ACTIVE_GENERATIONS.dec()
                TAILORING_GENERATIONS_TOTAL.labels(
                    status="error", matching_mode=settings.matching_mode
                ).inc()
                return
            tailoring.generation_stage = "generating"
            db.commit()
        except Exception:
            logger.exception("phase_error", phase="set_generating_stage")
            TAILORING_ACTIVE_GENERATIONS.dec()
            TAILORING_GENERATIONS_TOTAL.labels(
                status="error", matching_mode=settings.matching_mode
            ).inc()
            return
        finally:
            db.close()

        # Capture structlog and OTel contexts for propagation into both threads.
        import opentelemetry.context as _otel_context

        _ctx_vars = structlog.contextvars.get_contextvars()
        _otel_ctx = _otel_context.get_current()

        _letter_result: tuple | None = None
        _letter_failed = False
        _gap_failed = False
        _letter_duration_ms = 0
        _gap_duration_ms = 0

        def _run_letter_phase() -> None:
            nonlocal _letter_result, _letter_failed, _letter_duration_ms
            structlog.contextvars.clear_contextvars()
            structlog.contextvars.bind_contextvars(**_ctx_vars)
            _tok = _otel_context.attach(_otel_ctx)
            _start = time.perf_counter()
            try:
                with _tracer.start_as_current_span("tailoring.phase.generate_advocacy_letter"):
                    # Internal step: read chunk scores → build ranked matches for the letter.
                    # Logged inline; not emitted as a separate phase_complete event.
                    _ranked: list[dict] = []
                    try:
                        with SessionLocal() as _cdb:
                            _ranked = build_ranked_matches_from_chunks(uuid.UUID(job_id), _cdb)
                    except Exception:
                        logger.exception("ranked_matches_failed")

                    try:
                        _letter_result = generate_letter(
                            extracted_profile,
                            extracted_job,
                            candidate_name,
                            ranked_matches=_ranked,
                            job_url=job_url,
                            pronouns=pronouns,
                        )
                    except Exception:
                        logger.exception("phase_error", phase="generate_advocacy_letter")
                        _write_debug_log(
                            tailoring_id,
                            "phase_error",
                            {
                                "phase": "generate_advocacy_letter",
                                "error_message": "Advocacy letter generation failed",
                            },
                            user_id=user_id,
                        )
                        _letter_failed = True
            except Exception:
                _letter_failed = True
            finally:
                _letter_duration_ms = int((time.perf_counter() - _start) * 1000)
                _otel_context.detach(_tok)

        def _run_gap_phase() -> None:
            nonlocal _gap_failed, _gap_duration_ms
            structlog.contextvars.clear_contextvars()
            structlog.contextvars.bind_contextvars(**_ctx_vars)
            _tok = _otel_context.attach(_otel_ctx)
            _start = time.perf_counter()
            try:
                with _tracer.start_as_current_span("tailoring.phase.gap_analysis"):
                    run_gap_analysis(tailoring_id)
            except Exception:
                logger.exception("phase_error", phase="gap_analysis")
                _write_debug_log(
                    tailoring_id,
                    "phase_error",
                    {"phase": "gap_analysis", "error_message": "Gap analysis failed"},
                    user_id=user_id,
                )
                _gap_failed = True
            finally:
                _gap_duration_ms = int((time.perf_counter() - _start) * 1000)
                _otel_context.detach(_tok)

        _phases_executor = ThreadPoolExecutor(max_workers=2)
        _letter_future = _phases_executor.submit(_run_letter_phase)
        _gap_future = _phases_executor.submit(_run_gap_phase)
        _phases_done, _phases_not_done = wait(
            [_letter_future, _gap_future], timeout=_GENERATION_PHASES_TIMEOUT_SECONDS
        )
        _phases_executor.shutdown(
            wait=False
        )  # drain in background (threads exit when HTTP timeout fires)

        for _f in _phases_not_done:
            if _f is _letter_future:
                logger.error(
                    "phase_timeout",
                    phase="generate_advocacy_letter",
                    timeout_s=_GENERATION_PHASES_TIMEOUT_SECONDS,
                )
                _letter_failed = True
            else:
                logger.error(
                    "phase_timeout",
                    phase="gap_analysis",
                    timeout_s=_GENERATION_PHASES_TIMEOUT_SECONDS,
                )
                _gap_failed = True

        phase_durations["generate_advocacy_letter"] = _letter_duration_ms
        phase_durations["gap_analysis"] = _gap_duration_ms
        TAILORING_PHASE_DURATION_MS.labels(phase="generate_advocacy_letter").observe(
            _letter_duration_ms
        )
        TAILORING_PHASE_DURATION_MS.labels(phase="gap_analysis").observe(_gap_duration_ms)

        if _letter_failed:
            # Letter failure is fatal — abort and mark generation as error.
            _write_debug_log(
                tailoring_id,
                "generation_error",
                {
                    "phase": "generate_advocacy_letter",
                    "error_message": "Unexpected error in letter generation phase",
                },
                user_id=user_id,
            )
            db = SessionLocal()
            try:
                tailoring = db.get(Tailoring, tailoring_id)
                if tailoring:
                    tailoring.generation_status = "error"
                    tailoring.generation_stage = None
                    tailoring.generation_error = (
                        "Tailoring generation failed. You can retry by regenerating."
                    )
                    db.commit()
            except Exception:
                pass
            finally:
                db.close()
            TAILORING_ACTIVE_GENERATIONS.dec()
            TAILORING_GENERATIONS_TOTAL.labels(
                status="error", matching_mode=settings.matching_mode
            ).inc()
            return

        if _gap_failed:
            # Gap failure is fatal — abort and mark generation as error.
            _write_debug_log(
                tailoring_id,
                "generation_error",
                {
                    "phase": "gap_analysis",
                    "error_message": "Gap analysis failed or timed out",
                },
                user_id=user_id,
            )
            db = SessionLocal()
            try:
                tailoring = db.get(Tailoring, tailoring_id)
                if tailoring:
                    tailoring.generation_status = "error"
                    tailoring.generation_stage = None
                    tailoring.generation_error = "Gap analysis failed. Please regenerate."
                    db.commit()
            except Exception:
                pass
            finally:
                db.close()
            TAILORING_ACTIVE_GENERATIONS.dec()
            TAILORING_GENERATIONS_TOTAL.labels(
                status="error", matching_mode=settings.matching_mode
            ).inc()
            return

        # Letter succeeded — log phase completions.
        assert _letter_result is not None
        generated_output, letter_content = _letter_result
        _write_debug_log(
            tailoring_id,
            "phase_complete",
            {"phase": "generate_advocacy_letter", "duration_ms": _letter_duration_ms},
            user_id=user_id,
        )
        logger.info(
            "phase_complete",
            phase="generate_advocacy_letter",
            duration_ms=_letter_duration_ms,
        )
        _write_debug_log(
            tailoring_id,
            "phase_complete",
            {"phase": "gap_analysis", "duration_ms": _gap_duration_ms},
            user_id=user_id,
        )
        logger.info(
            "phase_complete",
            phase="gap_analysis",
            duration_ms=_gap_duration_ms,
        )

        # Write letter results and set generation_status = "ready".
        # This fires only after BOTH letter and gap analysis have completed.
        _captured_telemetry: dict = {}
        db = SessionLocal()
        try:
            tailoring = db.get(Tailoring, tailoring_id)
            if not tailoring:
                logger.error("tailoring_not_found_after_parallel_phases")
                TAILORING_ACTIVE_GENERATIONS.dec()
                TAILORING_GENERATIONS_TOTAL.labels(
                    status="error", matching_mode=settings.matching_mode
                ).inc()
                return

            now = datetime.now(timezone.utc)
            tailoring.generated_output = generated_output
            tailoring.letter_content = letter_content
            tailoring.models = {"letter": settings.llm_model}
            tailoring.generation_status = "ready"
            tailoring.generation_stage = None
            tailoring.generated_at = now
            telemetry: dict = {"matching_mode": settings.matching_mode}
            if tailoring.generation_started_at:
                delta_ms = (now - tailoring.generation_started_at).total_seconds() * 1000
                telemetry["duration_ms"] = int(delta_ms)
            if "detect_bounds" in phase_durations:
                telemetry["detect_bounds_ms"] = phase_durations["detect_bounds"]
            tailoring.generation_telemetry = {**(tailoring.generation_telemetry or {}), **telemetry}
            db.commit()
            _generation_success = True
            # Capture final telemetry (includes chunk_matcher's batch_count/batch_errors)
            # before the session closes so we can include it in the generation_complete log.
            _captured_telemetry = tailoring.generation_telemetry or {}
        except Exception:
            logger.exception("phase_error", phase="write_letter_results")
            _write_debug_log(
                tailoring_id,
                "generation_error",
                {
                    "phase": "write_letter_results",
                    "error_message": "Unexpected error writing letter results",
                },
                user_id=user_id,
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
            TAILORING_ACTIVE_GENERATIONS.dec()
            TAILORING_GENERATIONS_TOTAL.labels(
                status="error", matching_mode=settings.matching_mode
            ).inc()
            return
        finally:
            db.close()

        total_duration_ms = int((time.perf_counter() - overall_start) * 1000)
        logger.info(
            "generation_complete",
            total_duration_ms=total_duration_ms,
            phase_durations=phase_durations,
        )
        _write_debug_log(
            tailoring_id,
            "generation_complete",
            {
                "total_duration_ms": total_duration_ms,
                "phase_durations": phase_durations,
                "matching_mode": settings.matching_mode,
                "llm_model": settings.llm_model,
                "batch_count": _captured_telemetry.get("batch_count"),
                "batch_errors": _captured_telemetry.get("batch_errors"),
            },
            user_id=user_id,
        )
        _cleanup_old_debug_logs()
        from app.core.llm_call_logger import cleanup_old_llm_call_logs

        cleanup_old_llm_call_logs()
        TAILORING_ACTIVE_GENERATIONS.dec()
        TAILORING_GENERATIONS_TOTAL.labels(
            status="success" if _generation_success else "error",
            matching_mode=settings.matching_mode,
        ).inc()
        TAILORING_GENERATION_DURATION_MS.observe(total_duration_ms)


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
        # experience_sources is loaded via selectin — no extra query needed.
        extracted_profile = sources_to_profile_dict(user.experience_sources)
        if not extracted_profile:
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
            _validate_profile(extracted_profile)
        except HTTPException as exc:
            yield _sse("error", json.dumps({"detail": exc.detail}))
            return

        # Capture what we need from the session before the long async scrape.
        # db.commit() closes the implicit read transaction so the connection doesn't
        # sit idle-in-transaction for the entire scraping duration (5–15s).
        user_id = user.id
        candidate_name = user.candidate_name
        candidate_pronouns = user.profile.pronouns if user.profile else None
        if existing_tailoring:
            existing_tailoring_id = str(existing_tailoring.id)
            existing_job_id = str(existing_tailoring.job_id)
        db.commit()

        from app.metrics import TAILORING_PHASE_DURATION_MS as _PHASE_DURATION_MS
        from app.telemetry import get_tracer as _get_tracer_handler

        _tracer_handler = _get_tracer_handler("tailord.tailoring")
        pre_phase_start = time.perf_counter()

        with _tracer_handler.start_as_current_span("tailoring.phase.validate_job_posting"):
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
                db.commit()
                job_record = db.get(Job, existing_job_id)
            else:
                job_record = Job(
                    user_id=user.id,
                    job_url=request.job_url or None,
                    raw_description=request.description or None,
                    source_type="manual" if is_manual else "url",
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

            # Serialize the current OTel span context so the background task can parent
            # its root span to this HTTP request's trace.
            from opentelemetry import propagate as _otel_propagate

            _otel_carrier: dict = {}
            _otel_propagate.inject(_otel_carrier)

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
                user_id,
                is_manual,
                structlog.contextvars.get_contextvars().get("correlation_id", ""),
                _otel_carrier,
            )

            _pre_phase_duration_ms = int((time.perf_counter() - pre_phase_start) * 1000)
            _PHASE_DURATION_MS.labels(phase="validate_job_posting").observe(_pre_phase_duration_ms)
            logger.info(
                "phase_complete",
                phase="validate_job_posting",
                duration_ms=_pre_phase_duration_ms,
                tailoring_id=str(tailoring.id),
                is_manual=is_manual,
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


def _compute_base_slug(company: str | None, title: str | None) -> str:
    def slugify(s: str) -> str:
        s = s.lower().strip()
        s = re.sub(r"[^\w\s-]", "", s)
        s = re.sub(r"[\s_-]+", "-", s).strip("-")
        return s[:20]

    parts = [p for p in [slugify(company or ""), slugify(title or "")] if p]
    return "-".join(parts)


def _generate_slug(
    company: str | None,
    title: str | None,
    db: Session | None = None,
    user_id: uuid.UUID | None = None,
) -> str:
    base = _compute_base_slug(company, title)
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    if db is None or user_id is None:
        return f"{base}-{suffix}" if base else suffix
    slug = f"{base}-{suffix}" if base else suffix
    for _ in range(5):
        existing = (
            db.query(Tailoring)
            .filter(Tailoring.user_id == user_id, Tailoring.public_slug == slug)
            .first()
        )
        if not existing:
            return slug
        slug = f"{base}-{secrets.token_urlsafe(4)}"
    return f"{base}-{secrets.token_urlsafe(6)}"


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
            validate_job_url(body.job_url, is_local=settings.environment == "local")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
    _check_tailoring_rate_limit(user.id, db)
    db.add(LlmUsageLog(user_id=user.id, event_type="tailoring_create"))
    db.commit()
    background_tasks.add_task(_cleanup_old_trigger_logs, db)
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
    db.add(LlmUsageLog(user_id=user.id, event_type="tailoring_regen"))
    db.commit()
    background_tasks.add_task(_cleanup_old_trigger_logs, db)

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


def _run_letter_regen(
    tailoring_id: str,
    job_id: str,
    extracted_profile: dict,
    candidate_name: str,
    job_url: str | None,
    pronouns: str | None,
    user_id: uuid.UUID,
) -> None:
    """
    Background task: re-score chunks (in-place) + re-generate letter + re-run gap analysis.
    Used by the regenerate-letter endpoint to upgrade old tailorings without a full regen.

    Creates its own DB sessions — do not pass a session across thread boundaries.
    """
    from app.clients.database import SessionLocal

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(tailoring_id=tailoring_id)
    logger.info("letter_regen_started", tailoring_id=tailoring_id)

    # Phase 1: re-score chunks in-place
    db = SessionLocal()
    try:
        tailoring = db.get(Tailoring, tailoring_id)
        if not tailoring:
            return
        tailoring.generation_stage = "enriching"
        db.commit()
    except Exception:
        logger.exception("letter_regen_stage_update_failed")
        return
    finally:
        db.close()

    try:
        refresh_job_chunks(
            uuid.UUID(job_id),
            tailoring_id,
            extracted_profile,
            pronouns=pronouns,
            user_id=user_id,
            candidate_name=candidate_name,
        )
    except Exception:
        logger.exception("letter_regen_refresh_failed", tailoring_id=tailoring_id)
        db = SessionLocal()
        try:
            tailoring = db.get(Tailoring, tailoring_id)
            if tailoring:
                tailoring.generation_status = "error"
                tailoring.generation_stage = None
                tailoring.generation_error = "Requirement re-scoring failed. Please regenerate."
                db.commit()
        except Exception:
            pass
        finally:
            db.close()
        return

    # Phase 2: build ranked matches + generate letter
    db = SessionLocal()
    try:
        tailoring = db.get(Tailoring, tailoring_id)
        if not tailoring:
            return
        tailoring.generation_stage = "generating"
        db.commit()
        job = db.get(Job, job_id)
        extracted_job = (job.extracted_job or {}) if job else {}
    except Exception:
        logger.exception("letter_regen_stage_update_failed")
        return
    finally:
        db.close()

    ranked: list[dict] = []
    try:
        with SessionLocal() as _cdb:
            ranked = build_ranked_matches_from_chunks(uuid.UUID(job_id), _cdb)
    except Exception:
        logger.exception("letter_regen_ranked_matches_failed")

    try:
        generated_output, letter_content = generate_letter(
            extracted_profile,
            extracted_job,
            candidate_name,
            ranked_matches=ranked,
            job_url=job_url,
            pronouns=pronouns,
        )
    except Exception:
        logger.exception("letter_regen_generate_failed", tailoring_id=tailoring_id)
        db = SessionLocal()
        try:
            tailoring = db.get(Tailoring, tailoring_id)
            if tailoring:
                tailoring.generation_status = "error"
                tailoring.generation_stage = None
                tailoring.generation_error = "Letter generation failed. Please regenerate."
                db.commit()
        except Exception:
            pass
        finally:
            db.close()
        return

    # Phase 3: gap analysis (non-fatal)
    try:
        run_gap_analysis(tailoring_id)
    except Exception:
        logger.exception("letter_regen_gap_analysis_failed", tailoring_id=tailoring_id)

    # Write results
    now = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        tailoring = db.get(Tailoring, tailoring_id)
        if not tailoring:
            return
        tailoring.generated_output = generated_output
        tailoring.letter_content = letter_content
        tailoring.models = {"letter": settings.llm_model}
        tailoring.generation_status = "ready"
        tailoring.generation_stage = None
        tailoring.generated_at = now
        tailoring.profile_snapshot = format_sourced_profile(
            extracted_profile, candidate_name=candidate_name, pronouns=pronouns
        )
        db.commit()
        logger.info("letter_regen_complete", tailoring_id=tailoring_id)
    except Exception:
        logger.exception("letter_regen_write_failed", tailoring_id=tailoring_id)
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


@router.post("/tailorings/{tailoring_id}/regenerate-letter")
async def regenerate_letter(
    tailoring_id: str,
    background_tasks: BackgroundTasks,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    """
    Regenerate only the letter (re-score chunks + letter generation + gap analysis),
    skipping job scraping/extraction. Intended for upgrading old tailorings that have
    generated_output but no letter_content.
    """
    tailoring = (
        db.query(Tailoring)
        .filter(Tailoring.id == tailoring_id, Tailoring.user_id == user.id)
        .first()
    )
    if not tailoring:
        raise HTTPException(status_code=404, detail="Tailoring not found")
    if tailoring.generation_status == "generating":
        raise HTTPException(status_code=409, detail="Tailoring is currently being generated.")

    job = tailoring.job
    if not job or not job.extracted_job:
        raise HTTPException(
            status_code=422, detail="Job data not available for letter regeneration."
        )

    extracted_profile = sources_to_profile_dict(user.experience_sources)
    if not extracted_profile:
        raise HTTPException(status_code=422, detail="No experience found.")

    _check_tailoring_rate_limit(user.id, db)

    tailoring.generation_status = "generating"
    tailoring.generation_stage = "enriching"
    tailoring.generation_error = None
    tailoring.last_regenerated_at = datetime.now(timezone.utc)
    db.add(LlmUsageLog(user_id=user.id, event_type="letter_regen"))
    db.commit()
    background_tasks.add_task(_cleanup_old_trigger_logs, db)

    candidate_name = user.candidate_name
    pronouns = user.profile.pronouns if user.profile else None

    background_tasks.add_task(
        _run_letter_regen,
        str(tailoring.id),
        str(job.id),
        extracted_profile,
        candidate_name,
        job.job_url,
        pronouns,
        user.id,
    )

    async def _sse_ready() -> AsyncGenerator[str, None]:
        yield _sse("ready", json.dumps({"id": tailoring_id}))

    return StreamingResponse(
        _sse_ready(),
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


@router.post("/tailorings/{tailoring_id}/retry-gap-analysis")
def retry_gap_analysis(
    tailoring_id: str,
    background_tasks: BackgroundTasks,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    """Reset gap_analysis_status to pending and re-run gap analysis in the background."""
    tailoring = (
        db.query(Tailoring)
        .filter(Tailoring.id == tailoring_id, Tailoring.user_id == user.id)
        .first()
    )
    if not tailoring:
        raise HTTPException(status_code=404, detail="Tailoring not found")
    if tailoring.generation_status != "ready":
        raise HTTPException(
            status_code=409,
            detail="Gap analysis can only be retried after generation completes.",
        )
    tailoring.gap_analysis = None  # Reset so frontend polls again
    db.commit()
    background_tasks.add_task(run_gap_analysis, tailoring_id)
    job = tailoring.job
    return {
        "id": str(tailoring.id),
        "generation_status": tailoring.generation_status,
        "title": job.extracted_job.get("title") if job and job.extracted_job else None,
        "company": job.extracted_job.get("company") if job and job.extracted_job else None,
    }


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

    # Lazy recovery: surface silent background-task deaths as errors.
    if tailoring.generation_status == "generating" and tailoring.generation_started_at is not None:
        stale_cutoff = datetime.now(timezone.utc) - timedelta(
            minutes=settings.generation_stale_threshold_minutes
        )
        if tailoring.generation_started_at < stale_cutoff:
            logger.warning(
                "stale_generation_detected",
                tailoring_id=tailoring_id,
                generation_started_at=tailoring.generation_started_at.isoformat(),
                threshold_minutes=settings.generation_stale_threshold_minutes,
            )
            tailoring.generation_status = "error"
            tailoring.generation_stage = None
            tailoring.generation_error = "Generation timed out. Please regenerate."
            db.commit()

    job = tailoring.job
    resume_data: dict = {}
    for src in user.experience_sources:
        if src.source_type == "resume" and src.source_data:
            resume_data = src.source_data.get("extracted") or {}
            break

    # Filter stale gap_analysis chunk refs (chunks may have been deleted on regen)
    if tailoring.gap_analysis and isinstance(tailoring.gap_analysis, dict):
        valid_chunk_ids = {
            str(row.id)
            for row in db.query(JobChunk.id).filter(JobChunk.job_id == tailoring.job_id).all()
        }
        ga = tailoring.gap_analysis
        gap_analysis: dict | list | None = {
            **ga,
            "gaps": [g for g in (ga.get("gaps") or []) if g.get("chunk_id") in valid_chunk_ids],
            "partials": [
                g for g in (ga.get("partials") or []) if g.get("chunk_id") in valid_chunk_ids
            ],
        }
    else:
        gap_analysis = tailoring.gap_analysis

    notion = tailoring.notion_export or {}
    return {
        "id": str(tailoring.id),
        "title": job.extracted_job.get("title") if job.extracted_job else None,
        "company": job.extracted_job.get("company") if job.extracted_job else None,
        "job_url": job.job_url if job else None,
        "generated_output": tailoring.generated_output,
        "letter_content": tailoring.letter_content,
        "author_email": resume_data.get("email") or None,
        "author_title": resume_data.get("title") or None,
        "author_linkedin": resume_data.get("linkedin") or None,
        "models": tailoring.models,
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
        "author_username_slug": (
            tailoring.user.profile.username_slug
            if tailoring.user and tailoring.user.profile
            else None
        ),
        "notion_page_url": notion.get("page_url"),
        "notion_posting_page_url": notion.get("posting_page_url"),
        "gap_analysis": gap_analysis,
        "resume_draft": tailoring.resume_draft,
        "updated_at": tailoring.updated_at.isoformat() if tailoring.updated_at else None,
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

    # Derive enrichment_status from chunk data (column removed from tailorings table)
    enrichment_status = "complete" if chunks else "pending"
    return {
        "enrichment_status": enrichment_status,
        "chunks": [_serialize_chunk(c) for c in chunks],
    }


class TailoringJobUpdate(BaseModel):
    title: str | None = None
    company: str | None = None


@router.patch("/tailorings/{tailoring_id}")
def update_tailoring_job(
    tailoring_id: str,
    body: TailoringJobUpdate,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    """Patch the job's extracted title and/or company for a tailoring.

    Only fields included in the request body are updated. Updates the Job row's
    extracted_job JSON directly so all surfaces that read from it reflect the change
    immediately (header, dashboard card, public page) without regeneration.
    """
    tailoring = (
        db.query(Tailoring)
        .filter(Tailoring.id == tailoring_id, Tailoring.user_id == user.id)
        .first()
    )
    if not tailoring:
        raise HTTPException(status_code=404, detail="Tailoring not found")

    job = tailoring.job
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    updates = body.model_dump(exclude_unset=True)
    if updates:
        extracted = dict(job.extracted_job or {})
        extracted.update(updates)
        job.extracted_job = extracted
        db.commit()

    extracted_job = job.extracted_job or {}
    return {
        "title": extracted_job.get("title"),
        "company": extracted_job.get("company"),
    }


class PatchChunkRequest(BaseModel):
    content: str | None = None
    should_render: bool | None = None
    include_in_scoring: bool | None = None
    section: str | None = None
    position: int | None = None
    chunk_type: str | None = None  # "bullet" | "paragraph" (header not user-editable)
    excluded_reason: str | None = None  # present in payload = set/clear; absent = don't touch


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


class RescoreRequest(BaseModel):
    force_score: bool = False


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
    if body.include_in_scoring is not None:
        chunk.include_in_scoring = body.include_in_scoring
    if body.section is not None:
        chunk.section = body.section
    if body.position is not None:
        chunk.position = body.position
    if body.chunk_type is not None and body.chunk_type in ("bullet", "paragraph"):
        chunk.chunk_type = body.chunk_type
    if "excluded_reason" in body.model_fields_set:
        chunk.excluded_reason = body.excluded_reason
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
        include_in_scoring=True,
        evaluation_status=None,
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

    extracted_profile = sources_to_profile_dict(user.experience_sources)
    if not extracted_profile:
        raise HTTPException(status_code=422, detail="No experience found")

    candidate_name = user.candidate_name

    db.commit()

    from app.services.chunk_matcher import refresh_job_chunks as _refresh_job_chunks

    background_tasks.add_task(
        _refresh_job_chunks,
        tailoring.job_id,
        tailoring_id,
        extracted_profile,
        user.profile.pronouns if user.profile else None,
        user.id,
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
    Persists the answer as a gap_response ExperienceClaim, then re-scores only the
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

    # Persist the answer as a gap_response ExperienceClaim.
    # TODO: pass answer through a claim normalisation LLM step before storing.
    # Users often phrase gap answers as conversational replies ("Yes, I did X at Y") rather
    # than claim-speak ("Did X at Y"). A normalisation pass would rewrite all claims into
    # first-person declarative form ("Led X at Y") — improving embedding quality and LLM
    # context. This applies to gap_response, partial_response, and user_input source types.
    # See planning/33-sprint-plan-20260527.md Day 5 notes.
    requirement_label = gap.get("job_requirement", "")[:60]
    answer_entry = f"[Gap answer — {requirement_label}]: {body.answer.strip()}"
    now = datetime.now(timezone.utc)
    from sqlalchemy import func as _func

    max_pos = (
        db.query(_func.max(ExperienceClaim.position))
        .filter(ExperienceClaim.user_id == user.id)
        .scalar()
    )
    next_pos = (max_pos if max_pos is not None else -1) + 1
    gap_claim = ExperienceClaim(
        user_id=user.id,
        source_type="gap_response",
        source_ref=None,
        claim_type="other",
        content=answer_entry,
        group_key=None,
        date_range=None,
        keywords=None,
        provenance_metadata={"job_chunk_id": chunk_id, "tailoring_id": tailoring_id}
        if chunk_id
        else None,
        position=next_pos,
        created_at=now,
        updated_at=now,
    )
    db.add(gap_claim)
    db.commit()

    # Build profile for re-scoring using all experience sources
    updated_profile = sources_to_profile_dict(user.experience_sources)

    # Re-score the specific chunk in the background using the updated profile.
    chunk_reenrichment_queued = False
    if chunk_id:
        gap_candidate_name = user.candidate_name
        background_tasks.add_task(
            re_enrich_single_chunk,
            chunk_id,
            updated_profile,
            user.profile.pronouns if user.profile else None,
            user.id,
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
    body: RescoreRequest = Body(default=RescoreRequest()),
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

    extracted_profile = sources_to_profile_dict(user.experience_sources)
    if not extracted_profile:
        raise HTTPException(status_code=422, detail="No experience found")

    candidate_name = user.candidate_name

    # Promote to scoreable and clear bounds-detection exclusion if present.
    changed = False
    if not chunk.include_in_scoring:
        chunk.include_in_scoring = True
        changed = True
    if chunk.excluded_reason is not None:
        chunk.excluded_reason = None
        chunk.should_render = True
        changed = True
    if changed:
        db.commit()

    re_enrich_single_chunk(
        str(chunk.id),
        extracted_profile,
        user.profile.pronouns if user.profile else None,
        user.id,
        candidate_name,
        force_score=body.force_score,
    )

    # re_enrich_single_chunk commits via its own session — re-query for fresh data
    db.expire(chunk)
    db.refresh(chunk)

    return {
        "id": str(chunk.id),
        "match_score": chunk.match_score,
        "match_rationale": chunk.match_rationale,
        "advocacy_blurb": chunk.advocacy_blurb,
        "experience_sources": chunk.experience_sources or [],
        "source_label": SOURCE_LABELS.get((chunk.experience_sources or [None])[0])
        if chunk.experience_sources
        else None,
        "include_in_scoring": chunk.include_in_scoring,
        "semantic_type": chunk.semantic_type,
        "evaluation_status": chunk.evaluation_status,
        "should_render": chunk.should_render,
        "display_ready": is_display_ready(chunk),
        "excluded_reason": chunk.excluded_reason,
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
        extracted_profile = sources_to_profile_dict(user.experience_sources)
        formatted_profile = format_sourced_profile(
            extracted_profile,
            candidate_name=user.name,
            pronouns=user.profile.pronouns if user.profile else None,
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
    _telemetry = tailoring.generation_telemetry or {}
    _stored_mode = _telemetry.get("matching_mode")
    if _stored_mode is not None:
        used_vector = _stored_mode == "vector"
    else:
        # Historical tailoring — infer from rationale prefix (pre-migration data only)
        used_vector = any(
            c.match_rationale and c.match_rationale.startswith("[vector") for c in scored_chunks
        )

    if used_vector and scored_chunks:
        from app.services.chunk_matcher import _build_candidate_header

        first = scored_chunks[0]
        # Extract candidate_name from profile_snapshot or user record
        _cname = user.candidate_name
        candidate_header = _build_candidate_header(
            _cname, user.profile.pronouns if user.profile else None
        )
        sample_user_message = chunk_prompt.format_user_template_vector(
            candidate_header=candidate_header,
            job_requirement=f"[{first.chunk_type.upper()}] {first.content}",
            grouped_context=(
                "(top-8 ExperienceClaims retrieved by cosine similarity at scoring time —\n"
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
        sample_user_message = chunk_prompt.format_user_template(
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

    _debug_telemetry = tailoring.generation_telemetry or {}
    return {
        "model": (tailoring.models or {}).get("letter") or settings.llm_model,
        "generation_duration_ms": _debug_telemetry.get("duration_ms"),
        "detect_bounds_ms": _debug_telemetry.get("detect_bounds_ms"),
        "chunk_batch_count": _debug_telemetry.get("batch_count"),
        "chunk_error_count": _debug_telemetry.get("batch_errors"),
        "formatted_profile": formatted_profile,
        "profile_snapshot_source": profile_snapshot_source,
        "matching_mode": matching_mode,
        "job_extraction_system_prompt": prompt_job_extraction.SYSTEM,
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
        tailoring.public_slug = _generate_slug(company, title, db, user.id)

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
    from app.models.database import UserProfile

    author_profile = (
        db.query(UserProfile).filter(UserProfile.username_slug == username_slug).first()
    )
    if not author_profile:
        raise HTTPException(status_code=404, detail="Tailoring not found")
    author = author_profile.user

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
        "letter_content": tailoring.letter_content,
        "letter_public": tailoring.letter_public,
        "posting_public": tailoring.posting_public,
        "created_at": tailoring.created_at.isoformat(),
        "author_slug": author.profile.username_slug if author and author.profile else None,
        "author_name": (
            " ".join(
                p
                for p in [author.profile.preferred_first_name, author.profile.preferred_last_name]
                if p
            ).strip()
            or author.name
            if author and author.profile
            else author.name
            if author
            else None
        ),
    }

    if author:
        has_resume = False
        github_repos_with_url = []
        resume_data: dict = {}
        for src in author.experience_sources:
            if src.source_type == "resume":
                has_resume = bool((src.config or {}).get("storage_key"))
                resume_data = (src.source_data or {}).get("extracted") or {}
            elif src.source_type == "github":
                repo_details = (src.source_data or {}).get("repo_details") or {}
                for r in repo_details.values():
                    if r.get("url"):
                        github_repos_with_url.append({"name": r.get("name"), "url": r.get("url")})
        response["sources"] = {
            "has_resume": has_resume,
            "github_repos": github_repos_with_url,
        }
        response["author_title"] = resume_data.get("title") or None
        response["author_email"] = resume_data.get("email") or None
        response["author_linkedin"] = resume_data.get("linkedin") or None
        response["author_profile_public"] = bool(
            author.profile.profile_public if author.profile else False
        )

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
