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
from .metrics import log_event, Timer


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
    http_first = scrape_post_details_http(url, non_negotiable)
    if http_first:
        log_event("detail_http_used", url=url)
        return http_first

    ua = random_user_agent()

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
        t_nav = Timer()
        page.goto(url, wait_until="domcontentloaded")
        log_event("detail_playwright_goto", url=url, ms=t_nav.ms())

        # First, try JSON sources
        t_parse = Timer()
        data = _extract_from_window(page) or _extract_from_ld_json(page)

        body_text = page.inner_text("body")
        title = None
        try:
            title = page.locator("h1").first.inner_text()
            title = clean_text(title)
        except Exception:
            title = None
        # Additional fallbacks for title
        if not title:
            # Try <meta property="og:title">
            try:
                ogt = page.locator("meta[property='og:title']").first.get_attribute("content")
                if ogt:
                    title = clean_text(ogt)
            except Exception:
                pass
        if not title and isinstance(data, dict):
            for k in ("title", "name", "headline"):
                val = data.get(k)
                if isinstance(val, str) and val.strip():
                    title = clean_text(val)
                    break
        if not title:
            # Fallback by heuristics: first significant line of page body
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

        log_event("detail_parse_done", url=url, ms=t_parse.ms())
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


def _inner_text_from_html(html: str) -> str:
    # Very rough HTML to text conversion for heuristics
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def scrape_post_details_http(url: str, non_negotiable: bool = True) -> Optional[Dict[str, Any]]:
    try:
        import requests  # type: ignore
    except Exception:
        return None

    ua = random_user_agent()
    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://divar.ir/",
    }

    try:
        t_req = Timer()
        resp = requests.get(url, headers=headers, timeout=15)
        dur_ms = t_req.ms()
        if resp.status_code != 200:
            log_event("detail_http_status", url=url, status=resp.status_code, ms=dur_ms)
            return None
        html = resp.text
        log_event("detail_http_ok", url=url, status=resp.status_code, ms=dur_ms, bytes=len(html.encode("utf-8", errors="ignore")))
    except Exception as e:
        log_event("detail_http_error", url=url, error=str(e))
        return None

    title = None
    # og:title
    m_og = re.search(r"<meta[^>]+property=\"og:title\"[^>]+content=\"(.*?)\"", html, re.I)
    if m_og:
        title = clean_text(m_og.group(1))
    # ld+json
    if not title:
        m_ld = re.search(r"<script[^>]+type=\"application/ld\+json\"[^>]*>([\s\S]*?)</script>", html, re.I)
        if m_ld:
            try:
                data = json.loads(m_ld.group(1))
                if isinstance(data, dict):
                    for k in ("name", "headline", "title"):
                        if isinstance(data.get(k), str) and data.get(k).strip():
                            title = clean_text(data[k])
                            break
                elif isinstance(data, list) and data:
                    d0 = data[0]
                    if isinstance(d0, dict):
                        for k in ("name", "headline", "title"):
                            val = d0.get(k)
                            if isinstance(val, str) and val.strip():
                                title = clean_text(val)
                                break
            except Exception:
                pass

    body_text = _inner_text_from_html(html)
    if not title and body_text:
        title = clean_text(body_text.split(" ")[0])

    city, district = parse_location_line(body_text)
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

    if not title:
        return None

    out = {
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
        "posted_at": None,
        "scraped_at": now_iso(),
    }
    log_event("detail_http_parsed", url=url, ok=bool(out.get("title")))
    return out
