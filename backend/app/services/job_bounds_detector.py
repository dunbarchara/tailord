import re

import structlog
from pydantic import BaseModel

import app.prompts.job_bounds as prompt
from app.clients.llm_client import get_llm_client
from app.config import settings
from app.core.llm_utils import llm_parse_with_retry

logger = structlog.get_logger(__name__)


class JobContentBounds(BaseModel):
    start_anchor: str | None = None
    end_anchor: str | None = None


def detect_job_content_bounds(markdown: str) -> JobContentBounds:
    """
    One focused LLM call to identify where job description content starts and ends.

    Returns semantic anchor substrings (verbatim text, not line numbers) that can
    be located in the markdown via str.find() / str.rfind(). Falls back to
    JobContentBounds() (both anchors null — use full markdown) on any failure.
    """
    client = get_llm_client()
    messages = [
        {"role": "system", "content": prompt.SYSTEM},
        {"role": "user", "content": prompt.USER_TEMPLATE.format(markdown=markdown)},
    ]
    try:
        bounds = llm_parse_with_retry(
            client,
            settings.llm_model,
            messages,
            response_model=JobContentBounds,
            temperature=prompt.TEMPERATURE,
            max_retries=1,
            prompt_name=prompt.PROMPT_NAME,
        )
        logger.info(
            "job_bounds_detected",
            has_start=bounds.start_anchor is not None,
            has_end=bounds.end_anchor is not None,
        )
        return bounds
    except Exception:
        logger.warning("job_bounds_detection_failed — using full markdown")
        return JobContentBounds()


def _anchor_pattern(anchor: str) -> re.Pattern[str]:
    """
    Build a regex that matches anchor text regardless of whitespace variation.

    The LLM sometimes collapses newlines and multi-space runs to a single space
    when copying anchor text from the markdown (e.g. "About Nominal Nominal is…"
    instead of "About Nominal\nNominal is…"). We escape the individual words and
    join them with \\s+ so any whitespace sequence matches.
    """
    words = anchor.split()
    return re.compile(r"\s+".join(re.escape(w) for w in words))


def apply_bounds(markdown: str, bounds: JobContentBounds) -> tuple[str, str, str]:
    """
    Split markdown into (pre_content, core_content, post_content) using anchor substrings.

    Matching is whitespace-normalized: the LLM may collapse newlines in the anchor,
    so each whitespace run in the anchor matches any whitespace in the markdown.

    - start_anchor: first match → everything before is pre_content.
    - end_anchor: last match in remaining text → everything after is post_content.
    - If an anchor is not found, logs a warning and skips that split.

    Returns ("", markdown, "") when both anchors are absent or not found.
    """
    remaining = markdown
    pre = ""

    if bounds.start_anchor:
        pattern = _anchor_pattern(bounds.start_anchor)
        m = pattern.search(remaining)
        if m:
            pre = remaining[: m.start()]
            remaining = remaining[m.start() :]
        else:
            logger.warning(
                "job_bounds_start_anchor_not_found",
                anchor_preview=bounds.start_anchor[:60],
            )

    if bounds.end_anchor:
        pattern = _anchor_pattern(bounds.end_anchor)
        matches = list(pattern.finditer(remaining))
        if matches:
            last = matches[-1]
            core = remaining[: last.end()]
            post = remaining[last.end() :]
        else:
            logger.warning(
                "job_bounds_end_anchor_not_found",
                anchor_preview=bounds.end_anchor[:60],
            )
            core = remaining
            post = ""
    else:
        core = remaining
        post = ""

    return pre, core, post
