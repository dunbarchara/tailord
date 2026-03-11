from playwright.async_api import async_playwright

async def get_rendered_content(url: str) -> str:
    browser = None
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=60000)
            await page.wait_for_load_state(timeout=30000)
            return await page.content()
        finally:
            if browser:
                await browser.close()
