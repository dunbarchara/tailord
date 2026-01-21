from app.core.fetch import fetch_html
from app.core.extract import extract_deterministic, extract_markdown_content
from app.core.llm_job_parser import extract_semantic
from app.core.playwright_helper import get_rendered_content
from app.core.merge import deep_merge
from app.models.job_posting import JobPosting
import logging
logger = logging.getLogger(__name__)

async def parse_job(url: str) -> JobPosting:
    html = await get_rendered_content(url)
    logger.debug("\n\n===== RENDERED HTML =====\n" + html)
    base = extract_deterministic(html, url)
    markdown_content = extract_markdown_content(html)
    logger.debug("\n\n===== EXTRACTED MARKDOWN =====\n" + markdown_content)
    semantic = extract_semantic(markdown_content)
    merged = deep_merge(base, semantic)

    return JobPosting.model_validate(merged)
