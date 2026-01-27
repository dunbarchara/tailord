from fastapi import APIRouter, Depends

from app.auth import require_api_key

from app.core.mvp_github import fetch_repos
from app.core.mvp_llm import extract_profile
from app.services.mvp_profile_store import save_profile
from app.models.mvp_schemas import ProfileInput

from sqlalchemy.orm import Session
from app.models.database import Profile
from app.core.deps_database import get_db

router = APIRouter()
        
@router.post("/profile")
def create_profile(
    data: ProfileInput,
    _: str = Depends(require_api_key),
    db: Session = Depends(get_db)
):
    repos = fetch_repos(data.github_username)
    extracted = extract_profile(data.resume_text, repos)
    
    profile = Profile(
        summary=extracted.get("summary"),
        raw_profile=extracted
    )

    db.add(profile)
    db.commit()
    db.refresh(profile)
    
    return {"profile_id": str(profile.id), "profile": extracted}

