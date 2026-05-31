import ipaddress
import logging
import random
import re
import socket
from urllib.parse import urlparse

import httpx
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from app.metrics import JOB_SCRAPE_TOTAL

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

# RFC 1918 private ranges, loopback, link-local (includes cloud metadata 169.254.169.254),
# and other non-routable / reserved ranges that must never be fetched.
_BLOCKED_NETWORKS: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
    ipaddress.ip_network("0.0.0.0/8"),  # "This" network
    ipaddress.ip_network("10.0.0.0/8"),  # RFC 1918 private
    ipaddress.ip_network("100.64.0.0/10"),  # Shared address space (RFC 6598)
    ipaddress.ip_network("127.0.0.0/8"),  # Loopback
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local — cloud metadata endpoints live here
    ipaddress.ip_network("172.16.0.0/12"),  # RFC 1918 private
    ipaddress.ip_network("192.0.0.0/24"),  # IETF protocol assignments
    ipaddress.ip_network("192.168.0.0/16"),  # RFC 1918 private
    ipaddress.ip_network("198.18.0.0/15"),  # Benchmarking (RFC 2544)
    ipaddress.ip_network("224.0.0.0/4"),  # Multicast
    ipaddress.ip_network("240.0.0.0/4"),  # Reserved
    ipaddress.ip_network("::1/128"),  # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),  # IPv6 unique local
    ipaddress.ip_network("fe80::/10"),  # IPv6 link-local
]


def _assert_public_url(url: str) -> None:
    """Raise ValueError if *url* is not a safe, publicly-routable http(s) URL.

    Checks performed:
    1. Scheme must be http or https.
    2. Hostname must be present and not a well-known internal name.
    3. All addresses the hostname resolves to must be publicly routable —
       private, loopback, link-local (including the cloud metadata endpoint
       at 169.254.169.254), and other reserved ranges are rejected.

    Note: pre-flight DNS resolution does not fully eliminate DNS-rebinding
    attacks (an attacker with control over a DNS server could return a valid
    public IP during the check then switch to a private IP for the actual
    connection). For a job-parsing workload the residual risk is negligible;
    full rebinding prevention would require a pinned-IP custom transport.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"Only http/https URLs are allowed (got {parsed.scheme!r})")

    host = parsed.hostname or ""
    if not host:
        raise ValueError("URL must include a hostname")

    lower = host.lower().rstrip(".")
    if lower in {"localhost"} or lower.endswith((".local", ".internal", ".localhost")):
        raise ValueError(f"Internal hostname not allowed: {host!r}")

    try:
        addr_infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise ValueError(f"Could not resolve hostname {host!r}: {exc}") from exc

    for _family, _type, _proto, _canonname, sockaddr in addr_infos:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        for network in _BLOCKED_NETWORKS:
            if ip in network:
                raise ValueError(
                    f"URL resolves to a reserved/private address ({ip}) — "
                    "only publicly routable job URLs are supported"
                )


async def _validate_request_hook(request: httpx.Request) -> None:
    """httpx request event hook — fires before every request, including redirect hops.

    Validates each destination URL so that an open redirect on a job board
    (e.g. https://jobs.example.com → http://169.254.169.254/) cannot bypass the
    pre-flight check in _assert_public_url.
    """
    _assert_public_url(str(request.url))


async def _fetch_with_httpx(url: str) -> str:
    """Plain HTTPS GET with browser-like headers. Returns decoded HTML."""
    headers = {**_FETCH_HEADERS, "User-Agent": random.choice(_USER_AGENTS)}
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=_HTTPX_TIMEOUT_S,
        event_hooks={"request": [_validate_request_hook]},
    ) as client:
        # URL is validated by _assert_public_url() at the get_html_content entry point
        # and re-validated on every redirect hop via _validate_request_hook.
        response = await client.get(url, headers=headers)  # lgtm[py/full-ssrf]
        response.raise_for_status()
        return response.text


# Minimum visible-text length to trust httpx HTML as real job content.
# SPAs that slip past the _SPA_PATTERN check (e.g. Ashby) still return < 1 500 chars
# of visible body text — real job postings are substantially longer.
_MIN_CONTENT_CHARS = 1_500


def _needs_browser(html: str) -> tuple[bool, str]:
    """Return (needs_browser, reason) — True if JS rendering is required."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    body = soup.find("body")
    visible_text = body.get_text(" ", strip=True) if body else ""

    if len(visible_text) < 500:
        return True, "thin_body"

    if _SPA_PATTERN.search(html):
        return True, "spa_pattern"

    if len(visible_text) < _MIN_CONTENT_CHARS:
        return True, "thin_content"

    return False, ""


async def get_html_content(url: str) -> str:
    """Fetch HTML for a job URL. Tries plain httpx first; falls back to Playwright."""
    _assert_public_url(url)
    try:
        html = await _fetch_with_httpx(url)
        needs_browser, reason = _needs_browser(html)
        if not needs_browser:
            logger.info("httpx_fetch_success", extra={"url": url})
            JOB_SCRAPE_TOTAL.labels(method="httpx", outcome="success").inc()
            return html
        logger.debug(
            "httpx_fetch_needs_browser: falling through to Playwright for %s (reason=%s)",
            url,
            reason,
        )
        JOB_SCRAPE_TOTAL.labels(method="httpx", outcome="spa_fallthrough").inc()
    except Exception:
        logger.debug("httpx_fetch_failed: falling through to Playwright for %s", url, exc_info=True)
        JOB_SCRAPE_TOTAL.labels(method="httpx", outcome="error_fallthrough").inc()
    return await get_rendered_content(url)


async def get_rendered_content(url: str) -> str:
    _assert_public_url(url)
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
            html = await page.content()
            JOB_SCRAPE_TOTAL.labels(method="playwright", outcome="success").inc()
            return html
        finally:
            if browser:
                await browser.close()
