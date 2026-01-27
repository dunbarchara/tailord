from fastapi import APIRouter, Request, Depends
from app.models.mvp_schemas import GenerateInput, GeneratedOutput
from app.services.mvp_profile_store import get_profile
from app.core.mvp_llm import generate_match

from sqlalchemy.orm import Session
from app.models.database import Job, Profile
from app.core.deps_database import get_db

router = APIRouter()

@router.post("/generate", response_model=GeneratedOutput)
def generate(
    data: GenerateInput,
    request: Request,
    db: Session = Depends(get_db)
):
    job = db.get(Job, data.job_id)
    profile = db.query(Profile).order_by(Profile.updated_at.desc()).first()

    if not job or not profile:
        return {"content": "Missing job or profile"}

    content = generate_match(profile.raw_profile, job.extracted_job)
    return {"content": content}

