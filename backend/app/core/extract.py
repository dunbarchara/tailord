import json
import logging
import re

from bs4 import BeautifulSoup
from markdownify import markdownify as md

from app.core.format_text import reduce_newlines_to_two

logger = logging.getLogger(__name__)

# Known ATS platforms and job boards — og:site_name returns these, not the hiring company
_KNOWN_PLATFORMS = {
    "linkedin", "greenhouse", "lever", "workday", "indeed", "glassdoor",
    "smartrecruiters", "jobvite", "bamboohr", "ashby", "rippling",
    "icims", "taleo", "successfactors", "workable", "recruitee",
}


def extract_jsonld(html: str) -> dict:
    """
    Look for schema.org JobPosting JSON-LD blocks and extract title + company.
    Handles both top-level objects and @graph arrays.
    Returns {"title": str|None, "company": str|None}.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        # Normalise to a flat list of objects to check
        candidates: list = []
        if isinstance(data, list):
            candidates = data
        elif isinstance(data, dict):
            if data.get("@type") == "JobPosting":
                candidates = [data]
            else:
                candidates = data.get("@graph", [])

        for item in candidates:
            if not isinstance(item, dict) or item.get("@type") != "JobPosting":
                continue
            title = item.get("title") or item.get("name")
            org = item.get("hiringOrganization") or {}
            company = org.get("name") if isinstance(org, dict) else None
            if title or company:
                result = {
                    "title": title.strip() if title else None,
                    "company": company.strip() if company else None,
                }
                logger.debug("extract_jsonld: found %s", result)
                return result

    return {"title": None, "company": None}


def _strip_platform_suffix(s: str) -> str:
    """Remove trailing ' | Platform' or ' - Platform' from a string."""
    for sep in (" | ", " - ", " – ", " — "):
        idx = s.rfind(sep)
        if idx == -1:
            continue
        suffix = s[idx + len(sep):]
        if suffix.lower().strip() in _KNOWN_PLATFORMS:
            return s[:idx].strip()
    return s


def parse_title_tag(title_str: str) -> dict:
    """
    Parse a <title> tag string into job title and company name.

    Handles patterns like:
      "Senior Engineer at Acme Corp | LinkedIn"
      "Senior Engineer - Acme Corp - Greenhouse"
      "Acme Corp | Senior Engineer"

    Returns {"title": str|None, "company": str|None}.
    """
    s = _strip_platform_suffix(title_str.strip())

    # " at " is the most reliable separator ("Role at Company")
    for sep in (" at ", " @ "):
        lower = s.lower()
        if sep in lower:
            idx = lower.index(sep)
            job_title = s[:idx].strip()
            company = _strip_platform_suffix(s[idx + len(sep):].strip())
            if job_title and company:
                return {"title": job_title, "company": company}

    # Pipe / dash separators — try both orderings
    for sep in (" | ", " - ", " – "):
        if sep in s:
            parts = [p.strip() for p in s.split(sep) if p.strip()]
            if len(parts) >= 2:
                # Heuristic: if the first part looks like a company (short, title-case, no verb-like words)
                # swap — otherwise assume "title | company"
                return {"title": parts[0], "company": parts[1]}

    return {"title": s if s else None, "company": None}


def extract_meta_signals(html: str) -> dict:
    """
    Extract title and company hints from <title> and OpenGraph meta tags.

    og:site_name is intentionally excluded — it returns the platform name
    (LinkedIn, Greenhouse) not the hiring company.

    Returns {"title": str|None, "company": str|None}.
    """
    soup = BeautifulSoup(html, "html.parser")

    page_title = None
    title_tag = soup.find("title")
    if title_tag:
        page_title = title_tag.get_text(strip=True) or None

    og_title = None
    og_tag = soup.find("meta", property="og:title")
    if og_tag:
        og_title = (og_tag.get("content") or "").strip() or None

    result = {"title": None, "company": None}

    if page_title:
        parsed = parse_title_tag(page_title)
        result.update(parsed)

    # og:title is often a clean job title without company suffix — prefer it for
    # the title field if it has no separators (meaning it's just the role name)
    if og_title:
        has_separator = any(sep in og_title for sep in (" at ", " | ", " - ", " – ", " @ "))
        if not result["title"]:
            result["title"] = og_title
        elif not has_separator:
            # Clean og:title with no separators is likely a better title signal
            result["title"] = og_title

    logger.debug("extract_meta_signals: %s", result)
    return result


_BOT_DETECTION_PHRASES = [
    "enable javascript and cookies to continue",
    "checking your browser before accessing",
    "please verify you are a human",
    "ddos protection by cloudflare",
    "just a moment...",
    "cf-browser-verification",
    "access denied",
    "403 forbidden",
]

_JOB_REMOVED_PHRASES = [
    "this job is no longer available",
    "this position has been filled",
    "this job listing has expired",
    "this posting has been removed",
    "job listing has expired",
    "this listing has expired",
    "this job has expired",
    "no longer accepting applications",
    "position has been closed",
    "this position is no longer available",
    "this role is no longer available",
    "this opportunity is no longer available",
    "this requisition is no longer available",
    "this job is not available",
    "this job is closed",
    "position is filled",
    "job is no longer active",
    "job not found",
    "the job you requested was not found",
]

_LOGIN_WALL_PHRASES = [
    "sign in to view this job",
    "log in to view this job",
    "please sign in to continue",
    "create an account to view",
    "sign in to apply",
]

_MIN_CONTENT_LENGTH = 200


def _markdown_plain_text(markdown: str) -> str:
    """Strip markdown syntax to get approximate plain text for length checking.

    Removes image tags, link URLs, heading markers, and bare URLs so that the
    length check reflects readable content, not URL noise embedded in markdown.
    """
    text = markdown
    text = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', text)       # images: ![alt](url)
    text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)   # links: [text](url) -> text
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)  # headings
    text = re.sub(r'https?://\S+', '', text)                # bare URLs
    text = re.sub(r'[*_`~]+', '', text)                     # emphasis/code markers
    return text.strip()


def validate_job_content(markdown: str, html: str | None = None) -> tuple[bool, str]:
    """
    Check whether scraped content looks like a real job posting.

    Phrase checks run against the full HTML text (if provided) so that phrases
    inside elements stripped by extract_markdown_content (nav, header, aside, etc.)
    are still caught. Length check uses the cleaned markdown since that reflects
    what the LLM will actually receive.

    Returns (True, "") if valid, or (False, user_facing_reason) if not.
    """
    md_text = markdown.strip()
    plain_text = _markdown_plain_text(md_text)

    # Extract full visible text from HTML for phrase matching — broader than
    # markdown, which strips nav/header/aside where "Job not found" often lives.
    if html:
        html_soup = BeautifulSoup(html, "html.parser")
        for tag in html_soup(["script", "style", "noscript"]):
            tag.decompose()
        phrase_text = html_soup.get_text(" ", strip=True).lower()
    else:
        phrase_text = plain_text.lower()

    for phrase in _JOB_REMOVED_PHRASES:
        if phrase in phrase_text:
            return False, (
                "That job posting appears to have been removed or has expired. "
                "Check that the URL still points to an active listing."
            )

    if len(plain_text) < _MIN_CONTENT_LENGTH:
        return False, (
            "That page didn't return enough content to extract a job posting. "
            "The URL may have redirected, returned an error, or requires a login."
        )

    for phrase in _BOT_DETECTION_PHRASES:
        if phrase in phrase_text:
            return False, (
                "That job posting is protected by bot detection (e.g. Cloudflare). "
                "Try opening the URL in a browser and copying the direct posting URL."
            )

    for phrase in _LOGIN_WALL_PHRASES:
        if phrase in phrase_text:
            return False, (
                "That job posting requires a login to view. "
                "Try finding a direct link to the posting that doesn't require an account."
            )

    return True, ""


def extract_markdown_content(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["noscript", "script", "style", "header", "footer", "nav", "aside"]):
        tag.decompose()
    markdown_content = md(str(soup), heading_style="ATX")
    return reduce_newlines_to_two(markdown_content)
