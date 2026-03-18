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
import requests

logger = logging.getLogger(__name__)

NOTION_VERSION = "2022-06-28"
NOTION_BLOCKS_LIMIT = 100  # Notion max children per request


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
# Notion API — page creation
# ---------------------------------------------------------------------------

def create_notion_page(
    access_token: str,
    title: str,
    blocks: list[dict],
) -> str:
    """
    Create a top-level Notion page with the given title and blocks.
    Handles the 100-block-per-request limit by appending in batches.
    Returns the URL of the created page.
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

    # Create the page with up to 100 blocks
    first_batch = blocks[:NOTION_BLOCKS_LIMIT]
    payload = {
        "parent": {"type": "workspace", "workspace": True},
        "properties": {
            "title": [{"text": {"content": title}}],
        },
        "children": first_batch,
    }

    res = requests.post("https://api.notion.com/v1/pages", headers=headers, json=payload)
    if res.status_code != 200:
        logger.error("Notion page creation failed: %s %s", res.status_code, res.text)
        raise ValueError(f"Notion API error {res.status_code}: {res.json().get('message', res.text)}")

    page = res.json()
    page_id = page["id"]
    page_url = page["url"]

    # Append remaining blocks in batches of 100
    remaining = blocks[NOTION_BLOCKS_LIMIT:]
    while remaining:
        batch = remaining[:NOTION_BLOCKS_LIMIT]
        remaining = remaining[NOTION_BLOCKS_LIMIT:]
        append_res = requests.patch(
            f"https://api.notion.com/v1/blocks/{page_id}/children",
            headers=headers,
            json={"children": batch},
        )
        if append_res.status_code != 200:
            logger.error("Notion block append failed: %s %s", append_res.status_code, append_res.text)
            # Page was created — return URL even if append partially failed
            break

    return page_url
