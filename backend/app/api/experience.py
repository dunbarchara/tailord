import json
import re
import time as _time
import uuid
from datetime import datetime, timedelta, timezone

import anyio
import structlog
import structlog.contextvars
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator, model_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.clients.llm_client import get_llm_client
from app.clients.storage_client import get_storage_client
from app.config import settings
from app.core.deps_database import get_db
from app.core.deps_user import require_approved_user
from app.core.llm_utils import llm_parse_with_retry
from app.metrics import (
    EXPERIENCE_PHASE_DURATION_MS,
    EXPERIENCE_PROCESSING_DURATION_MS,
    EXPERIENCE_PROCESSING_TOTAL,
    GAP_RESPONSE_DURATION_MS,
)
from app.models.database import (
    ExperienceClaim,
    ExperienceGroup,
    ExperienceSource,
    Job,
    JobChunk,
    LlmUsageLog,
    Tailoring,
    User,
)
from app.prompts import user_input_parse as parse_prompt
from app.schemas.llm_outputs import ParsedClaims
from app.services.chunk_matcher import re_enrich_single_chunk
from app.services.experience_chunker import (
    chunk_resume,
    delete_github_chunks,
    delete_github_groups,
    delete_resume_chunks,
    delete_resume_groups,
    delete_user_input_chunks,
    normalize_claim_text,
)
from app.services.experience_embedder import (
    embed_experience_chunks,
    embed_experience_chunks_task,
    re_embed_chunk,
)
from app.services.experience_processor import (
    _friendly_processing_error,
    _normalize_resume_text,
    extract_text,
)
from app.services.gap_analyzer import _build_job_context, _generate_question
from app.services.profile_extractor import extract_profile
from app.services.profile_formatter import format_sourced_profile, sources_to_profile_dict
from app.telemetry import get_tracer as _get_tracer

router = APIRouter()
logger = structlog.get_logger(__name__)
_exp_tracer = _get_tracer("tailord.experience")

ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "txt"}

# Minimum gap between experience processing triggers per user.
_EXPERIENCE_PROCESS_COOLDOWN_MINUTES = 5


def _cleanup_old_usage_logs(db: Session) -> None:
    """Delete LlmUsageLog rows older than 90 days. Amortized on experience processing."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    db.query(LlmUsageLog).filter(LlmUsageLog.created_at < cutoff).delete()
    db.commit()


# Resumes are typically < 500 KB. 10 MB is a generous ceiling that still
# blocks accidental or malicious oversized uploads before text extraction.
_MAX_RESUME_BYTES = 10 * 1024 * 1024  # 10 MB


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------


def _source_status(src: ExperienceSource) -> str:
    """Derive a legacy status string from an ExperienceSource."""
    if src.sync_status == "syncing":
        return "processing"
    if src.sync_status == "error" or src.connection_status == "error":
        return "error"
    if src.connection_status == "connected":
        return "ready"
    return "pending"


def _experience_response(sources: list) -> dict:
    """Build the experience API response from a list of ExperienceSource rows.

    Returns both the new `sources` array (for updated frontends) and the
    legacy flat fields (for backward compat with existing frontend code).
    """
    resume_src = next((s for s in sources if s.source_type == "resume"), None)
    github_src = next((s for s in sources if s.source_type == "github"), None)

    resume_data = (resume_src.source_data or {}) if resume_src else {}
    resume_cfg = (resume_src.config or {}) if resume_src else {}
    github_data = (github_src.source_data or {}) if github_src else {}
    github_cfg = (github_src.config or {}) if github_src else {}

    # Derive legacy status: resume takes precedence over github
    if resume_src:
        status = _source_status(resume_src)
    elif github_src:
        status = _source_status(github_src)
    else:
        status = "pending"

    # Assemble legacy extracted_profile shape from source_data
    extracted_profile: dict = {}
    if resume_data.get("extracted"):
        extracted_profile["resume"] = resume_data["extracted"]
    if resume_data.get("corrections"):
        extracted_profile["corrections"] = resume_data["corrections"]
    if github_data.get("repos"):
        extracted_profile["github"] = {
            **(github_data.get("extracted") or {}),
            "repos": github_data["repos"],
        }

    # New per-source status array
    sources_list = []
    if resume_src:
        sources_list.append(
            {
                "id": str(resume_src.id),
                "source_type": "resume",
                "connection_status": resume_src.connection_status,
                "sync_status": resume_src.sync_status,
                "config": {"filename": resume_cfg.get("filename")},
                "error_message": resume_src.error_message,
                "last_synced_at": resume_src.last_synced_at.isoformat()
                if resume_src.last_synced_at
                else None,
            }
        )
    if github_src:
        sources_list.append(
            {
                "id": str(github_src.id),
                "source_type": "github",
                "connection_status": github_src.connection_status,
                "sync_status": github_src.sync_status,
                "config": {"username": github_cfg.get("username")},
                "error_message": github_src.error_message,
                "last_synced_at": github_src.last_synced_at.isoformat()
                if github_src.last_synced_at
                else None,
            }
        )

    primary_id = str(resume_src.id) if resume_src else (str(github_src.id) if github_src else None)

    return {
        # New format
        "sources": sources_list,
        # Legacy format (backward compat)
        "id": primary_id,
        "filename": resume_cfg.get("filename"),
        "status": status,
        "extracted_profile": extracted_profile or None,
        "raw_resume_text": resume_data.get("raw_text"),
        "error_message": resume_src.error_message if resume_src else None,
        "github_username": github_cfg.get("username"),
        "github_repos": github_data.get("repos"),
        "github_repo_details": github_data.get("repo_details"),
        "user_input_text": None,  # dropped — claims are the source of truth
        "uploaded_at": resume_src.created_at.isoformat() if resume_src else None,
        "processed_at": resume_src.last_synced_at.isoformat()
        if (resume_src and resume_src.last_synced_at)
        else None,
        "last_process_requested_at": resume_src.last_requested_at.isoformat()
        if (resume_src and resume_src.last_requested_at)
        else None,
    }


def _all_sources(user: User, db: Session) -> list:
    """Load all ExperienceSource rows for the user."""
    return db.query(ExperienceSource).filter(ExperienceSource.user_id == user.id).all()


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class UploadUrlRequest(BaseModel):
    filename: str


class ProcessRequest(BaseModel):
    storage_key: str
    experience_id: str
    destructive: bool = False  # True = delete existing resume claims before inserting new ones


class GitHubRequest(BaseModel):
    github_username: str
    selected_repo_names: list[str] | None = None
    rescan_repo_names: list[str] | None = None
    enrich_only_repo_names: list[str] | None = None
    cascade_removed_repos: bool = True  # if False, keep claims/groups for de-selected repos


class UserInputRequest(BaseModel):
    text: str


class UserInputChunksRequest(BaseModel):
    chunks: list[str]


class GapResponseRequest(BaseModel):
    job_chunk_id: str
    tailoring_id: str
    question: str = ""
    answer: str
    response_type: str = "gap"  # "gap" | "partial"


class ProfileUpdate(BaseModel):
    title: str | None = None
    headline: str | None = None
    summary: str | None = None
    location: str | None = None
    email: str | None = None
    phone: str | None = None
    linkedin: str | None = None
    work_experience: list | None = None
    skills: dict | None = None
    education: list | None = None
    projects: list | None = None
    certifications: list | None = None
    yoe_override: float | None = None


# ---------------------------------------------------------------------------
# Upload URL
# ---------------------------------------------------------------------------


@router.post("/experience/upload-url")
def get_upload_url(
    body: UploadUrlRequest,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    ext = body.filename.rsplit(".", 1)[-1].lower() if "." in body.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type .{ext} not allowed. Supported: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    resume_src = next((s for s in user.experience_sources if s.source_type == "resume"), None)
    storage_key = f"users/{user.id}/{uuid.uuid4()}.{ext}"

    now = datetime.now(timezone.utc)

    if resume_src:
        # Clean up old storage file
        old_storage_key = (resume_src.config or {}).get("storage_key")
        if old_storage_key:
            try:
                get_storage_client().delete_object(old_storage_key)
            except Exception:
                logger.warning("storage_cleanup_failed", storage_key=old_storage_key)
        # Reset resume source — preserve corrections across re-uploads
        existing_data = resume_src.source_data or {}
        resume_src.config = {"storage_key": storage_key, "filename": body.filename}
        resume_src.source_data = {
            k: v for k, v in existing_data.items() if k == "corrections"
        } or None
        resume_src.connection_status = "disconnected"
        resume_src.sync_status = "idle"
        resume_src.error_message = None
        resume_src.updated_at = now
    else:
        resume_src = ExperienceSource(
            user_id=user.id,
            source_type="resume",
            connection_status="disconnected",
            sync_status="idle",
            config={"storage_key": storage_key, "filename": body.filename},
            created_at=now,
            updated_at=now,
        )
        db.add(resume_src)

    db.commit()
    db.refresh(resume_src)

    try:
        upload_url = get_storage_client().generate_upload_url(storage_key)
    except Exception as exc:
        logger.exception("generate_upload_url_failed", source_id=str(resume_src.id))
        resume_src.sync_status = "error"
        resume_src.error_message = "Failed to prepare upload. Please try again."
        db.commit()
        raise HTTPException(
            status_code=500, detail="Failed to prepare upload. Please try again."
        ) from exc

    logger.info("upload_url_created", source_id=str(resume_src.id))

    return {
        "upload_url": upload_url,
        "storage_key": storage_key,
        "experience_id": str(resume_src.id),
    }


# ---------------------------------------------------------------------------
# Process (SSE)
# ---------------------------------------------------------------------------


@router.post("/experience/process")
async def trigger_process(
    body: ProcessRequest,
    background_tasks: BackgroundTasks,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    try:
        source_uuid = uuid.UUID(body.experience_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid experience_id")

    resume_src = db.get(ExperienceSource, source_uuid)
    if (
        not resume_src
        or resume_src.user_id != user.id
        or resume_src.source_type != "resume"
        or (resume_src.config or {}).get("storage_key") != body.storage_key
    ):
        raise HTTPException(status_code=404, detail="Experience record not found")

    if resume_src.last_requested_at:
        cooldown_end = resume_src.last_requested_at + timedelta(
            minutes=_EXPERIENCE_PROCESS_COOLDOWN_MINUTES
        )
        if datetime.now(timezone.utc) < cooldown_end:
            remaining = max(
                1, int((cooldown_end - datetime.now(timezone.utc)).total_seconds() / 60) + 1
            )
            logger.warning("experience_process_cooldown", user_id=str(user.id))
            raise HTTPException(
                status_code=429,
                detail=f"Please wait {remaining} minute(s) before re-processing your experience.",
            )

    now = datetime.now(timezone.utc)
    resume_src.last_requested_at = now
    resume_src.sync_status = "syncing"
    resume_src.updated_at = now
    db.add(LlmUsageLog(user_id=user.id, event_type="resume_process"))
    db.commit()
    background_tasks.add_task(_cleanup_old_usage_logs, db)

    storage_key = body.storage_key
    filename = (resume_src.config or {}).get("filename") or "file.txt"

    async def _stream():
        completed = False
        overall_start = _time.perf_counter()
        phase_durations: dict[str, int] = {}
        try:
            # --- extracting ---
            _phase_start = _time.perf_counter()
            yield "event: stage\ndata: extracting\n\n"

            with _exp_tracer.start_as_current_span(
                "experience.phase.extracting",
                attributes={"experience.id": str(resume_src.id)},
            ):
                file_bytes = await anyio.to_thread.run_sync(
                    lambda: get_storage_client().download_bytes(storage_key)
                )

                if len(file_bytes) > _MAX_RESUME_BYTES:
                    mb = len(file_bytes) / 1024 / 1024
                    logger.warning("file_too_large", size_mb=round(mb, 1))
                    resume_src.sync_status = "error"
                    resume_src.connection_status = "error"
                    resume_src.error_message = (
                        f"File is too large ({mb:.1f} MB). Please upload a file under 10 MB."
                    )
                    resume_src.updated_at = datetime.now(timezone.utc)
                    db.commit()
                    yield f"event: error\ndata: {json.dumps({'message': resume_src.error_message})}\n\n"
                    completed = True
                    return

                text = await anyio.to_thread.run_sync(lambda: extract_text(file_bytes, filename))
                normalized = _normalize_resume_text(text)

            phase_durations["extracting"] = int((_time.perf_counter() - _phase_start) * 1000)
            EXPERIENCE_PHASE_DURATION_MS.labels(phase="extracting").observe(
                phase_durations["extracting"]
            )
            logger.info(
                "phase_complete", phase="extracting", duration_ms=phase_durations["extracting"]
            )

            # --- analyzing ---
            _phase_start = _time.perf_counter()
            yield "event: stage\ndata: analyzing\n\n"

            with _exp_tracer.start_as_current_span("experience.phase.analyzing"):
                profile = await anyio.to_thread.run_sync(lambda: extract_profile(normalized))

                # Re-apply any saved corrections to the freshly extracted resume so the user's
                # manual overrides aren't silently discarded when they re-upload.
                existing_data = resume_src.source_data or {}
                corrections = existing_data.get("corrections") or {}
                if corrections:
                    correctable = (
                        "title",
                        "headline",
                        "summary",
                        "location",
                        "email",
                        "phone",
                        "linkedin",
                    )
                    profile = {
                        **profile,
                        **{
                            k: v
                            for k, v in corrections.items()
                            if k in correctable and v is not None and v != ""
                        },
                    }

                resume_src.source_data = {
                    **existing_data,
                    "extracted": profile,
                    "raw_text": normalized,
                }
                resume_src.sync_status = "idle"
                resume_src.connection_status = "connected"
                resume_src.last_synced_at = datetime.now(timezone.utc)
                resume_src.error_message = None
                resume_src.updated_at = datetime.now(timezone.utc)
                db.commit()
                db.refresh(resume_src)

            phase_durations["analyzing"] = int((_time.perf_counter() - _phase_start) * 1000)
            EXPERIENCE_PHASE_DURATION_MS.labels(phase="analyzing").observe(
                phase_durations["analyzing"]
            )
            logger.info(
                "phase_complete", phase="analyzing", duration_ms=phase_durations["analyzing"]
            )

            # --- chunking ---
            _phase_start = _time.perf_counter()
            with _exp_tracer.start_as_current_span("experience.phase.chunking"):
                chunk_count = chunk_resume(db, resume_src, destructive=body.destructive)
                db.commit()
                _ctx = structlog.contextvars.get_contextvars()
                background_tasks.add_task(
                    embed_experience_chunks_task,
                    resume_src.user_id,
                    correlation_id=_ctx.get("correlation_id"),
                )

            phase_durations["chunking"] = int((_time.perf_counter() - _phase_start) * 1000)
            EXPERIENCE_PHASE_DURATION_MS.labels(phase="chunking").observe(
                phase_durations["chunking"]
            )
            logger.info(
                "resume_chunks_extracted",
                chunk_count=chunk_count,
                duration_ms=phase_durations["chunking"],
            )

            # --- summary ---
            total_duration_ms = int((_time.perf_counter() - overall_start) * 1000)
            EXPERIENCE_PROCESSING_TOTAL.labels(status="success").inc()
            EXPERIENCE_PROCESSING_DURATION_MS.observe(total_duration_ms)
            logger.info(
                "processing_complete",
                total_duration_ms=total_duration_ms,
                phase_durations=phase_durations,
            )

            all_sources = _all_sources(user, db)
            yield f"event: ready\ndata: {json.dumps(_experience_response(all_sources))}\n\n"
            completed = True

        except Exception as exc:
            EXPERIENCE_PROCESSING_TOTAL.labels(status="error").inc()
            logger.exception("processing_error")
            resume_src.sync_status = "error"
            resume_src.connection_status = "error"
            resume_src.error_message = _friendly_processing_error(exc)
            resume_src.updated_at = datetime.now(timezone.utc)
            db.commit()
            yield f"event: error\ndata: {json.dumps({'message': resume_src.error_message})}\n\n"
            completed = True
        finally:
            if not completed and resume_src.sync_status == "syncing":
                logger.warning("processing_interrupted")
                resume_src.sync_status = "error"
                resume_src.error_message = "Processing was interrupted. Please try again."
                resume_src.updated_at = datetime.now(timezone.utc)
                try:
                    db.commit()
                except Exception:
                    pass

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


# ---------------------------------------------------------------------------
# GET / DELETE experience
# ---------------------------------------------------------------------------


@router.get("/experience")
def get_experience(
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
):
    logger.debug("get_experience")
    if not user.experience_sources:
        return None
    return _experience_response(user.experience_sources)


@router.delete("/experience", status_code=204)
def delete_experience(
    cascade: bool = True,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    """Remove the resume ExperienceSource.

    cascade=true (default): also hard-deletes all derived claims and groups.
    cascade=false: keeps claims and groups; they become independent of any source.
    """
    resume_src = next((s for s in user.experience_sources if s.source_type == "resume"), None)
    if not resume_src:
        raise HTTPException(status_code=404, detail="No experience found")

    storage_key = (resume_src.config or {}).get("storage_key")
    if storage_key:
        try:
            get_storage_client().delete_object(storage_key)
        except Exception:
            logger.warning("storage_delete_failed", storage_key=storage_key)

    if cascade:
        delete_resume_chunks(db, user.id)
        delete_resume_groups(db, user.id)

    db.delete(resume_src)
    db.commit()
    logger.info("delete_experience_complete", cascade=cascade)


# ---------------------------------------------------------------------------
# Profile corrections
# ---------------------------------------------------------------------------


@router.patch("/experience/profile")
def update_profile(
    body: ProfileUpdate,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    resume_src = (
        db.query(ExperienceSource)
        .filter(
            ExperienceSource.user_id == user.id,
            ExperienceSource.source_type == "resume",
        )
        .first()
    )
    if not resume_src:
        raise HTTPException(status_code=404, detail="No experience found")

    existing_data = resume_src.source_data or {}
    corrections = dict(existing_data.get("corrections") or {})

    # None means "clear this correction" — remove the key so the field falls back to extracted.
    # Unset fields (not in the request at all) are left untouched.
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is None or v == "":
            corrections.pop(k, None)
        else:
            corrections[k] = v

    # Apply text corrections into the extracted block so all consumers see corrected values
    correctable = ("title", "headline", "summary", "location", "email", "phone", "linkedin")
    extracted = dict(existing_data.get("extracted") or {})
    extracted.update(
        {k: v for k, v in corrections.items() if k in correctable and v is not None and v != ""}
    )

    resume_src.source_data = {
        **existing_data,
        "corrections": corrections,
        "extracted": extracted,
    }
    resume_src.last_synced_at = datetime.now(timezone.utc)
    resume_src.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(resume_src)

    logger.info("update_profile_complete")
    all_sources = _all_sources(user, db)
    return _experience_response(all_sources)


# ---------------------------------------------------------------------------
# GitHub
# ---------------------------------------------------------------------------


@router.get("/experience/github/{username}/repos")
def get_github_repos(
    username: str,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
):
    from app.clients.github_client import get_github_client

    client = get_github_client()
    try:
        raw_repos = client.get_user_repos(username)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    repos = [
        {
            "name": r["name"],
            "description": r.get("description"),
            "language": r.get("language"),
            "star_count": r.get("stargazers_count", 0),
            "pushed_at": r.get("pushed_at"),
        }
        for r in raw_repos
    ]
    return {"username": username, "repos": repos}


@router.post("/experience/github")
def set_github(
    body: GitHubRequest,
    background_tasks: BackgroundTasks,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    from app.clients.github_client import get_github_client
    from app.services.github_enricher import enrich_github_repos

    github_src = (
        db.query(ExperienceSource)
        .filter(
            ExperienceSource.user_id == user.id,
            ExperienceSource.source_type == "github",
        )
        .first()
    )

    _ctx = structlog.contextvars.get_contextvars()

    # Rescan path: re-enrich specific repos without touching the connected repos list.
    if body.rescan_repo_names is not None:
        if not github_src:
            raise HTTPException(status_code=404, detail="No GitHub connection found")
        now_iso = datetime.now(timezone.utc).isoformat()
        rescan_set = set(body.rescan_repo_names)
        existing_repos = (github_src.source_data or {}).get("repos") or []
        updated_repos = [
            {**r, "scanning_started_at": now_iso} if r["name"] in rescan_set else r
            for r in existing_repos
        ]
        github_src.source_data = {**(github_src.source_data or {}), "repos": updated_repos}
        github_src.sync_status = "syncing"
        github_src.updated_at = datetime.now(timezone.utc)
        db.commit()
        background_tasks.add_task(
            enrich_github_repos,
            github_username=body.github_username,
            source_id=github_src.id,
            repo_names=body.rescan_repo_names,
            merge_with_existing=True,
            destructive=True,  # rescan = explicit refresh; replace existing claims for those repos
            user_id=_ctx.get("user_id"),
            correlation_id=_ctx.get("correlation_id"),
        )
        logger.info("github_rescan_queued", repo_count=len(body.rescan_repo_names or []))
        return {
            "experience_id": str(github_src.id),
            "status": "ready",
            "github_username": body.github_username,
        }

    client = get_github_client()
    try:
        raw_repos = client.get_user_repos(body.github_username)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    repos = [
        {
            "name": r["name"],
            "description": r.get("description"),
            "language": r.get("language"),
            "star_count": r.get("stargazers_count", 0),
            "pushed_at": r.get("pushed_at"),
        }
        for r in raw_repos
    ]

    if body.selected_repo_names is not None:
        selected = set(body.selected_repo_names)
        repos = [r for r in repos if r["name"] in selected]

    additions_only = body.enrich_only_repo_names is not None
    now = datetime.now(timezone.utc)

    if github_src:
        # Delete (or unlink) chunks/groups for repos being removed when selection changes
        if body.selected_repo_names is not None:
            old_repo_names = {
                r["name"] for r in ((github_src.source_data or {}).get("repos") or [])
            }
            new_repo_names = set(body.selected_repo_names)
            for removed_repo in old_repo_names - new_repo_names:
                if body.cascade_removed_repos:
                    delete_github_chunks(db, user.id, repo_name=removed_repo)
                    delete_github_groups(db, user.id, repo_name=removed_repo)
                # cascade=False: claims and groups are kept; the ExperienceSource row
                # is updated to exclude the repo from future syncs, but derived data survives

        github_src.config = {"username": body.github_username}
        if additions_only:
            github_src.source_data = {**(github_src.source_data or {}), "repos": repos}
        else:
            github_src.source_data = {"repos": repos}
        github_src.connection_status = "connected"
        github_src.updated_at = now
    else:
        github_src = ExperienceSource(
            user_id=user.id,
            source_type="github",
            connection_status="connected",
            sync_status="idle",
            config={"username": body.github_username},
            source_data={"repos": repos},
            created_at=now,
            updated_at=now,
        )
        db.add(github_src)

    db.commit()
    db.refresh(github_src)

    # Mark repos about to be enriched with scanning_started_at
    repo_names_to_enrich = (
        body.enrich_only_repo_names if additions_only else body.selected_repo_names
    )
    enrich_set = (
        set(repo_names_to_enrich)
        if repo_names_to_enrich is not None
        else {r["name"] for r in repos}
    )
    now_iso = now.isoformat()
    existing_repos = (github_src.source_data or {}).get("repos") or []
    updated_repos = [
        {**r, "scanning_started_at": now_iso} if r["name"] in enrich_set else r
        for r in existing_repos
    ]
    github_src.source_data = {**(github_src.source_data or {}), "repos": updated_repos}
    github_src.sync_status = "syncing"
    github_src.updated_at = datetime.now(timezone.utc)
    db.commit()

    background_tasks.add_task(
        enrich_github_repos,
        github_username=body.github_username,
        source_id=github_src.id,
        repo_names=repo_names_to_enrich,
        merge_with_existing=additions_only,
        user_id=_ctx.get("user_id"),
        correlation_id=_ctx.get("correlation_id"),
    )
    logger.info("github_enrichment_queued", github_username=body.github_username)

    return {
        "experience_id": str(github_src.id),
        "status": "ready",
        "github_username": body.github_username,
    }


@router.delete("/experience/github", status_code=204)
def remove_github(
    cascade: bool = True,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    """Remove the GitHub ExperienceSource.

    cascade=true (default): also hard-deletes all derived claims and groups.
    cascade=false: keeps claims and groups; they become independent of any source.
    """
    github_src = (
        db.query(ExperienceSource)
        .filter(
            ExperienceSource.user_id == user.id,
            ExperienceSource.source_type == "github",
        )
        .first()
    )
    if not github_src:
        raise HTTPException(status_code=404, detail="No GitHub profile connected")

    if cascade:
        delete_github_chunks(db, user.id)
        delete_github_groups(db, user.id)

    db.delete(github_src)
    db.commit()
    logger.info("remove_github_complete", cascade=cascade)


@router.delete("/experience/user-input", status_code=204)
def remove_user_input(
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    """Delete all user_input claims."""
    deleted = delete_user_input_chunks(db, user.id)
    db.commit()
    logger.info("user_input_removed", chunk_count=deleted)


# ---------------------------------------------------------------------------
# Short-input heuristic — no LLM needed for obvious single claims
# ---------------------------------------------------------------------------

_SENTENCE_SPLIT = re.compile(r"[.!?]\s[A-Z]")


def _is_short_input(text: str) -> bool:
    """Return True if the text is short enough to skip LLM parsing."""
    stripped = text.strip()
    if len(stripped) <= 200:
        return True
    # More than one sentence detected → needs LLM parse
    if _SENTENCE_SPLIT.search(stripped):
        return False
    return True


@router.post("/experience/user-input/parse")
def parse_user_input(
    body: UserInputRequest,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
):
    """Parse free-form text into a list of atomic claims. Preview only — no DB write."""
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="text cannot be empty")

    if _is_short_input(text):
        return {"chunks": [text]}

    result = llm_parse_with_retry(
        get_llm_client(),
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": parse_prompt.SYSTEM},
            {"role": "user", "content": parse_prompt.USER_TEMPLATE.format(text=text)},
        ],
        response_model=ParsedClaims,
        temperature=parse_prompt.TEMPERATURE,
        prompt_name=parse_prompt.PROMPT_NAME,
    )
    claims = [c.strip() for c in result.claims if c.strip()]
    if not claims:
        claims = [text]
    return {"chunks": claims}


@router.post("/experience/user-input/claims")
def persist_user_input_claims(
    body: UserInputChunksRequest,
    background_tasks: BackgroundTasks,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    """Persist a list of user_input claim strings as individual ExperienceClaims.

    Additive — does not replace existing user_input claims.
    Each claim is embedded in a background task.
    """
    chunks_text = [n for c in body.chunks if (n := normalize_claim_text(c))]
    if not chunks_text:
        raise HTTPException(status_code=422, detail="chunks cannot be empty")

    # Append after the highest existing position across all source types
    max_pos = (
        db.query(func.max(ExperienceClaim.position))
        .filter(ExperienceClaim.user_id == user.id)
        .scalar()
    )
    next_pos = (max_pos if max_pos is not None else -1) + 1

    now = datetime.now(timezone.utc)
    created_ids: list[str] = []
    for text in chunks_text:
        chunk = ExperienceClaim(
            user_id=user.id,
            source_type="user_input",
            source_ref=None,
            claim_type="other",
            content=text,
            group_key=None,
            date_range=None,
            keywords=None,
            provenance_metadata=None,
            position=next_pos,
            created_at=now,
            updated_at=now,
        )
        db.add(chunk)
        created_ids.append(str(chunk.id))
        next_pos += 1

    db.commit()
    _ctx = structlog.contextvars.get_contextvars()
    background_tasks.add_task(
        embed_experience_chunks_task,
        user.id,
        correlation_id=_ctx.get("correlation_id"),
    )
    logger.info("user_input_claims_persisted", claim_count=len(chunks_text))
    # Return any source id as experience_id for backward compat; None if no sources yet
    any_src = next(iter(user.experience_sources), None)
    return {
        "experience_id": str(any_src.id) if any_src else None,
        "claim_ids": created_ids,
    }


# ---------------------------------------------------------------------------
# Experience chunks — read + edit
# ---------------------------------------------------------------------------


def _serialize_exp_claim(c: ExperienceClaim) -> dict:
    return {
        "id": str(c.id),
        "source_type": c.source_type,
        "source_ref": c.source_ref,
        "claim_type": c.claim_type,
        "content": c.content,
        "group_key": c.group_key,
        "group_id": str(c.group_id) if c.group_id else None,
        "date_range": c.date_range,
        "keywords": c.keywords,
        "provenance_metadata": c.provenance_metadata,
        "original_content": c.original_content,
        "status": c.status,
        "position": c.position,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def _serialize_exp_group(g: ExperienceGroup) -> dict:
    type_meta = g.type_meta or {}
    return {
        "id": str(g.id),
        "name": g.name,
        "group_type": g.group_type,
        "source_type": g.source_type,
        "source_ref": g.source_ref,
        "parent_group_id": str(g.parent_group_id) if g.parent_group_id else None,
        "start_date": g.start_date,
        "end_date": g.end_date,
        "location": g.location,
        "type_meta": type_meta,
        "suggested_parent_id": type_meta.get("suggested_parent_id"),
        "suggestion_confidence": type_meta.get("suggestion_confidence"),
        "position": g.position,
        "description": g.description,
    }


def _group_experience_claims(chunks: list) -> dict:
    """Group ExperienceClaim rows into a render-ready structure.

    Maintains insertion order so work-experience roles and projects appear in the
    same sequence they were chunked (i.e. as they appeared in the resume).
    """
    work_exp_keys: list[tuple] = []
    work_exp_groups: dict[tuple, dict] = {}
    project_keys: list = []
    project_groups: dict = {}
    resume_skills: list = []
    resume_education: list = []
    resume_other: list = []
    github_keys: list = []
    github_groups: dict = {}
    user_input_chunks: list = []
    gap_response_chunks: list = []
    partial_response_chunks: list = []

    for c in chunks:
        s = _serialize_exp_claim(c)
        if c.source_type == "resume":
            if c.claim_type == "work_experience":
                key = (c.group_key, c.date_range)
                if key not in work_exp_groups:
                    work_exp_keys.append(key)
                    work_exp_groups[key] = {
                        "group_key": c.group_key,
                        "date_range": c.date_range,
                        "chunks": [],
                    }
                work_exp_groups[key]["chunks"].append(s)
            elif c.claim_type == "skill":
                resume_skills.append(s)
            elif c.claim_type == "project":
                key = c.group_key
                if key not in project_groups:
                    project_keys.append(key)
                    project_groups[key] = {"group_key": c.group_key, "chunks": []}
                project_groups[key]["chunks"].append(s)
            elif c.claim_type == "education":
                resume_education.append(s)
            else:
                resume_other.append(s)
        elif c.source_type == "github":
            key = c.source_ref
            if key not in github_groups:
                github_keys.append(key)
                github_groups[key] = {"group_key": c.source_ref, "chunks": []}
            github_groups[key]["chunks"].append(s)
        elif c.source_type == "user_input":
            user_input_chunks.append(s)
        elif c.source_type in ("gap_response", "additional_experience"):
            gap_response_chunks.append(s)
        elif c.source_type == "partial_response":
            partial_response_chunks.append(s)

    has_resume = bool(
        work_exp_keys or resume_skills or project_keys or resume_education or resume_other
    )
    has_github = bool(github_keys)

    return {
        "resume": {
            "work_experience": [work_exp_groups[k] for k in work_exp_keys],
            "skills": resume_skills,
            "projects": [project_groups[k] for k in project_keys],
            "education": resume_education,
            "other": resume_other,
        }
        if has_resume
        else None,
        "github": {"repos": [github_groups[k] for k in github_keys]} if has_github else None,
        "user_input": user_input_chunks if user_input_chunks else None,
        "gap_response": gap_response_chunks if gap_response_chunks else None,
        "partial_response": partial_response_chunks if partial_response_chunks else None,
    }


@router.get("/experience/claims")
def get_experience_claims(
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    chunks = (
        db.query(ExperienceClaim)
        .filter(ExperienceClaim.user_id == user.id)
        .order_by(ExperienceClaim.source_type, ExperienceClaim.position)
        .all()
    )
    return _group_experience_claims(chunks)


class ClaimContentUpdate(BaseModel):
    content: str | None = None
    group_key: str | None = None
    date_range: str | None = None
    status: str | None = None
    # Pass a UUID string to move to a group; pass "" to move to ungrouped.
    group_id: str | None = None

    @model_validator(mode="after")
    def at_least_one(self) -> "ClaimContentUpdate":
        if (
            self.content is None
            and self.group_key is None
            and self.date_range is None
            and self.status is None
            and self.group_id is None
        ):
            raise ValueError(
                "at least one of content, group_key, date_range, status, or group_id is required"
            )
        return self


@router.patch("/experience/claims/{claim_id}")
def update_experience_claim(
    claim_id: str,
    body: ClaimContentUpdate,
    background_tasks: BackgroundTasks,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    try:
        claim_uuid = uuid.UUID(claim_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid claim ID")

    claim = (
        db.query(ExperienceClaim)
        .filter(
            ExperienceClaim.id == claim_uuid,
            ExperienceClaim.user_id == user.id,
        )
        .first()
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    now = datetime.now(timezone.utc)

    if body.content is not None:
        content = body.content.strip()
        if not content:
            raise HTTPException(status_code=422, detail="Content cannot be empty")
        if claim.original_content is None:
            claim.original_content = claim.content
        claim.content = content
        claim.updated_at = now

    if body.status is not None:
        if body.status not in ("active", "archived"):
            raise HTTPException(status_code=422, detail="status must be 'active' or 'archived'")
        claim.status = body.status
        claim.updated_at = now

    if body.group_key is not None or body.date_range is not None:
        old_group_key = claim.group_key
        new_group_key = body.group_key if body.group_key is not None else old_group_key
        new_date_range = body.date_range if body.date_range is not None else claim.date_range
        siblings = (
            db.query(ExperienceClaim)
            .filter(
                ExperienceClaim.user_id == user.id,
                ExperienceClaim.source_type == claim.source_type,
                ExperienceClaim.source_ref == claim.source_ref,
                ExperienceClaim.group_key == old_group_key,
            )
            .all()
        )
        for sibling in siblings:
            sibling.group_key = new_group_key
            sibling.date_range = new_date_range
            sibling.updated_at = now

    if body.group_id is not None:
        if body.group_id == "":
            # Rehome to ungrouped — clear group_id and group_key
            claim.group_id = None
            claim.group_key = None
            claim.updated_at = now
        else:
            try:
                target_group_uuid = uuid.UUID(body.group_id)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid group_id")
            target_group = (
                db.query(ExperienceGroup)
                .filter(
                    ExperienceGroup.id == target_group_uuid,
                    ExperienceGroup.user_id == user.id,
                )
                .first()
            )
            if not target_group:
                raise HTTPException(status_code=404, detail="Target group not found")
            claim.group_id = target_group_uuid
            # Keep group_key in sync for legacy rendering compatibility
            claim.group_key = target_group.name
            claim.updated_at = now

    db.commit()
    db.refresh(claim)
    if body.content is not None:
        background_tasks.add_task(re_embed_chunk, claim.id)
    logger.info("update_experience_claim", claim_id=str(claim.id))
    return _serialize_exp_claim(claim)


@router.get("/experience/groups")
def get_experience_groups(
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    """Return all ExperienceGroup rows for the user."""
    groups = (
        db.query(ExperienceGroup)
        .filter(ExperienceGroup.user_id == user.id)
        .order_by(ExperienceGroup.source_type, ExperienceGroup.group_type, ExperienceGroup.name)
        .all()
    )
    return [_serialize_exp_group(g) for g in groups]


_DATE_RE = re.compile(r"^\d{4}(-\d{2})?$")


class GroupUpdate(BaseModel):
    parent_group_id: str | None = None  # UUID string to associate; "" or null to clear
    name: str | None = None
    description: str | None = None
    start_date: str | None = None  # YYYY or YYYY-MM; explicit null clears the field
    end_date: str | None = None  # YYYY or YYYY-MM; explicit null clears the field
    location: str | None = None  # explicit null clears the field
    type_meta: dict | None = None  # merged (not replaced) into existing type_meta

    @model_validator(mode="after")
    def at_least_one(self) -> "GroupUpdate":
        if all(
            v is None
            for v in [
                self.parent_group_id,
                self.name,
                self.description,
                self.start_date,
                self.end_date,
                self.location,
                self.type_meta,
            ]
        ):
            raise ValueError("at least one field is required")
        return self

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def validate_date(cls, v: object) -> object:
        if v is None or v == "":
            return None
        if isinstance(v, str) and not _DATE_RE.match(v):
            raise ValueError("date must be YYYY or YYYY-MM")
        return v


@router.patch("/experience/groups/{group_id}")
def update_experience_group(
    group_id: str,
    body: GroupUpdate,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    """Update an ExperienceGroup — primarily used to set/clear parent_group_id."""
    try:
        group_uuid = uuid.UUID(group_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid group ID")

    group = (
        db.query(ExperienceGroup)
        .filter(ExperienceGroup.id == group_uuid, ExperienceGroup.user_id == user.id)
        .first()
    )
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    if body.parent_group_id is not None:
        if body.parent_group_id == "":
            # Clear association
            group.parent_group_id = None
        else:
            try:
                parent_uuid = uuid.UUID(body.parent_group_id)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid parent_group_id")

            if parent_uuid == group.id:
                raise HTTPException(status_code=422, detail="A group cannot be its own parent")

            parent = (
                db.query(ExperienceGroup)
                .filter(ExperienceGroup.id == parent_uuid, ExperienceGroup.user_id == user.id)
                .first()
            )
            if not parent:
                raise HTTPException(status_code=404, detail="Parent group not found")
            if parent.group_type != "role":
                raise HTTPException(status_code=422, detail="Parent group must be a role group")
            if parent.parent_group_id is not None:
                raise HTTPException(
                    status_code=422, detail="Only one level of hierarchy is supported"
                )
            group.parent_group_id = parent_uuid

    if body.name is not None:
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="Name cannot be empty")
        group.name = name

    if body.description is not None:
        group.description = body.description.strip() or None

    if "start_date" in body.model_fields_set:
        group.start_date = body.start_date
    if "end_date" in body.model_fields_set:
        group.end_date = body.end_date
    if "location" in body.model_fields_set:
        group.location = (body.location or "").strip() or None
    if body.type_meta is not None:
        group.type_meta = {**(group.type_meta or {}), **body.type_meta}

    db.commit()
    db.refresh(group)
    logger.info("update_experience_group", group_id=str(group.id))
    return _serialize_exp_group(group)


@router.delete("/experience/groups/{group_id}", status_code=204)
def delete_experience_group(
    group_id: str,
    cascade: bool = False,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    """Delete an ExperienceGroup.

    cascade=false (default): group row is deleted; claims and child groups have their FK nulled
    out by the DB SET NULL constraint (they become ungrouped/standalone).
    cascade=true: all claims directly in this group and all child groups (and their claims)
    are hard-deleted before the group itself is removed.
    """
    try:
        group_uuid = uuid.UUID(group_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid group ID")

    group = (
        db.query(ExperienceGroup)
        .filter(ExperienceGroup.id == group_uuid, ExperienceGroup.user_id == user.id)
        .first()
    )
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    if cascade:
        child_ids = [
            row.id
            for row in db.query(ExperienceGroup.id).filter(
                ExperienceGroup.parent_group_id == group_uuid,
                ExperienceGroup.user_id == user.id,
            )
        ]
        all_group_ids = [group_uuid] + child_ids
        db.query(ExperienceClaim).filter(
            ExperienceClaim.group_id.in_(all_group_ids),
            ExperienceClaim.user_id == user.id,
        ).delete(synchronize_session=False)
        if child_ids:
            db.query(ExperienceGroup).filter(
                ExperienceGroup.id.in_(child_ids),
                ExperienceGroup.user_id == user.id,
            ).delete(synchronize_session=False)

    db.delete(group)
    db.commit()
    logger.info("delete_experience_group", group_id=str(group_uuid), cascade=cascade)


@router.delete("/experience/claims/{claim_id}", status_code=204)
def delete_experience_claim(
    claim_id: str,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    """Delete a single ExperienceClaim by ID. Works for any source_type."""
    try:
        claim_uuid = uuid.UUID(claim_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid claim ID")

    claim = (
        db.query(ExperienceClaim)
        .filter(
            ExperienceClaim.id == claim_uuid,
            ExperienceClaim.user_id == user.id,
        )
        .first()
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    db.delete(claim)
    db.commit()
    logger.info("delete_experience_claim", claim_id=str(claim_uuid))


# ---------------------------------------------------------------------------
# gap_response — creation + inline re-scoring
# ---------------------------------------------------------------------------


@router.post("/experience/gap-response")
def create_gap_response(
    body: GapResponseRequest,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    """
    Record a user's answer to a gap question.

    Creates a gap_response ExperienceClaim, embeds it synchronously, then re-scores
    the specific JobChunk that triggered the gap question. Returns the new score inline
    so the UI can update the requirement badge without a full page reload.
    """
    answer = body.answer.strip()
    question = body.question.strip()
    if not answer:
        raise HTTPException(status_code=422, detail="answer cannot be empty")
    is_additional = not question
    if body.response_type == "partial":
        source_type = "partial_response"
    elif question:
        source_type = "gap_response"
    else:
        source_type = "additional_experience"

    # Verify the tailoring belongs to this user
    try:
        tailoring_uuid = uuid.UUID(body.tailoring_id)
        job_chunk_uuid = uuid.UUID(body.job_chunk_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tailoring_id or job_chunk_id")

    tailoring = (
        db.query(Tailoring)
        .filter(Tailoring.id == tailoring_uuid, Tailoring.user_id == user.id)
        .first()
    )
    if not tailoring:
        raise HTTPException(status_code=404, detail="Tailoring not found")

    # Verify the job chunk belongs to that tailoring's job
    job_chunk = (
        db.query(JobChunk)
        .filter(JobChunk.id == job_chunk_uuid, JobChunk.job_id == tailoring.job_id)
        .first()
    )
    if not job_chunk:
        raise HTTPException(status_code=404, detail="Job chunk not found")

    structlog.contextvars.bind_contextvars(tailoring_id=body.tailoring_id)
    _gap_start = _time.perf_counter()

    # Upsert: reuse any existing response chunk for this job_chunk_id regardless of source type
    existing_gap_chunks = (
        db.query(ExperienceClaim)
        .filter(
            ExperienceClaim.user_id == user.id,
            ExperienceClaim.source_type.in_(
                ["gap_response", "additional_experience", "partial_response"]
            ),
        )
        .all()
    )
    gap_chunk = next(
        (
            c
            for c in existing_gap_chunks
            if c.provenance_metadata
            and c.provenance_metadata.get("job_chunk_id") == body.job_chunk_id
        ),
        None,
    )

    now = datetime.now(timezone.utc)
    metadata = (
        {"job_chunk_id": body.job_chunk_id, "tailoring_id": body.tailoring_id}
        if is_additional
        else {
            "question": question,
            "job_chunk_id": body.job_chunk_id,
            "tailoring_id": body.tailoring_id,
        }
    )
    if gap_chunk is not None:
        gap_chunk.content = answer
        gap_chunk.source_type = source_type
        gap_chunk.provenance_metadata = metadata
        gap_chunk.updated_at = now
    else:
        max_pos = (
            db.query(func.max(ExperienceClaim.position))
            .filter(ExperienceClaim.user_id == user.id)
            .scalar()
        )
        next_pos = (max_pos if max_pos is not None else -1) + 1
        gap_chunk = ExperienceClaim(
            user_id=user.id,
            source_type=source_type,
            source_ref=None,
            claim_type="other",
            content=answer,
            group_key=None,
            date_range=None,
            keywords=None,
            provenance_metadata=metadata,
            position=next_pos,
            created_at=now,
            updated_at=now,
        )
        db.add(gap_chunk)
    db.commit()

    with _exp_tracer.start_as_current_span(
        "experience.gap_response",
        attributes={
            "tailoring.id": body.tailoring_id,
            "job_chunk.id": body.job_chunk_id,
        },
    ):
        # Embed synchronously — must complete before re_enrich so the new vector is retrievable
        embed_experience_chunks(user.id, db)

        # Build profile from all sources (loaded via selectin on user)
        extracted_profile = sources_to_profile_dict(user.experience_sources)

        # Re-score the requirement synchronously — user is waiting for the result
        candidate_name = user.candidate_name
        re_enrich_single_chunk(
            str(job_chunk_uuid),
            extracted_profile,
            user.profile.pronouns if user.profile else None,
            user.id,
            candidate_name,
        )

        # re_enrich_single_chunk committed via its own session — re-query for updated score
        updated_chunk = db.query(JobChunk).filter(JobChunk.id == job_chunk_uuid).first()

        # If the re-score landed at partial (1), generate a path-to-strong question on the spot
        partial_question: str | None = None
        partial_context: str | None = None
        if updated_chunk and updated_chunk.match_score == 1:
            try:
                job = db.query(Job).filter(Job.id == tailoring.job_id).first()
                extracted_job = (job.extracted_job or {}) if job else {}
                job_context = _build_job_context(extracted_job)
                formatted_profile = format_sourced_profile(
                    extracted_profile,
                    candidate_name=candidate_name,
                    pronouns=user.profile.pronouns if user.profile else None,
                )
                pq = _generate_question(
                    "partial",
                    requirement=updated_chunk.content,
                    match_rationale=updated_chunk.match_rationale or "",
                    formatted_profile=formatted_profile,
                    job_context=job_context,
                )
                partial_question = pq.question_for_candidate
                partial_context = pq.context
            except Exception:
                logger.warning("partial_question_failed", job_chunk_id=str(job_chunk_uuid))

    duration_ms = int((_time.perf_counter() - _gap_start) * 1000)
    GAP_RESPONSE_DURATION_MS.observe(duration_ms)
    logger.info(
        "gap_response_complete",
        job_chunk_id=body.job_chunk_id,
        new_score=updated_chunk.match_score if updated_chunk else None,
        duration_ms=duration_ms,
        partial_question_generated=partial_question is not None,
    )
    return {
        "claim_id": str(gap_chunk.id),
        "updated_score": updated_chunk.match_score if updated_chunk else None,
        "updated_rationale": updated_chunk.match_rationale if updated_chunk else None,
        "advocacy_blurb": updated_chunk.advocacy_blurb if updated_chunk else None,
        "experience_sources": updated_chunk.experience_sources if updated_chunk else None,
        "partial_question": partial_question,
        "partial_context": partial_context,
    }
