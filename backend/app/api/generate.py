from fastapi import APIRouter, Depends, HTTPException
from app.models.mvp_schemas import GenerateInput, GeneratedOutput
from app.core.mvp_llm import generate_match
from app.auth import require_api_key
from app.core.deps_user import require_approved_user

from sqlalchemy.orm import Session
from app.models.database import Experience, Job, User
from app.core.deps_database import get_db

router = APIRouter()

@router.post("/generate", response_model=GeneratedOutput)
def generate(
    data: GenerateInput,
    _: str = Depends(require_api_key),
    user: User = Depends(require_approved_user),
    db: Session = Depends(get_db)
):
    job = db.query(Job).filter(
        Job.id == data.job_id,
        Job.user_id == user.id,
    ).first()

    experience = db.query(Experience).filter(
        Experience.user_id == user.id,
        Experience.status == "ready",
    ).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not experience or not experience.extracted_profile:
        raise HTTPException(status_code=404, detail="No experience found — upload a resume or add a GitHub profile first")

    content = generate_match(experience.extracted_profile, job.extracted_job)
    return {"content": content}
