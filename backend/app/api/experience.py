import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.clients.storage_client import get_storage_client
from app.core.deps_database import get_db
from app.core.deps_user import require_approved_user
from app.models.database import Experience, User
from app.services.experience_processor import process_experience

router = APIRouter()
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "txt"}


class UploadUrlRequest(BaseModel):
    filename: str


class ProcessRequest(BaseModel):
    storage_key: str
    experience_id: str


class GitHubRequest(BaseModel):
    github_username: str


class UserInputRequest(BaseModel):
    text: str


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

    # Delete existing experience record + blob if one already exists
    existing = db.query(Experience).filter(Experience.user_id == user.id).first()
    if existing:
        logger.debug("Deleting existing experience %s for user %s", existing.id, user.id)
        if existing.s3_key:
            try:
                get_storage_client().delete_object(existing.s3_key)
            except Exception:
                logger.warning("Storage cleanup failed for key=%s — continuing", existing.s3_key)
        db.delete(existing)
        db.commit()

    storage_key = f"users/{user.google_sub}/{uuid.uuid4()}.{ext}"
    logger.debug("Assigned storage_key=%s", storage_key)

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
def trigger_process(
    body: ProcessRequest,
    background_tasks: BackgroundTasks,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    logger.info("trigger_process: user=%s storage_key=%s experience_id=%s",
                user.id, body.storage_key, body.experience_id)
    experience = db.query(Experience).filter(
        Experience.user_id == user.id,
        Experience.s3_key == body.storage_key,
    ).first()

    if not experience:
        logger.warning("trigger_process: no experience found for user=%s storage_key=%s",
                       user.id, body.storage_key)
        raise HTTPException(status_code=404, detail="Experience record not found")

    experience.status = "processing"
    db.commit()

    background_tasks.add_task(
        process_experience,
        experience.id,
        experience.s3_key,
        experience.filename,
    )
    logger.info("trigger_process: background task queued for experience_id=%s", experience.id)

    return {"experience_id": str(experience.id), "status": "processing"}


@router.get("/experience")
def get_experience(
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
):
    logger.debug("get_experience: user=%s", user.id)
    e = user.experience
    if not e:
        return None

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
            logger.warning("delete_experience: storage delete failed for key=%s — continuing", e.s3_key)

    db.delete(e)
    db.commit()
    logger.info("delete_experience: complete for user=%s", user.id)


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
    repos = fetch_repos(body.github_username)

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
