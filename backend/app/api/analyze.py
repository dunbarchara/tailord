from fastapi import APIRouter, Depends
from app.models.request import RequestURL
from app.models.v1_request_response import AnalyzeResponse
from app.core.scraper import extract_job_text
from app.core.llm_job_analyzer import analyze_job
from app.auth import require_api_key

router = APIRouter()

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    req: RequestURL,
    _: str = Depends(require_api_key),
):
    text = await extract_job_text(str(req.url))
    return analyze_job(text)
