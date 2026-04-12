import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

import anyio
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.clients.storage_client import get_storage_client
from app.core.deps_database import get_db
from app.core.deps_user import require_approved_user
from app.models.database import Experience, LlmTriggerLog, User
from app.services.experience_processor import (
    _friendly_processing_error,
    _normalize_resume_text,
    extract_text,
)
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


def _clear_resume_fields(e: Experience) -> None:
    """Remove all file-upload data from the experience row, preserving other sources."""
    e.s3_key = None
    e.filename = None
    e.raw_resume_text = None
    e.error_message = None
    e.processed_at = None
    e.extracted_profile = {
        k: v for k, v in (e.extracted_profile or {}).items() if k != "resume"
    } or None


class UploadUrlRequest(BaseModel):
    filename: str


class ProcessRequest(BaseModel):
    storage_key: str
    experience_id: str


class GitHubRequest(BaseModel):
    github_username: str


class UserInputRequest(BaseModel):
    text: str


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
        "user_input_text": e.user_input_text,
        "uploaded_at": e.uploaded_at.isoformat() if e.uploaded_at else None,
        "processed_at": e.processed_at.isoformat() if e.processed_at else None,
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
        _clear_resume_fields(existing)
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

    upload_url = get_storage_client().generate_upload_url(storage_key)
    logger.info("get_upload_url complete: experience_id=%s", experience.id)

    return {
        "upload_url": upload_url,
        "storage_key": storage_key,
        "experience_id": str(experience.id),
    }


@router.post("/experience/process")
async def trigger_process(
    body: ProcessRequest,
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
                return

            text = await anyio.to_thread.run_sync(lambda: extract_text(file_bytes, filename))
            normalized = _normalize_resume_text(text)

            yield "event: stage\ndata: analyzing\n\n"

            profile = await anyio.to_thread.run_sync(lambda: extract_profile(normalized))

            experience.raw_resume_text = normalized
            experience.extracted_profile = {"resume": profile}
            experience.status = "ready"
            experience.processed_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(experience)

            logger.info("trigger_process SSE complete: experience_id=%s", experience.id)
            yield f"event: ready\ndata: {json.dumps(_experience_response(experience))}\n\n"

        except Exception as exc:
            logger.exception("trigger_process SSE failed: %s", exc)
            experience.status = "error"
            experience.error_message = _friendly_processing_error(exc)
            db.commit()
            yield f"event: error\ndata: {json.dumps({'message': experience.error_message})}\n\n"

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
        _clear_resume_fields(e)
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

    resume = {}
    if experience.extracted_profile:
        resume = dict(experience.extracted_profile.get("resume") or {})

    update_data = body.model_dump(exclude_unset=True)
    resume = {**resume, **update_data}

    experience.extracted_profile = {
        **(experience.extracted_profile or {}),
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
    from app.core.mvp_github import fetch_repos

    return {"username": username, "repos": fetch_repos(username)}


@router.post("/experience/github")
def set_github(
    body: GitHubRequest,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    from app.core.mvp_github import fetch_repos

    experience = db.query(Experience).filter(Experience.user_id == user.id).first()
    try:
        repos = fetch_repos(body.github_username)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if experience:
        experience.github_username = body.github_username
        experience.github_repos = repos
        profile = experience.extracted_profile or {}
        experience.extracted_profile = {**profile, "github": {"repos": repos}}
        experience.processed_at = datetime.now(timezone.utc)
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
            processed_at=datetime.now(timezone.utc),
        )
        db.add(experience)

    db.commit()
    db.refresh(experience)
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
    if experience.extracted_profile and "github" in experience.extracted_profile:
        experience.extracted_profile = {
            k: v for k, v in experience.extracted_profile.items() if k != "github"
        } or None
    db.commit()


@router.post("/experience/user-input")
def set_user_input(
    body: UserInputRequest,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    experience = db.query(Experience).filter(Experience.user_id == user.id).first()

    if experience:
        experience.user_input_text = body.text
        profile = experience.extracted_profile or {}
        experience.extracted_profile = {**profile, "user_input": {"text": body.text}}
        experience.processed_at = datetime.now(timezone.utc)
        if experience.status not in ("ready", "processing"):
            experience.status = "ready"
    else:
        experience = Experience(
            user_id=user.id,
            s3_key=None,
            filename=None,
            status="ready",
            user_input_text=body.text,
            extracted_profile={"user_input": {"text": body.text}},
            processed_at=datetime.now(timezone.utc),
        )
        db.add(experience)

    db.commit()
    db.refresh(experience)
    return {"experience_id": str(experience.id), "status": experience.status}
