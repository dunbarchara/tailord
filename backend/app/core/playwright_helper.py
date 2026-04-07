import logging

from playwright.async_api import TimeoutError as PlaywrightTimeoutError, async_playwright

logger = logging.getLogger(__name__)

# Hard ceiling on the initial page navigation.
_GOTO_TIMEOUT_MS = 60_000

# Extra wait for JS-rendered content to settle after the load event. Non-fatal:
# many sites have persistent analytics XHR that prevent ever reaching "networkidle".
# If this times out we log a warning and use whatever DOM is already available.
_NETWORKIDLE_TIMEOUT_MS = 10_000


async def get_rendered_content(url: str) -> str:
    browser = None
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=_GOTO_TIMEOUT_MS)
            try:
                await page.wait_for_load_state("networkidle", timeout=_NETWORKIDLE_TIMEOUT_MS)
            except PlaywrightTimeoutError:
                logger.warning("get_rendered_content: networkidle timeout for %s — using available DOM", url)
            return await page.content()
        finally:
            if browser:
                await browser.close()
