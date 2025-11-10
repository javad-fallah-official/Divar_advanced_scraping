from typing import Optional, Dict, Any
import json
import re

from playwright.sync_api import sync_playwright

from .utils import (
    clean_text,
    parse_price_toman,
    parse_mileage_km,
    parse_model_year_jalali,
    parse_location_line,
    now_iso,
    random_user_agent,
)


KNOWN_LABELS = [
    "کارکرد",
    "مدل (سال تولید)",
    "رنگ",
    "برند",
    "قیمت",
    "توضیحات",
    "اطلاعات تماس",
    "چت",
    "زنگ خطرهای قبل از معامله",
]


def _extract_from_ld_json(page) -> dict | None:
    try:
        scripts = page.locator("script[type='application/ld+json']")
        count = scripts.count()
        for i in range(count):
            raw = scripts.nth(i).inner_text()
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
            if isinstance(data, list) and data:
                return data[0]
    except Exception:
        return None
    return None


def _extract_from_window(page) -> dict | None:
    # Try to read common SSR/SPA hydration payloads
    try:
        raw = page.evaluate(
            "() => JSON.stringify(window.__APOLLO_STATE__ || window.__layoutProps || window.__INITIAL_STATE__ || null)"
        )
        if raw:
            return json.loads(raw)
    except Exception:
        return None
    return None


def _value_after(label: str, body_text: str) -> Optional[str]:
    # Capture text following a label until the next known label or newline
    body_text = clean_text(body_text)
    idx = body_text.find(label)
    if idx == -1:
        return None
    tail = body_text[idx + len(label) :]
    # Stop at the next label occurrence
    stop_positions = []
    for l in KNOWN_LABELS:
        j = tail.find(l)
        if j != -1:
            stop_positions.append(j)
    stop = min(stop_positions) if stop_positions else len(tail)
    value = tail[:stop].strip()
    # Trim excessive trailing pieces
    value = re.split(r"\n|\r|\t", value)[0].strip()
    return value or None


def scrape_post_details(url: str, headless: bool = True, non_negotiable: bool = True) -> Optional[Dict[str, Any]]:
    ua = random_user_agent()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(user_agent=ua, viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded")

        # First, try JSON sources
        data = _extract_from_window(page) or _extract_from_ld_json(page)

        body_text = page.inner_text("body")
        title = None
        try:
            title = page.locator("h1").first.inner_text()
            title = clean_text(title)
        except Exception:
            # Fallback by heuristics: first significant line
            title = clean_text(body_text.split("\n")[0]) if body_text else None

        # Location line (e.g., "دقایقی پیش در تهران، امامت")
        city, district = parse_location_line(body_text)

        # Attributes via text heuristics
        price_text = _value_after("قیمت", body_text)
        price_toman = parse_price_toman(price_text or "") if price_text else None

        mileage_text = _value_after("کارکرد", body_text)
        mileage_km = parse_mileage_km(mileage_text or "") if mileage_text else None

        year_text = _value_after("مدل (سال تولید)", body_text) or _value_after("مدل", body_text)
        model_year_jalali = parse_model_year_jalali(year_text or "") if year_text else None

        color_text = _value_after("رنگ", body_text)
        color = clean_text(color_text) if color_text else None

        brand_text = _value_after("برند", body_text)
        brand = clean_text(brand_text) if brand_text else None

        desc_text = _value_after("توضیحات", body_text)
        description = clean_text(desc_text) if desc_text else None

        # Posted at line (raw, not parsed)
        posted_line = None
        m_posted = re.search(r"(دقایقی پیش .*|ساعت پیش .*|روز پیش .*|در\s+[^\n]+)", body_text)
        if m_posted:
            posted_line = clean_text(m_posted.group(1))

        browser.close()

    if not title:
        return None

    result: Dict[str, Any] = {
        "url": url,
        "title": title,
        "city": city,
        "district": district,
        "brand": brand,
        "model_year_jalali": model_year_jalali,
        "mileage_km": mileage_km,
        "color": color,
        "price_toman": price_toman,
        "negotiable": 0 if non_negotiable else None,
        "description": description,
        "posted_at": posted_line,
        "scraped_at": now_iso(),
    }

    return result

