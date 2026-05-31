"""
Shared display rules for job chunks.

Both the API serialisation layer (tailorings.py) and the Notion export service
(notion_export.py) use these to ensure the Posting view and the Notion Posting
page apply identical filtering and labelling logic.
"""

import re

_NOISE_PATTERN = re.compile(r"^(\[[^\]]+\]\([^)]+\)|!\[[^\]]*\]\([^)]+\))$")

SOURCE_LABELS: dict[str, str] = {
    "resume": "Resume",
    "github": "GitHub",
    "user_input": "Additional context",
}


def is_display_ready(chunk) -> bool:
    """
    Return True if a chunk should appear in the Posting view.

    Rules (mirrors JobPosting.groupBySection in the frontend):
    - header-type chunks are structural, not displayable
    - chunks outside the job content bounds (excluded_reason set) are page chrome, not job content
    - chunks whose entire content is a bare markdown link/image are noise

    NOTE: section is intentionally NOT checked here. Some in-bounds content (e.g. overview
    paragraphs on postings that use bold text instead of ## headings) is sectionless but still
    real job content. The authoritative signal for "outside job content" is excluded_reason,
    set by the LLM bounds detector.
    """
    if chunk.chunk_type == "header":
        return False
    if getattr(chunk, "excluded_reason", None) in ("pre_content", "post_content"):
        return False
    if _NOISE_PATTERN.match(chunk.content.strip()):
        return False
    return True
