from fastapi import APIRouter, Depends, Request

from app.auth import require_api_key

from app.core.mvp_llm import extract_job
from app.models.mvp_schemas import JobInput
from app.core.extract import extract_markdown_content
from app.core.playwright_helper import get_rendered_content

from app.models.database import Job
from app.core.deps_database import get_db
from sqlalchemy.orm import Session

import logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/job")
async def create_job(
    data: JobInput,
    request: Request,
    _: str = Depends(require_api_key),
    db: Session = Depends(get_db)
):
    html = await get_rendered_content(data.job_url)
    #logger.debug("\n\n===== RENDERED HTML =====\n" + html)
    markdown_content = extract_markdown_content(html)
    logger.debug("\n\n===== EXTRACTED MARKDOWN =====\n" + markdown_content)
    extracted = extract_job(markdown_content)

    job = Job(
        job_url=data.job_url,
        extracted_job=extracted
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    return {"job_id": str(job.id), "job": extracted}

