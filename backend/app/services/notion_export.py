"""
Notion page creation and update using the native markdown API.

Page hierarchy:
  Tailord - Tailorings  (workspace root, one per user)
    └─ {Job Title — Company}  (per-tailoring container)
        ├─ Posting  (primary — created first to hold top position)
        └─ Letter
"""

import logging
import re

import requests

from app.services.chunk_display import SOURCE_LABELS as _SOURCE_LABELS
from app.services.chunk_display import is_display_ready

logger = logging.getLogger(__name__)


class NotionAuthError(Exception):
    """Raised when Notion returns 401 — the user has revoked the integration's access."""

    pass


NOTION_VERSION = "2026-03-11"
PARENT_PAGE_TITLE = "Tailord - Tailorings"
TAILORD_ICON = {"type": "external", "external": {"url": "https://tailord.app/tailordicon.png"}}

_ESCAPE_RE = re.compile(r"([\\~`\[\]<>{}|^])")
_FORMATTING_RE = re.compile(r"\*+")
_LINK_RE = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")


def _escape(text: str) -> str:
    """Escape Notion enhanced markdown special characters, preserving bold/italic (*).."""
    return _ESCAPE_RE.sub(r"\\\1", text)


def _strip_links(text: str) -> str:
    """Replace markdown links [text](url) and images ![alt](url) with their inner text."""
    return _LINK_RE.sub(r"\1", text)


def _strip_formatting(text: str) -> str:
    """Remove markdown bold/italic markers (e.g. **Section**) from plain text."""
    return _FORMATTING_RE.sub("", text).strip()


def chunks_to_notion_markdown(chunks: list) -> str:
    """
    Convert enriched job chunks to Notion enhanced markdown (public mode):
    - chunk_type='header' chunks are skipped (section field is used as the heading)
    - score=0 (gap) chunks are omitted
    - score=2 (strong) → green_bg toggle with advocacy blurb + source
    - score=1 (partial) → yellow_bg toggle with advocacy blurb + source
    - score=-1 or None (N/A) → plain bullet or paragraph, no toggle
    """
    lines = []
    current_section = None

    for chunk in chunks:
        if not is_display_ready(chunk):
            continue

        score = chunk.match_score

        # Omit gaps (public mode)
        if score == 0:
            continue

        section = chunk.section
        if section != current_section:
            if lines:
                lines.append("")
            lines.append(f"## {_strip_formatting(section)}")
            lines.append("")
        current_section = section

        content = _escape(_strip_links(chunk.content.strip()))

        # N/A chunks (not scorable) render as plain text — no toggle
        if score is None or score == -1:
            if chunk.chunk_type == "bullet":
                lines.append(f"- {content}")
            else:
                lines.append(content)
            lines.append("")
            continue

        # Scored chunks render as toggles
        if score == 2:
            color_attr = ' color="green_bg"'
        elif score == 1:
            color_attr = ' color="yellow_bg"'
        else:
            color_attr = ""

        lines.append(f"<details{color_attr}>")
        lines.append(f"<summary>{content}</summary>")

        if chunk.advocacy_blurb or chunk.experience_source:
            lines.append('\t<callout color="gray_bg">')
            if chunk.advocacy_blurb:
                advocacy = _escape(_strip_links(chunk.advocacy_blurb.strip()))
                lines.append(f"\t\t{advocacy}")
            if chunk.advocacy_blurb and chunk.experience_source:
                lines.append("\t\t---")
            if chunk.experience_source:
                label = _SOURCE_LABELS.get(chunk.experience_source, chunk.experience_source)
                lines.append(f"\t\t*Source: {label}*")
            lines.append("\t</callout>")

        lines.append("</details>")
        lines.append("")

    return "\n".join(lines)


def _make_session(access_token: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {access_token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }
    )
    return session


def _get_or_create_page(
    session: requests.Session,
    existing_id: str | None,
    parent: dict,
    title: str,
    log_label: str,
    markdown: str | None = None,
) -> tuple[str, str]:
    """
    Verify an existing page is accessible (by patching its title) or create a new one.
    Returns (page_id, page_url).
    """
    if existing_id:
        res = session.patch(
            f"https://api.notion.com/v1/pages/{existing_id}",
            json={"properties": {"title": [{"text": {"content": title}}]}},
        )
        if res.status_code == 401:
            raise NotionAuthError("Notion access revoked")
        if res.status_code == 200:
            return existing_id, res.json().get("url", "")
        logger.warning(
            "Notion %s %s inaccessible (%s), creating new", log_label, existing_id, res.status_code
        )

    body: dict = {
        "parent": parent,
        "icon": TAILORD_ICON,
        "properties": {"title": [{"text": {"content": title}}]},
    }
    if markdown is not None:
        body["markdown"] = markdown

    res = session.post("https://api.notion.com/v1/pages", json=body)
    if res.status_code == 401:
        raise NotionAuthError("Notion access revoked")
    if res.status_code != 200:
        logger.error("Notion %s creation failed: %s %s", log_label, res.status_code, res.text)
        raise ValueError(
            f"Notion API error {res.status_code}: {res.json().get('message', res.text)}"
        )

    page = res.json()
    logger.info("Created Notion %s %s", log_label, page["id"])
    return page["id"], page["url"]


_PARENT_PAGE_DESCRIPTION = (
    "Tailorings exported from [**Tailord**](https://tailord.app/) — "
    "your advocacy letters and job posting analyses, one page per position."
)


def get_or_create_parent_page(
    access_token: str,
    existing_parent_page_id: str | None,
) -> str:
    """
    Return the ID of the workspace-level 'Tailord - Tailorings' container page.
    """
    session = _make_session(access_token)
    page_id, _ = _get_or_create_page(
        session=session,
        existing_id=existing_parent_page_id,
        parent={"type": "workspace", "workspace": True},
        title=PARENT_PAGE_TITLE,
        log_label="parent page",
        markdown=_PARENT_PAGE_DESCRIPTION,
    )
    return page_id


def get_or_create_tailoring_container(
    access_token: str,
    parent_page_id: str,
    existing_container_id: str | None,
    title: str,
    tailoring_id: str | None = None,
    job_title: str | None = None,
    company: str | None = None,
    job_url: str | None = None,
) -> str:
    """
    Return the ID of the per-tailoring container page nested under parent_page_id.
    """
    lines = []

    if job_title or company:
        position = f"**{job_title}**" if job_title else None
        org = f"**{company}**" if company else None
        heading = " at ".join(p for p in [position, org] if p)
        lines.append(f"[{heading}]({job_url})" if job_url else heading)

    lines.append(
        "\nThis page contains your Tailord-generated materials for this position — "
        "your advocacy letter and an experience-matched analysis of the job posting."
    )

    if tailoring_id:
        tailord_url = f"https://tailord.app/dashboard/tailorings/{tailoring_id}"
        lines.append(f"[Open this tailoring in Tailord →]({tailord_url})")

    session = _make_session(access_token)
    container_id, _ = _get_or_create_page(
        session=session,
        existing_id=existing_container_id,
        parent={"type": "page_id", "page_id": parent_page_id},
        title=title,
        log_label="tailoring container",
        markdown="\n".join(lines) if lines else None,
    )
    return container_id


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
    return _get_or_create_page(
        session=session,
        existing_id=None,
        parent={"type": "page_id", "page_id": parent_page_id},
        title=title,
        log_label="content page",
        markdown=markdown,
    )


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
    if title_res.status_code == 401:
        raise NotionAuthError("Notion access revoked")
    if title_res.status_code != 200:
        logger.warning(
            "Notion page %s inaccessible (%s), will create new", page_id, title_res.status_code
        )
        return False

    content_res = session.patch(
        f"https://api.notion.com/v1/pages/{page_id}/markdown",
        json={
            "type": "replace_content",
            "replace_content": {"new_str": markdown},
        },
    )
    if content_res.status_code != 200:
        logger.error(
            "Notion content replace failed: %s %s", content_res.status_code, content_res.text
        )
        return False

    return True
