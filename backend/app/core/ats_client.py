"""Direct ATS API client for Greenhouse and Lever job postings.

Fetches structured job data from public ATS APIs without relying on Playwright,
bypassing JS-embed hydration timing issues (e.g. Greenhouse-embedded career pages).
"""

import logging
import re
from urllib.parse import parse_qs, urlparse

import requests

from app.core.extract import extract_markdown_content

logger = logging.getLogger(__name__)

_ATS_FETCH_TIMEOUT = 10  # seconds


def _parse_greenhouse_url(url: str) -> tuple[str, str] | None:
    """Return (board_token, job_id) or None if not a Greenhouse URL.

    Handles three patterns:
    1. Any domain with ?gh_jid=JOB_ID&board=BOARD_TOKEN (e.g. coreweave.com/careers/job?gh_jid=...)
    2. boards.greenhouse.io/BOARD/jobs/JOB_ID
    3. job-boards.greenhouse.io/BOARD/jobs/JOB_ID
    """
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)

    # Pattern 1: gh_jid + board query params (embedded on any company site)
    if "gh_jid" in qs and "board" in qs:
        job_id = qs["gh_jid"][0]
        board_token = qs["board"][0]
        if job_id and board_token:
            return board_token, job_id

    # Patterns 2 & 3: Greenhouse-hosted domains
    host = parsed.hostname or ""
    if host in ("boards.greenhouse.io", "job-boards.greenhouse.io"):
        # Path: /BOARD/jobs/JOB_ID
        match = re.match(r"^/([^/]+)/jobs/(\d+)", parsed.path)
        if match:
            return match.group(1), match.group(2)

    return None


def _parse_lever_url(url: str) -> tuple[str, str] | None:
    """Return (company, job_id) or None if not a Lever URL.

    Handles: jobs.lever.co/COMPANY/UUID
    """
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if host != "jobs.lever.co":
        return None

    # Path: /COMPANY/UUID
    match = re.match(r"^/([^/]+)/([^/]+)/?$", parsed.path)
    if match:
        return match.group(1), match.group(2)

    return None


def _greenhouse_to_markdown(data: dict) -> str:
    """Convert a Greenhouse job API response to markdown."""
    parts: list[str] = []

    title = data.get("title", "").strip()
    if title:
        parts.append(f"# {title}")

    location = (data.get("location") or {}).get("name", "").strip()
    if location:
        parts.append(f"**Location:** {location}")

    content_html = data.get("content", "")
    if content_html:
        content_md = extract_markdown_content(content_html)
        if content_md:
            parts.append(content_md)

    return "\n\n".join(parts)


def _lever_to_markdown(data: dict) -> str:
    """Convert a Lever posting API response to markdown."""
    parts: list[str] = []

    title = data.get("text", "").strip()
    if title:
        parts.append(f"# {title}")

    categories = data.get("categories") or {}
    team = categories.get("team", "").strip()
    location = categories.get("location", "").strip()
    if team or location:
        meta = " | ".join(p for p in [team, location] if p)
        parts.append(f"**{meta}**")

    description_plain = (data.get("descriptionPlain") or "").strip()
    if description_plain:
        parts.append(description_plain)

    for section in data.get("lists") or []:
        section_title = (section.get("text") or "").strip()
        section_content_html = section.get("content") or ""
        if section_title:
            parts.append(f"## {section_title}")
        if section_content_html:
            section_md = extract_markdown_content(section_content_html)
            if section_md:
                parts.append(section_md)

    return "\n\n".join(parts)


def try_ats_fetch(url: str) -> str | None:
    """Try fetching job data from Greenhouse or Lever public APIs.

    Returns markdown string on success, None on any failure or if the URL
    is not a recognized ATS pattern. Never raises.
    """
    try:
        gh = _parse_greenhouse_url(url)
        if gh:
            board_token, job_id = gh
            api_url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}?questions=false"
            logger.info("try_ats_fetch: Greenhouse API %s", api_url)
            resp = requests.get(api_url, timeout=_ATS_FETCH_TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                markdown = _greenhouse_to_markdown(data)
                if markdown.strip():
                    logger.info(
                        "try_ats_fetch: Greenhouse fetch succeeded (%d chars)", len(markdown)
                    )
                    return markdown
            else:
                logger.warning(
                    "try_ats_fetch: Greenhouse API returned %d for %s", resp.status_code, api_url
                )
            return None

        lv = _parse_lever_url(url)
        if lv:
            company, job_id = lv
            api_url = f"https://api.lever.co/v0/postings/{company}/{job_id}"
            logger.info("try_ats_fetch: Lever API %s", api_url)
            resp = requests.get(api_url, timeout=_ATS_FETCH_TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                markdown = _lever_to_markdown(data)
                if markdown.strip():
                    logger.info("try_ats_fetch: Lever fetch succeeded (%d chars)", len(markdown))
                    return markdown
            else:
                logger.warning(
                    "try_ats_fetch: Lever API returned %d for %s", resp.status_code, api_url
                )
            return None

    except Exception:
        logger.warning("try_ats_fetch: failed for %s", url, exc_info=True)

    return None
