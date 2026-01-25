from fastapi import APIRouter, Depends

from app.auth import require_api_key

from app.core.mvp_github import fetch_repos
from app.core.mvp_llm import extract_profile
from app.services.mvp_profile_store import save_profile
from app.models.mvp_schemas import ProfileInput

router = APIRouter()
        
@router.post("/profile")
def create_profile(
    data: ProfileInput,
    _: str = Depends(require_api_key),
):
    repos = fetch_repos(data.github_username)
    profile = extract_profile(data.resume_text, repos)
    save_profile(profile)
    return {"profile": profile}

