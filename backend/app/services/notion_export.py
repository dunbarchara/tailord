"""
Notion page creation and update using the native markdown API.

Notion supports passing markdown directly to the pages API — no block
conversion required. Updates use the replace_content command to replace
all page content in a single request.
"""
import logging

import requests

logger = logging.getLogger(__name__)

NOTION_VERSION = "2026-03-11"


def _make_session(access_token: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {access_token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    })
    return session


def create_notion_page(
    access_token: str,
    title: str,
    markdown: str,
) -> tuple[str, str]:
    """
    Create a top-level Notion page from a markdown string.
    Returns (page_id, page_url).
    """
    session = _make_session(access_token)

    res = session.post(
        "https://api.notion.com/v1/pages",
        json={
            "parent": {"type": "workspace", "workspace": True},
            "properties": {"title": [{"text": {"content": title}}]},
            "markdown": markdown,
        },
    )
    if res.status_code != 200:
        logger.error("Notion page creation failed: %s %s", res.status_code, res.text)
        raise ValueError(f"Notion API error {res.status_code}: {res.json().get('message', res.text)}")

    page = res.json()
    return page["id"], page["url"]


def update_notion_page(
    access_token: str,
    page_id: str,
    title: str,
    markdown: str,
) -> bool:
    """
    Update an existing Notion page — refresh title and replace all content.
    Returns True on success, False if the page is inaccessible (deleted/revoked).
    """
    session = _make_session(access_token)

    # Update title
    title_res = session.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        json={"properties": {"title": [{"text": {"content": title}}]}},
    )
    if title_res.status_code != 200:
        logger.warning("Notion page %s inaccessible (%s), will create new", page_id, title_res.status_code)
        return False

    # Replace all content
    content_res = session.patch(
        f"https://api.notion.com/v1/pages/{page_id}/markdown",
        json={
            "type": "replace_content",
            "replace_content": {"new_str": markdown},
        },
    )
    if content_res.status_code != 200:
        logger.error("Notion content replace failed: %s %s", content_res.status_code, content_res.text)
        return False

    return True
