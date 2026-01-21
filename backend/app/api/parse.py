from fastapi import APIRouter, HTTPException, Depends
from app.models.request import RequestURL
from app.models.job_posting import JobPosting
from app.services.parser import parse_job

from app.auth import require_api_key

router = APIRouter()

@router.post("/parse", response_model=JobPosting)
async def parse(
    req: RequestURL,
    _: str = Depends(require_api_key),
):
    #try:
        job = await parse_job(str(req.url))
        return job.model_dump()
    #except Exception as e:
        #raise HTTPException(status_code=400, detail=str(e))