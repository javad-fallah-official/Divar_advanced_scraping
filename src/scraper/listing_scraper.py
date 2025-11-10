from typing import List
from urllib.parse import urljoin
import time

from playwright.sync_api import sync_playwright

from .utils import random_user_agent


def _build_listing_url(city: str, category: str, brand: str | None, non_negotiable: bool) -> str:
    base = f"https://divar.ir/s/{city}/{category}"
    if brand:
        base += f"/{brand}"
    if non_negotiable:
        sep = "?" if "?" not in base else "&"
        base += f"{sep}non-negotiable=true"
    return base


def collect_listing_urls(
    city: str = "tehran",
    category: str = "motorcycles",
    brand: str | None = "honda",
    non_negotiable: bool = True,
    max_items: int = 200,
    headless: bool = True,
) -> List[str]:
    start_url = _build_listing_url(city, category, brand, non_negotiable)
    ua = random_user_agent()
    urls: set[str] = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(user_agent=ua, viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page.goto(start_url, wait_until="domcontentloaded")

        stall_rounds = 0
        last_count = 0
        while len(urls) < max_items and stall_rounds < 8:
            # Collect anchors and filter product links
            anchors = page.eval_on_selector_all("a", "els => els.map(e => e.getAttribute('href'))")
            for href in anchors:
                if not href:
                    continue
                if href.startswith("/v/"):
                    full = urljoin("https://divar.ir", href)
                    urls.add(full)
                elif href.startswith("https://divar.ir/v/"):
                    urls.add(href)

            # Scroll down to load more
            page.mouse.wheel(0, 2500)
            time.sleep(1.2)

            if len(urls) == last_count:
                stall_rounds += 1
            else:
                stall_rounds = 0
                last_count = len(urls)

        browser.close()

    # Cap to max_items
    out = list(urls)
    if len(out) > max_items:
        out = out[:max_items]
    return out

