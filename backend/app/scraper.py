from playwright.async_api import async_playwright

async def extract_job_text(url: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(url, timeout=60000)
        await page.wait_for_timeout(3000)

        await page.evaluate("""
            document.querySelectorAll(
              'script, style, nav, footer, header, aside'
            ).forEach(el => el.remove());
        """)

        text = await page.evaluate("document.body.innerText")
        await browser.close()

        return text[:15000]
