import logging

from app.clients.llm_client import get_llm_client
from app.config import settings
from app.core.extract import extract_jsonld, extract_meta_signals
from app.core.llm_utils import llm_parse
from app.prompts import job_extraction as prompt
from app.schemas.llm_outputs import ExtractedJob

logger = logging.getLogger(__name__)


def _extract_hints(html: str) -> dict:
    """
    Deterministic cascade: try JSON-LD first (highest confidence), fall back to
    meta/title tag parsing. Returns {"title": str|None, "company": str|None}.
    """
    hints = extract_jsonld(html)

    if hints["title"] and hints["company"]:
        logger.info("job hints: JSON-LD title=%r company=%r", hints["title"], hints["company"])
        return hints

    meta = extract_meta_signals(html)
    merged = {
        "title": hints["title"] or meta["title"],
        "company": hints["company"] or meta["company"],
    }
    source = "JSON-LD+meta" if hints["title"] or hints["company"] else "meta"
    logger.info("job hints (%s): title=%r company=%r", source, merged["title"], merged["company"])
    return merged


def _format_hints_block(hints: dict) -> str:
    """Format pre-extracted signals for injection into the LLM prompt."""
    parts = []
    if hints.get("title"):
        parts.append(f'title: "{hints["title"]}"')
    if hints.get("company"):
        parts.append(f'company: "{hints["company"]}"')
    if not parts:
        return ""
    lines = "\n".join(parts)
    return (
        f"PRE-EXTRACTED SIGNALS (high-confidence, sourced from page metadata — "
        f"use these for title and company unless the posting clearly contradicts them):\n"
        f"{lines}\n\n"
    )


def extract_job(job_markdown: str, html: str | None = None) -> dict:
    """
    Extract structured job data from the markdown content of a job posting.

    If `html` is provided, runs a deterministic cascade (JSON-LD → meta tags)
    to extract title and company before the LLM call. Pre-found values are
    seeded into the prompt and used as a fallback if the LLM returns null.
    """
    hints: dict = {"title": None, "company": None}
    if html:
        hints = _extract_hints(html)

    hints_block = _format_hints_block(hints)

    client = get_llm_client()
    result = llm_parse(
        client,
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": prompt.SYSTEM},
            {
                "role": "user",
                "content": prompt.USER_TEMPLATE.format(
                    hints_block=hints_block,
                    job_markdown=job_markdown,
                ),
            },
        ],
        response_model=ExtractedJob,
        temperature=prompt.TEMPERATURE,
    )
    data = result.model_dump()

    # Apply deterministic hints as fallback where LLM returned null
    if hints.get("title") and not data.get("title"):
        logger.info("job hints: applying title fallback %r", hints["title"])
        data["title"] = hints["title"]
    if hints.get("company") and not data.get("company"):
        logger.info("job hints: applying company fallback %r", hints["company"])
        data["company"] = hints["company"]

    return data
