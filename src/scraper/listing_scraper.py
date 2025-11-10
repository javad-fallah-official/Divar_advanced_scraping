from typing import List
from urllib.parse import urljoin
import time

from playwright.sync_api import sync_playwright

from .utils import random_user_agent
from .api_listing import collect_listing_urls_via_api, collect_listing_urls_via_http, _extract_urls_from_json
import re


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

    # Try HTTP SSR-first; if it yields results, return early
    try:
        http_urls = collect_listing_urls_via_http(city, category, brand, non_negotiable, max_items)
        if http_urls:
            return http_urls[:max_items]
    except Exception:
        pass
    # Then try API; if it yields results, return
    try:
        api_urls = collect_listing_urls_via_api(city, category, brand, non_negotiable, max_items)
        if api_urls:
            return api_urls[:max_items]
    except Exception:
        pass

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent=ua,
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
        )
        page = context.new_page()
        page.goto(start_url, wait_until="domcontentloaded")
        # Give dynamic content some time to settle
        try:
            page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        # Try to accept consent if present
        try:
            page.locator("button:has-text('قبول')").first.click(timeout=1500)
        except Exception:
            pass
        try:
            page.wait_for_selector("a[href*='/v/']", timeout=7000)
        except Exception:
            pass

        stall_rounds = 0
        last_count = 0
        while len(urls) < max_items and stall_rounds < 30:
            # Collect anchors and filter product links (include data-* fallbacks)
            anchors = page.eval_on_selector_all(
                "a[href], [data-href], [data-link]",
                "els => els.map(e => (e.href || e.getAttribute('href') || e.getAttribute('data-href') || e.getAttribute('data-link')))"
            )
            for href in anchors:
                if not href:
                    continue
                if href.startswith("/v/"):
                    full = urljoin("https://divar.ir", href)
                    urls.add(full)
                elif href.startswith("https://divar.ir/v/"):
                    urls.add(href)

            # Fallback: scan window state / page HTML for absolute post URLs
            try:
                raw_state = page.evaluate(
                    "() => JSON.stringify(window.__APOLLO_STATE__ || window.__layoutProps || window.__INITIAL_STATE__ || null)"
                )
            except Exception:
                raw_state = None
            if raw_state:
                for m in re.findall(r"https://divar\.ir/v/[\w%\-_/]+", raw_state):
                    urls.add(m)
            # Parse Next.js SSR data
            try:
                next_raw = page.locator("script#__NEXT_DATA__").first.inner_text()
                if next_raw:
                    try:
                        import json as _json
                        next_obj = _json.loads(next_raw)
                        next_urls = _extract_urls_from_json(next_obj)
                        for u in next_urls:
                            urls.add(u)
                    except Exception:
                        pass
            except Exception:
                pass
            # Also scan HTML text for links
            try:
                html = page.content()
                # absolute
                for m in re.findall(r"https://divar\.ir/v/[\w%\-_/]+", html):
                    urls.add(m)
                # relative
                for m in re.findall(r"/v/[\w%\-_/]+", html):
                    urls.add(urljoin("https://divar.ir", m))
            except Exception:
                pass

            # Scroll down to load more
            try:
                page.mouse.wheel(0, 3000)
                page.keyboard.press("End")
            except Exception:
                pass
            time.sleep(2.0 + (0.5 * (stall_rounds % 3)))

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
