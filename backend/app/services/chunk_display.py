"""
Shared display rules for job chunks.

Both the API serialisation layer (tailorings.py) and the Notion export service
(notion_export.py) use these to ensure the Posting view and the Notion Posting
page apply identical filtering and labelling logic.
"""

import re

_NOISE_PATTERN = re.compile(r"^(\[.+\]\(.+\)|!\[.*\]\(.+\))$")

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
    - chunks without a section belong to pre-content job metadata
    - chunks whose entire content is a bare markdown link/image are noise
    """
    if chunk.chunk_type == "header":
        return False
    if chunk.section is None:
        return False
    if _NOISE_PATTERN.match(chunk.content.strip()):
        return False
    return True
