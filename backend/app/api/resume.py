import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.clients.s3_client import delete_object, generate_presigned_put_url
from app.core.deps_database import get_db
from app.core.deps_user import get_current_user
from app.models.database import Resume, User
from app.services.resume_processor import process_resume

router = APIRouter()

ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "txt"}


class UploadUrlRequest(BaseModel):
    filename: str


class ProcessRequest(BaseModel):
    s3_key: str
    resume_id: str


@router.post("/resume/upload-url")
def get_upload_url(
    body: UploadUrlRequest,
    _: str = Depends(require_api_key),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ext = body.filename.rsplit(".", 1)[-1].lower() if "." in body.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type .{ext} not allowed. Supported: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # Delete existing resume record + S3 object if one already exists
    existing = db.query(Resume).filter(Resume.user_id == user.id).first()
    if existing:
        try:
            delete_object(existing.s3_key)
        except Exception:
            pass  # S3 cleanup failure is non-fatal
        db.delete(existing)
        db.commit()

    s3_key = f"users/{user.google_sub}/{uuid.uuid4()}.{ext}"

    resume = Resume(
        user_id=user.id,
        s3_key=s3_key,
        filename=body.filename,
        status="pending",
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)

    upload_url = generate_presigned_put_url(s3_key)

    return {
        "upload_url": upload_url,
        "s3_key": s3_key,
        "resume_id": str(resume.id),
    }


@router.post("/resume/process")
def trigger_process(
    body: ProcessRequest,
    background_tasks: BackgroundTasks,
    _: str = Depends(require_api_key),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resume = db.query(Resume).filter(
        Resume.user_id == user.id,
        Resume.s3_key == body.s3_key,
    ).first()

    if not resume:
        raise HTTPException(status_code=404, detail="Resume record not found")

    resume.status = "processing"
    db.commit()

    background_tasks.add_task(
        process_resume,
        resume.id,
        resume.s3_key,
        resume.filename,
    )

    return {"resume_id": str(resume.id), "status": "processing"}


@router.get("/resume")
def get_resume(
    _: str = Depends(require_api_key),
    user: User = Depends(get_current_user),
):
    r = user.resume
    if not r:
        return None

    return {
        "id": str(r.id),
        "filename": r.filename,
        "status": r.status,
        "extracted_profile": r.extracted_profile,
        "error_message": r.error_message,
        "uploaded_at": r.uploaded_at.isoformat() if r.uploaded_at else None,
        "processed_at": r.processed_at.isoformat() if r.processed_at else None,
    }


@router.delete("/resume", status_code=204)
def delete_resume(
    _: str = Depends(require_api_key),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    r = user.resume
    if not r:
        raise HTTPException(status_code=404, detail="No resume found")

    try:
        delete_object(r.s3_key)
    except Exception:
        pass  # S3 delete failure is non-fatal; proceed with DB cleanup

    db.delete(r)
    db.commit()
