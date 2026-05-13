import json
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

import anyio
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, model_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.clients.llm_client import get_llm_client
from app.clients.storage_client import get_storage_client
from app.config import settings
from app.core.deps_database import get_db
from app.core.deps_user import require_approved_user
from app.core.llm_utils import llm_parse_with_retry
from app.models.database import (
    Experience,
    ExperienceChunk,
    Job,
    JobChunk,
    LlmTriggerLog,
    Tailoring,
    User,
)
from app.prompts import user_input_parse as parse_prompt
from app.schemas.llm_outputs import ParsedClaims
from app.services.chunk_matcher import re_enrich_single_chunk
from app.services.experience_chunker import (
    chunk_resume,
    delete_github_chunks,
    delete_resume_chunks,
    delete_user_input_chunks,
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
from app.services.gap_analyzer import _build_job_context, _generate_partial_question
from app.services.profile_extractor import extract_profile

router = APIRouter()
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "txt"}

# Minimum gap between experience processing triggers per user.
_EXPERIENCE_PROCESS_COOLDOWN_MINUTES = 5

# Resumes are typically < 500 KB. 10 MB is a generous ceiling that still
# blocks accidental or malicious oversized uploads before text extraction.
_MAX_RESUME_BYTES = 10 * 1024 * 1024  # 10 MB


def _has_non_resume_sources(e: Experience) -> bool:
    """Return True if the experience row has data from any source other than the uploaded file."""
    if e.github_username:
        return True
    if e.user_input_text:
        return True
    # Any extracted_profile keys other than "resume" indicate another source
    if e.extracted_profile and any(k != "resume" for k in e.extracted_profile):
        return True
    return False


def _clear_resume_fields(e: Experience, db: Session) -> None:
    """Remove all file-upload data from the experience row, preserving other sources.

    Also deletes associated resume ExperienceChunk rows. Does not commit.
    """
    e.s3_key = None
    e.filename = None
    e.raw_resume_text = None
    e.error_message = None
    e.processed_at = None
    e.last_process_requested_at = None
    e.extracted_profile = {
        k: v for k, v in (e.extracted_profile or {}).items() if k != "resume"
    } or None
    delete_resume_chunks(db, e.id)


class UploadUrlRequest(BaseModel):
    filename: str


class ProcessRequest(BaseModel):
    storage_key: str
    experience_id: str


class GitHubRequest(BaseModel):
    github_username: str
    selected_repo_names: list[str] | None = None
    rescan_repo_names: list[str] | None = None
    enrich_only_repo_names: list[str] | None = None


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


def _experience_response(e: Experience) -> dict:
    return {
        "id": str(e.id),
        "filename": e.filename,
        "status": e.status,
        "extracted_profile": e.extracted_profile,
        "raw_resume_text": e.raw_resume_text,
        "error_message": e.error_message,
        "github_username": e.github_username,
        "github_repos": e.github_repos,
        "github_repo_details": e.github_repo_details,
        "user_input_text": e.user_input_text,
        "uploaded_at": e.uploaded_at.isoformat() if e.uploaded_at else None,
        "processed_at": e.processed_at.isoformat() if e.processed_at else None,
        "last_process_requested_at": e.last_process_requested_at.isoformat()
        if e.last_process_requested_at
        else None,
    }


@router.post("/experience/upload-url")
def get_upload_url(
    body: UploadUrlRequest,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    logger.info("get_upload_url: user=%s filename=%s", user.id, body.filename)
    ext = body.filename.rsplit(".", 1)[-1].lower() if "." in body.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type .{ext} not allowed. Supported: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    existing = db.query(Experience).filter(Experience.user_id == user.id).first()

    storage_key = f"users/{user.google_sub}/{uuid.uuid4()}.{ext}"
    logger.debug("Assigned storage_key=%s", storage_key)

    if existing:
        # Clean up old file but preserve GitHub data on the existing row
        if existing.s3_key:
            try:
                get_storage_client().delete_object(existing.s3_key)
            except Exception:
                logger.warning("Storage cleanup failed for key=%s — continuing", existing.s3_key)
        _clear_resume_fields(existing, db)
        existing.s3_key = storage_key
        existing.filename = body.filename
        existing.status = "pending"
        existing.uploaded_at = datetime.now(timezone.utc)
        experience = existing
    else:
        experience = Experience(
            user_id=user.id,
            s3_key=storage_key,
            filename=body.filename,
            status="pending",
        )
        db.add(experience)
    db.commit()
    db.refresh(experience)

    try:
        upload_url = get_storage_client().generate_upload_url(storage_key)
    except Exception as exc:
        logger.exception("generate_upload_url failed for experience_id=%s", experience.id)
        experience.status = "error"
        experience.error_message = "Failed to prepare upload. Please try again."
        db.commit()
        raise HTTPException(
            status_code=500, detail="Failed to prepare upload. Please try again."
        ) from exc

    logger.info("get_upload_url complete: experience_id=%s", experience.id)

    return {
        "upload_url": upload_url,
        "storage_key": storage_key,
        "experience_id": str(experience.id),
    }


@router.post("/experience/process")
async def trigger_process(
    body: ProcessRequest,
    background_tasks: BackgroundTasks,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    logger.info("trigger_process: user=%s storage_key=%s", user.id, body.storage_key)
    experience = (
        db.query(Experience)
        .filter(
            Experience.user_id == user.id,
            Experience.s3_key == body.storage_key,
        )
        .first()
    )

    if not experience:
        raise HTTPException(status_code=404, detail="Experience record not found")

    if experience.last_process_requested_at:
        cooldown_end = experience.last_process_requested_at + timedelta(
            minutes=_EXPERIENCE_PROCESS_COOLDOWN_MINUTES
        )
        if datetime.now(timezone.utc) < cooldown_end:
            remaining = max(
                1, int((cooldown_end - datetime.now(timezone.utc)).total_seconds() / 60) + 1
            )
            logger.warning("Experience process cooldown active: user=%s", user.id)
            raise HTTPException(
                status_code=429,
                detail=f"Please wait {remaining} minute(s) before re-processing your experience.",
            )

    experience.last_process_requested_at = datetime.now(timezone.utc)
    experience.status = "processing"
    db.add(LlmTriggerLog(user_id=user.id, event_type="experience_process"))
    db.commit()

    storage_key = body.storage_key
    filename = experience.filename or "file.txt"

    async def _stream():
        completed = False
        try:
            yield "event: stage\ndata: extracting\n\n"

            file_bytes = await anyio.to_thread.run_sync(
                lambda: get_storage_client().download_bytes(storage_key)
            )

            if len(file_bytes) > _MAX_RESUME_BYTES:
                mb = len(file_bytes) / 1024 / 1024
                logger.warning("File too large: %.1f MB user=%s", mb, user.id)
                experience.status = "error"
                experience.error_message = (
                    f"File is too large ({mb:.1f} MB). Please upload a file under 10 MB."
                )
                db.commit()
                yield f"event: error\ndata: {json.dumps({'message': experience.error_message})}\n\n"
                completed = True
                return

            text = await anyio.to_thread.run_sync(lambda: extract_text(file_bytes, filename))
            normalized = _normalize_resume_text(text)

            yield "event: stage\ndata: analyzing\n\n"

            profile = await anyio.to_thread.run_sync(lambda: extract_profile(normalized))

            # Preserve non-resume keys (github, corrections, user_input, etc.) across reprocessing.
            # Re-apply any saved corrections to the freshly extracted resume so the user's
            # manual overrides aren't silently discarded when they re-upload.
            existing_profile = experience.extracted_profile or {}
            corrections = existing_profile.get("corrections") or {}
            if corrections:
                correctable = ("title", "headline", "summary", "location")
                profile = {
                    **profile,
                    **{k: v for k, v in corrections.items() if k in correctable and v is not None},
                }

            experience.raw_resume_text = normalized
            experience.extracted_profile = {
                **{k: v for k, v in existing_profile.items() if k != "resume"},
                "resume": profile,
            }
            experience.status = "ready"
            experience.processed_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(experience)

            chunk_count = chunk_resume(db, experience)
            db.commit()
            background_tasks.add_task(embed_experience_chunks_task, experience.id)
            logger.info(
                "trigger_process SSE complete: experience_id=%s chunks=%d",
                experience.id,
                chunk_count,
            )
            yield f"event: ready\ndata: {json.dumps(_experience_response(experience))}\n\n"
            completed = True

        except Exception as exc:
            logger.exception("trigger_process SSE failed: %s", exc)
            experience.status = "error"
            experience.error_message = _friendly_processing_error(exc)
            db.commit()
            yield f"event: error\ndata: {json.dumps({'message': experience.error_message})}\n\n"
            completed = True
        finally:
            if not completed and experience.status == "processing":
                logger.warning(
                    "trigger_process SSE interrupted (client disconnect?): experience_id=%s",
                    experience.id,
                )
                experience.status = "error"
                experience.error_message = "Processing was interrupted. Please try again."
                try:
                    db.commit()
                except Exception:
                    pass

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


@router.get("/experience")
def get_experience(
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
):
    logger.debug("get_experience: user=%s", user.id)
    e = user.experience
    if not e:
        return None
    return _experience_response(e)


@router.delete("/experience", status_code=204)
def delete_experience(
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    logger.info("delete_experience: user=%s", user.id)
    e = user.experience
    if not e:
        raise HTTPException(status_code=404, detail="No experience found")

    if e.s3_key:
        try:
            get_storage_client().delete_object(e.s3_key)
        except Exception:
            logger.warning(
                "delete_experience: storage delete failed for key=%s — continuing", e.s3_key
            )

    if _has_non_resume_sources(e):
        # Other sources exist — clear only the file upload fields
        _clear_resume_fields(e, db)
        e.status = "ready"
    else:
        db.delete(e)

    db.commit()
    logger.info("delete_experience: complete for user=%s", user.id)


@router.patch("/experience/profile")
def update_profile(
    body: ProfileUpdate,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    experience = db.query(Experience).filter(Experience.user_id == user.id).first()
    if not experience:
        raise HTTPException(status_code=404, detail="No experience found")

    existing = experience.extracted_profile or {}
    corrections = dict(existing.get("corrections") or {})
    corrections.update(body.model_dump(exclude_unset=True, exclude_none=True))

    # Also apply text corrections directly into the resume block so all consumers
    # (profile tab, public profile, etc.) see the corrected values without needing
    # to know about the corrections layer.
    resume = dict(existing.get("resume") or {})
    correctable = ("title", "headline", "summary", "location")
    resume.update({k: v for k, v in corrections.items() if k in correctable and v is not None})

    experience.extracted_profile = {
        **existing,
        "corrections": corrections,
        "resume": resume,
    }
    experience.processed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(experience)
    logger.info("update_profile: user=%s", user.id)
    return _experience_response(experience)


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

    experience = db.query(Experience).filter(Experience.user_id == user.id).first()

    # Rescan path: re-enrich specific repos without touching the connected repos list.
    if body.rescan_repo_names is not None:
        if not experience or not experience.github_username:
            raise HTTPException(status_code=404, detail="No GitHub connection found")
        now_iso = datetime.now(timezone.utc).isoformat()
        rescan_set = set(body.rescan_repo_names)
        experience.github_repos = [
            {**r, "scanning_started_at": now_iso} if r["name"] in rescan_set else r
            for r in (experience.github_repos or [])
        ]
        db.commit()
        background_tasks.add_task(
            enrich_github_repos,
            github_username=body.github_username,
            experience_id=experience.id,
            repo_names=body.rescan_repo_names,
            merge_with_existing=True,
        )
        logger.info(
            "set_github: queued rescan for user=%s repos=%s",
            user.id,
            body.rescan_repo_names,
        )
        return {
            "experience_id": str(experience.id),
            "status": experience.status,
            "github_username": experience.github_username,
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

    # When enrich_only_repo_names is set (additions-only modify), preserve existing
    # enrichment and merge new repos in. Otherwise clear stale enrichment.
    additions_only = body.enrich_only_repo_names is not None

    if experience:
        # Delete chunks for repos being removed whenever the selection changes
        if body.selected_repo_names is not None:
            old_repo_names = {r["name"] for r in (experience.github_repos or [])}
            new_repo_names = set(body.selected_repo_names)
            for removed_repo in old_repo_names - new_repo_names:
                delete_github_chunks(db, experience.id, repo_name=removed_repo)

        experience.github_username = body.github_username
        experience.github_repos = repos
        if not additions_only:
            experience.github_repo_details = None
        profile = experience.extracted_profile or {}
        experience.extracted_profile = {**profile, "github": {"repos": repos}}
        if experience.status not in ("ready", "processing"):
            experience.status = "ready"
    else:
        experience = Experience(
            user_id=user.id,
            s3_key=None,
            filename=None,
            status="ready",
            github_username=body.github_username,
            github_repos=repos,
            extracted_profile={"github": {"repos": repos}},
        )
        db.add(experience)

    db.commit()
    db.refresh(experience)

    repo_names_to_enrich = (
        body.enrich_only_repo_names if additions_only else body.selected_repo_names
    )
    now_iso = datetime.now(timezone.utc).isoformat()
    enrich_set = (
        set(repo_names_to_enrich)
        if repo_names_to_enrich is not None
        else {r["name"] for r in (experience.github_repos or [])}
    )
    experience.github_repos = [
        {**r, "scanning_started_at": now_iso} if r["name"] in enrich_set else r
        for r in (experience.github_repos or [])
    ]
    db.commit()
    background_tasks.add_task(
        enrich_github_repos,
        github_username=body.github_username,
        experience_id=experience.id,
        repo_names=repo_names_to_enrich,
        merge_with_existing=additions_only,
    )
    logger.info(
        "set_github: queued enrichment for user=%s username=%s", user.id, body.github_username
    )

    return {
        "experience_id": str(experience.id),
        "status": experience.status,
        "github_username": experience.github_username,
    }


@router.delete("/experience/github", status_code=204)
def remove_github(
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    experience = db.query(Experience).filter(Experience.user_id == user.id).first()
    if not experience or not experience.github_username:
        raise HTTPException(status_code=404, detail="No GitHub profile connected")

    experience.github_username = None
    experience.github_repos = None
    experience.github_repo_details = None
    if experience.extracted_profile and "github" in experience.extracted_profile:
        experience.extracted_profile = {
            k: v for k, v in experience.extracted_profile.items() if k != "github"
        } or None
    delete_github_chunks(db, experience.id)
    db.commit()


@router.delete("/experience/user-input", status_code=204)
def remove_user_input(
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    """Delete all user_input chunks for the experience."""
    experience = db.query(Experience).filter(Experience.user_id == user.id).first()
    if not experience:
        raise HTTPException(status_code=404, detail="No experience found")

    experience.user_input_text = None
    if experience.extracted_profile and "user_input" in experience.extracted_profile:
        experience.extracted_profile = {
            k: v for k, v in experience.extracted_profile.items() if k != "user_input"
        } or None
    deleted = delete_user_input_chunks(db, experience.id)
    db.commit()
    logger.info("remove_user_input: deleted %d chunks for user=%s", deleted, user.id)


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
    )
    claims = [c.strip() for c in result.claims if c.strip()]
    if not claims:
        claims = [text]
    return {"chunks": claims}


def _ensure_experience(user: User, db: Session) -> Experience:
    """Return the user's Experience row, creating one if it doesn't exist."""
    experience = db.query(Experience).filter(Experience.user_id == user.id).first()
    if not experience:
        experience = Experience(
            user_id=user.id,
            s3_key=None,
            filename=None,
            status="ready",
            processed_at=datetime.now(timezone.utc),
        )
        db.add(experience)
        db.flush()
    return experience


@router.post("/experience/user-input/chunks")
def persist_user_input_chunks(
    body: UserInputChunksRequest,
    background_tasks: BackgroundTasks,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    """Persist a list of user_input claim strings as individual ExperienceChunks.

    Additive — does not replace existing user_input chunks.
    Each chunk is embedded in a background task.
    """
    chunks_text = [c.strip() for c in body.chunks if c.strip()]
    if not chunks_text:
        raise HTTPException(status_code=422, detail="chunks cannot be empty")

    experience = _ensure_experience(user, db)

    # Append after the highest existing position across all source types
    max_pos = (
        db.query(func.max(ExperienceChunk.position))
        .filter(ExperienceChunk.experience_id == experience.id)
        .scalar()
    )
    next_pos = (max_pos if max_pos is not None else -1) + 1

    now = datetime.now(timezone.utc)
    created_ids: list[str] = []
    for text in chunks_text:
        chunk = ExperienceChunk(
            experience_id=experience.id,
            source_type="user_input",
            source_ref=None,
            claim_type="other",
            content=text,
            group_key=None,
            date_range=None,
            technologies=None,
            chunk_metadata=None,
            position=next_pos,
            created_at=now,
            updated_at=now,
        )
        db.add(chunk)
        created_ids.append(str(chunk.id))
        next_pos += 1

    if experience.status not in ("ready", "processing"):
        experience.status = "ready"

    db.commit()
    background_tasks.add_task(embed_experience_chunks_task, experience.id)
    logger.info(
        "persist_user_input_chunks: created %d chunks for user=%s", len(chunks_text), user.id
    )
    return {"experience_id": str(experience.id), "chunk_ids": created_ids}


# ---------------------------------------------------------------------------
# Experience chunks — read + edit
# ---------------------------------------------------------------------------


def _serialize_exp_chunk(c: ExperienceChunk) -> dict:
    return {
        "id": str(c.id),
        "source_type": c.source_type,
        "source_ref": c.source_ref,
        "claim_type": c.claim_type,
        "content": c.content,
        "group_key": c.group_key,
        "date_range": c.date_range,
        "technologies": c.technologies,
        "chunk_metadata": c.chunk_metadata,
        "position": c.position,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def _group_experience_chunks(chunks: list) -> dict:
    """Group ExperienceChunk rows into a render-ready structure.

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
        s = _serialize_exp_chunk(c)
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


@router.get("/experience/chunks")
def get_experience_chunks(
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    experience = db.query(Experience).filter(Experience.user_id == user.id).first()
    if not experience:
        return {
            "resume": None,
            "github": None,
            "user_input": None,
            "gap_response": None,
            "partial_response": None,
        }

    chunks = (
        db.query(ExperienceChunk)
        .filter(ExperienceChunk.experience_id == experience.id)
        .order_by(ExperienceChunk.source_type, ExperienceChunk.position)
        .all()
    )
    return _group_experience_chunks(chunks)


class ChunkContentUpdate(BaseModel):
    content: str | None = None
    group_key: str | None = None
    date_range: str | None = None

    @model_validator(mode="after")
    def at_least_one(self) -> "ChunkContentUpdate":
        if self.content is None and self.group_key is None and self.date_range is None:
            raise ValueError("at least one of content, group_key, or date_range is required")
        return self


@router.patch("/experience/chunks/{chunk_id}")
def update_experience_chunk(
    chunk_id: str,
    body: ChunkContentUpdate,
    background_tasks: BackgroundTasks,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    experience = db.query(Experience).filter(Experience.user_id == user.id).first()
    if not experience:
        raise HTTPException(status_code=404, detail="No experience found")

    try:
        chunk_uuid = uuid.UUID(chunk_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chunk ID")

    chunk = (
        db.query(ExperienceChunk)
        .filter(
            ExperienceChunk.id == chunk_uuid,
            ExperienceChunk.experience_id == experience.id,
        )
        .first()
    )
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")

    now = datetime.now(timezone.utc)

    if body.content is not None:
        content = body.content.strip()
        if not content:
            raise HTTPException(status_code=422, detail="Content cannot be empty")
        chunk.content = content
        chunk.updated_at = now

    if body.group_key is not None or body.date_range is not None:
        old_group_key = chunk.group_key
        new_group_key = body.group_key if body.group_key is not None else old_group_key
        new_date_range = body.date_range if body.date_range is not None else chunk.date_range
        siblings = (
            db.query(ExperienceChunk)
            .filter(
                ExperienceChunk.experience_id == experience.id,
                ExperienceChunk.source_type == chunk.source_type,
                ExperienceChunk.source_ref == chunk.source_ref,
                ExperienceChunk.group_key == old_group_key,
            )
            .all()
        )
        for sibling in siblings:
            sibling.group_key = new_group_key
            sibling.date_range = new_date_range
            sibling.updated_at = now

    db.commit()
    db.refresh(chunk)
    if body.content is not None:
        background_tasks.add_task(re_embed_chunk, chunk.id)
    logger.info("update_experience_chunk: chunk=%s user=%s", chunk.id, user.id)
    return _serialize_exp_chunk(chunk)


@router.delete("/experience/chunks/{chunk_id}", status_code=204)
def delete_experience_chunk(
    chunk_id: str,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    """Delete a single ExperienceChunk by ID. Works for any source_type."""
    experience = db.query(Experience).filter(Experience.user_id == user.id).first()
    if not experience:
        raise HTTPException(status_code=404, detail="No experience found")

    try:
        chunk_uuid = uuid.UUID(chunk_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chunk ID")

    chunk = (
        db.query(ExperienceChunk)
        .filter(
            ExperienceChunk.id == chunk_uuid,
            ExperienceChunk.experience_id == experience.id,
        )
        .first()
    )
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")

    db.delete(chunk)
    db.commit()
    logger.info("delete_experience_chunk: chunk=%s user=%s", chunk_uuid, user.id)


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

    Creates a gap_response ExperienceChunk, embeds it synchronously, then re-scores
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

    experience = _ensure_experience(user, db)

    # Upsert: reuse any existing response chunk for this job_chunk_id regardless of source type
    existing_gap_chunks = (
        db.query(ExperienceChunk)
        .filter(
            ExperienceChunk.experience_id == experience.id,
            ExperienceChunk.source_type.in_(
                ["gap_response", "additional_experience", "partial_response"]
            ),
        )
        .all()
    )
    gap_chunk = next(
        (
            c
            for c in existing_gap_chunks
            if c.chunk_metadata and c.chunk_metadata.get("job_chunk_id") == body.job_chunk_id
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
        gap_chunk.chunk_metadata = metadata
        gap_chunk.updated_at = now
    else:
        max_pos = (
            db.query(func.max(ExperienceChunk.position))
            .filter(ExperienceChunk.experience_id == experience.id)
            .scalar()
        )
        next_pos = (max_pos if max_pos is not None else -1) + 1
        gap_chunk = ExperienceChunk(
            experience_id=experience.id,
            source_type=source_type,
            source_ref=None,
            claim_type="other",
            content=answer,
            group_key=None,
            date_range=None,
            technologies=None,
            chunk_metadata=metadata,
            position=next_pos,
            created_at=now,
            updated_at=now,
        )
        db.add(gap_chunk)
    db.commit()

    # Embed synchronously — must complete before re_enrich so the new vector is retrievable
    embed_experience_chunks(experience.id, db)

    # Re-score the requirement synchronously — user is waiting for the result
    preferred = " ".join(
        filter(None, [user.preferred_first_name, user.preferred_last_name])
    ).strip()
    candidate_name = preferred or user.name or user.email
    re_enrich_single_chunk(
        str(job_chunk_uuid),
        experience.extracted_profile or {},
        user.pronouns,
        experience.id,
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
            preferred = " ".join(
                filter(None, [user.preferred_first_name, user.preferred_last_name])
            ).strip()
            candidate_name = preferred or user.name or user.email
            from app.services.tailoring_generator import _format_sourced_profile

            formatted_profile = _format_sourced_profile(
                experience.extracted_profile or {},
                candidate_name=candidate_name,
                pronouns=user.pronouns,
            )
            pq = _generate_partial_question(
                requirement=updated_chunk.content,
                match_rationale=updated_chunk.match_rationale or "",
                formatted_profile=formatted_profile,
                job_context=job_context,
            )
            partial_question = pq.question_for_candidate
            partial_context = pq.context
        except Exception:
            logger.warning(
                "On-demand partial question generation failed for chunk %s", job_chunk_uuid
            )

    logger.info(
        "create_gap_response: chunk=%s user=%s new_score=%s",
        gap_chunk.id,
        user.id,
        updated_chunk.match_score if updated_chunk else None,
    )
    return {
        "chunk_id": str(gap_chunk.id),
        "updated_score": updated_chunk.match_score if updated_chunk else None,
        "updated_rationale": updated_chunk.match_rationale if updated_chunk else None,
        "advocacy_blurb": updated_chunk.advocacy_blurb if updated_chunk else None,
        "experience_source": updated_chunk.experience_source if updated_chunk else None,
        "partial_question": partial_question,
        "partial_context": partial_context,
    }
