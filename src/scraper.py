import logging
from playwright.async_api import async_playwright, TimeoutError as PWTimeout
from .config import TARGET_URL, USER_AGENT, MAX_SCROLLS

LOAD_MORE_SELECTOR = "button[class*='post-list__load-more-btn']"

async def fetch_final_html() -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(user_agent=USER_AGENT, locale="fa-IR")
        page = await context.new_page()
        await page.goto(TARGET_URL, wait_until="load", timeout=60000)
        scroll_count = 0
        while scroll_count < MAX_SCROLLS:
            scroll_count += 1
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(800)
            try:
                btn = await page.wait_for_selector(LOAD_MORE_SELECTOR, timeout=1500)
                if btn:
                    try:
                        await btn.click()
                        await page.wait_for_timeout(1200)
                    except Exception as e:
                        logging.warning("load-more click failed: %s", e)
                        break
            except PWTimeout:
                break
        content = await page.content()
        await browser.close()
        return content