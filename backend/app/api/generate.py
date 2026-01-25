from fastapi import APIRouter, Request
from app.models.mvp_schemas import GeneratedOutput
from app.services.mvp_profile_store import get_profile
from app.core.mvp_llm import generate_match

router = APIRouter()

@router.post("/generate", response_model=GeneratedOutput)
def generate(
    request: Request
):
    profile = get_profile()
    job = request.app.state.job_cache.get("job")

    if not job:
        return {"content": "No job found. Please analyze a job first."}

    content = generate_match(profile, job)
    return {"content": content}

