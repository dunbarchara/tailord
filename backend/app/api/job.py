from fastapi import APIRouter, Depends, Request

from app.auth import require_api_key

from app.core.mvp_llm import extract_job
from app.models.mvp_schemas import JobInput
from app.core.extract import extract_markdown_content
from app.core.playwright_helper import get_rendered_content

import logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/job")
async def create_job(
    data: JobInput,
    request: Request,
    _: str = Depends(require_api_key),
):
    html = await get_rendered_content(data.job_url)
    #logger.debug("\n\n===== RENDERED HTML =====\n" + html)
    markdown_content = extract_markdown_content(html)
    logger.debug("\n\n===== EXTRACTED MARKDOWN =====\n" + markdown_content)
    job = extract_job(markdown_content)
    request.app.state.job_cache["job"] = job
    return {"job": job}

