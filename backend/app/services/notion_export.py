"""
Markdown → Notion blocks converter + Notion page creation.

Handles the subset of Markdown that the tailoring template produces:
  # h1 / ## h2 / ### h3
  --- (divider)
  - bullet / * bullet
  **bold** / *italic* / ***bold italic***
  plain paragraphs
"""
import re
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

logger = logging.getLogger(__name__)

NOTION_VERSION = "2022-06-28"
NOTION_BLOCKS_LIMIT = 100  # Notion max children per request
DELETE_WORKERS = 8          # Parallel DELETE threads


# ---------------------------------------------------------------------------
# Rich-text inline parsing
# ---------------------------------------------------------------------------

def _text_segment(content: str, bold: bool = False, italic: bool = False) -> dict:
    return {
        "type": "text",
        "text": {"content": content},
        "annotations": {
            "bold": bold,
            "italic": italic,
            "strikethrough": False,
            "underline": False,
            "code": False,
            "color": "default",
        },
    }


def _parse_inline(text: str) -> list[dict]:
    """Parse **bold**, *italic*, ***bold italic*** into Notion rich_text segments."""
    segments = []
    pattern = re.compile(r'\*\*\*(.+?)\*\*\*|\*\*(.+?)\*\*|\*(.+?)\*')
    last = 0
    for m in pattern.finditer(text):
        if m.start() > last:
            segments.append(_text_segment(text[last:m.start()]))
        if m.group(1):
            segments.append(_text_segment(m.group(1), bold=True, italic=True))
        elif m.group(2):
            segments.append(_text_segment(m.group(2), bold=True))
        elif m.group(3):
            segments.append(_text_segment(m.group(3), italic=True))
        last = m.end()
    if last < len(text):
        segments.append(_text_segment(text[last:]))
    return segments or [_text_segment(text)]


# ---------------------------------------------------------------------------
# Block constructors
# ---------------------------------------------------------------------------

def _heading_block(level: int, text: str) -> dict:
    block_type = f"heading_{level}"
    return {
        "object": "block",
        "type": block_type,
        block_type: {"rich_text": _parse_inline(text.strip())},
    }


def _paragraph_block(text: str) -> dict:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": _parse_inline(text)},
    }


def _bullet_block(text: str) -> dict:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": _parse_inline(text.strip())},
    }


def _divider_block() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}


# ---------------------------------------------------------------------------
# Main converter
# ---------------------------------------------------------------------------

def markdown_to_notion_blocks(md: str) -> list[dict]:
    blocks = []
    for line in md.splitlines():
        if line.startswith("### "):
            blocks.append(_heading_block(3, line[4:]))
        elif line.startswith("## "):
            blocks.append(_heading_block(2, line[3:]))
        elif line.startswith("# "):
            blocks.append(_heading_block(1, line[2:]))
        elif re.match(r'^-{3,}$', line.strip()):
            blocks.append(_divider_block())
        elif line.startswith("- ") or line.startswith("* "):
            blocks.append(_bullet_block(line[2:]))
        elif line.strip() == "":
            continue
        else:
            blocks.append(_paragraph_block(line))
    return blocks


# ---------------------------------------------------------------------------
# Notion API — session-based helpers
# ---------------------------------------------------------------------------

def _make_session(access_token: str) -> requests.Session:
    """Create a session with keep-alive and Notion auth headers."""
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {access_token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    })
    return session


def _append_blocks(session: requests.Session, page_id: str, blocks: list[dict]) -> None:
    """Append blocks to a page in batches of 100, reusing the session connection."""
    for i in range(0, len(blocks), NOTION_BLOCKS_LIMIT):
        batch = blocks[i:i + NOTION_BLOCKS_LIMIT]
        res = session.patch(
            f"https://api.notion.com/v1/blocks/{page_id}/children",
            json={"children": batch},
        )
        if res.status_code != 200:
            logger.error("Notion block append failed: %s %s", res.status_code, res.text)
            break


def _clear_page_blocks(session: requests.Session, page_id: str) -> None:
    """
    Archive all existing child blocks on a page.
    Fetches block IDs sequentially (must be serial), then deletes in parallel.
    """
    block_ids: list[str] = []
    cursor = None

    while True:
        params: dict = {"page_size": 100}
        if cursor:
            params["start_cursor"] = cursor
        res = session.get(
            f"https://api.notion.com/v1/blocks/{page_id}/children",
            params=params,
        )
        if res.status_code != 200:
            logger.warning("Could not fetch blocks to clear: %s", res.status_code)
            return
        data = res.json()
        block_ids.extend(b["id"] for b in data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")

    if not block_ids:
        return

    # Delete all blocks in parallel — each uses the shared session (connection reuse)
    def delete_block(block_id: str) -> None:
        session.delete(f"https://api.notion.com/v1/blocks/{block_id}")

    with ThreadPoolExecutor(max_workers=DELETE_WORKERS) as pool:
        futures = {pool.submit(delete_block, bid): bid for bid in block_ids}
        for future in as_completed(futures):
            future.result()  # surface any exceptions

    logger.debug("Cleared %d blocks from Notion page %s", len(block_ids), page_id)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def update_notion_page(
    access_token: str,
    page_id: str,
    title: str,
    blocks: list[dict],
) -> bool:
    """
    Update an existing Notion page — refresh title and replace all blocks.
    Returns True on success, False if the page is inaccessible (deleted/revoked).
    """
    session = _make_session(access_token)

    res = session.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        json={"properties": {"title": [{"text": {"content": title}}]}},
    )
    if res.status_code != 200:
        logger.warning("Notion page %s inaccessible (%s), will create new", page_id, res.status_code)
        return False

    _clear_page_blocks(session, page_id)
    _append_blocks(session, page_id, blocks)
    return True


def create_notion_page(
    access_token: str,
    title: str,
    blocks: list[dict],
) -> tuple[str, str]:
    """
    Create a top-level Notion page with the given title and blocks.
    Returns (page_id, page_url).
    """
    session = _make_session(access_token)

    res = session.post(
        "https://api.notion.com/v1/pages",
        json={
            "parent": {"type": "workspace", "workspace": True},
            "properties": {"title": [{"text": {"content": title}}]},
            "children": blocks[:NOTION_BLOCKS_LIMIT],
        },
    )
    if res.status_code != 200:
        logger.error("Notion page creation failed: %s %s", res.status_code, res.text)
        raise ValueError(f"Notion API error {res.status_code}: {res.json().get('message', res.text)}")

    page = res.json()
    page_id = page["id"]
    page_url = page["url"]

    if len(blocks) > NOTION_BLOCKS_LIMIT:
        _append_blocks(session, page_id, blocks[NOTION_BLOCKS_LIMIT:])

    return page_id, page_url
