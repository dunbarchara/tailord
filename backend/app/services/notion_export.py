"""
Notion page creation and update using the native markdown API.

All tailoring pages are created as sub-pages of a shared 'Tailord - Tailorings'
container page. The container is created on first export and its ID is stored on
the User record so subsequent exports reuse it.
"""
import logging

import requests

logger = logging.getLogger(__name__)

NOTION_VERSION = "2026-03-11"
PARENT_PAGE_TITLE = "Tailord - Tailorings"
TAILORD_ICON = {"type": "external", "external": {"url": "https://tailord.app/tailordicon.png"}}


def _make_session(access_token: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {access_token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    })
    return session


def get_or_create_parent_page(
    access_token: str,
    existing_parent_page_id: str | None,
) -> str:
    """
    Return the ID of the 'Tailord - Tailorings' container page.

    If existing_parent_page_id is provided and still accessible, return it.
    Otherwise create a new workspace-level container page and return its ID.
    """
    session = _make_session(access_token)

    if existing_parent_page_id:
        res = session.patch(
            f"https://api.notion.com/v1/pages/{existing_parent_page_id}",
            json={"properties": {"title": [{"text": {"content": PARENT_PAGE_TITLE}}]}},
        )
        if res.status_code == 200:
            return existing_parent_page_id
        logger.warning(
            "Notion parent page %s inaccessible (%s), creating new one",
            existing_parent_page_id, res.status_code,
        )

    res = session.post(
        "https://api.notion.com/v1/pages",
        json={
            "parent": {"type": "workspace", "workspace": True},
            "icon": TAILORD_ICON,
            "properties": {"title": [{"text": {"content": PARENT_PAGE_TITLE}}]},
        },
    )
    if res.status_code != 200:
        logger.error("Notion parent page creation failed: %s %s", res.status_code, res.text)
        raise ValueError(f"Notion API error {res.status_code}: {res.json().get('message', res.text)}")

    page_id = res.json()["id"]
    logger.info("Created Notion parent page %s", page_id)
    return page_id


def create_notion_page(
    access_token: str,
    parent_page_id: str,
    title: str,
    markdown: str,
) -> tuple[str, str]:
    """
    Create a Notion sub-page under parent_page_id from a markdown string.
    Returns (page_id, page_url).
    """
    session = _make_session(access_token)

    res = session.post(
        "https://api.notion.com/v1/pages",
        json={
            "parent": {"type": "page_id", "page_id": parent_page_id},
            "icon": TAILORD_ICON,
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

    title_res = session.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        json={"properties": {"title": [{"text": {"content": title}}]}},
    )
    if title_res.status_code != 200:
        logger.warning("Notion page %s inaccessible (%s), will create new", page_id, title_res.status_code)
        return False

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
