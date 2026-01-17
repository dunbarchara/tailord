from fastapi import APIRouter, Depends
from app.models import AnalyzeRequest, AnalyzeResponse
from app.scraper import extract_job_text
from app.analyzer import analyze_job
from app.auth import require_api_key

router = APIRouter()

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    req: AnalyzeRequest,
    _: str = Depends(require_api_key),
):
    text = await extract_job_text(str(req.url))
    return analyze_job(text)
