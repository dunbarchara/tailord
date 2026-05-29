import logging
import random
import re

import httpx
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

# Hard ceiling on the initial page navigation.
_GOTO_TIMEOUT_MS = 60_000

# Extra wait for JS-rendered content to settle after the load event. Non-fatal:
# many sites have persistent analytics XHR that prevent ever reaching "networkidle".
# If this times out we log a warning and use whatever DOM is already available.
_NETWORKIDLE_TIMEOUT_MS = 10_000

# httpx timeout for the fetch-first attempt.
_HTTPX_TIMEOUT_S = 15

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/139.0",
]

_FETCH_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

# SPA patterns: a nearly-empty body that is just a single mount point.
_SPA_PATTERN = re.compile(
    r"<body[^>]*>\s*(<noscript[^>]*>.*?</noscript>\s*)?<div\s+id=[\"'](root|app|main|__next)[\"'][^>]*>\s*</div>\s*</body>",
    re.IGNORECASE | re.DOTALL,
)


async def _fetch_with_httpx(url: str) -> str:
    """Plain HTTPS GET with browser-like headers. Returns decoded HTML."""
    headers = {**_FETCH_HEADERS, "User-Agent": random.choice(_USER_AGENTS)}
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=_HTTPX_TIMEOUT_S,
    ) as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.text


def _needs_browser(html: str) -> bool:
    """Return True if the HTML looks like it needs JS rendering to be useful."""
    # Very short body → SPA mount point with no server-rendered content
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    body = soup.find("body")
    if body:
        visible_text = body.get_text(" ", strip=True)
        if len(visible_text) < 500:
            return True

    # Explicit SPA shell pattern
    if _SPA_PATTERN.search(html):
        return True

    return False


async def get_html_content(url: str) -> str:
    """Fetch HTML for a job URL. Tries plain httpx first; falls back to Playwright."""
    try:
        html = await _fetch_with_httpx(url)
        if not _needs_browser(html):
            logger.info("httpx_fetch_success", extra={"url": url})
            return html
        logger.debug("httpx_fetch_needs_browser: falling through to Playwright for %s", url)
    except Exception:
        logger.debug("httpx_fetch_failed: falling through to Playwright for %s", url, exc_info=True)
    return await get_rendered_content(url)


async def get_rendered_content(url: str) -> str:
    browser = None
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(user_agent=random.choice(_USER_AGENTS))
            await page.goto(url, timeout=_GOTO_TIMEOUT_MS)
            try:
                await page.wait_for_load_state("networkidle", timeout=_NETWORKIDLE_TIMEOUT_MS)
            except PlaywrightTimeoutError:
                logger.warning(
                    "get_rendered_content: networkidle timeout for %s — using available DOM", url
                )
            return await page.content()
        finally:
            if browser:
                await browser.close()
