from playwright.async_api import async_playwright

async def get_rendered_content(url: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(url, timeout=60000)
        await page.wait_for_load_state()
        
        content = await page.content()
        
        await browser.close()
        
        return content
