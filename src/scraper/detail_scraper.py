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
    parse_color_name,
)
from .metrics import log_event, Timer
from .http_client import get_thread_session


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

_RE_MONTH = r"(فروردین|اردیبهشت|خرداد|تیر|مرداد|شهریور|مهر|آبان|آذر|دی|بهمن|اسفند)"
_RE_TITLE_CITY_DATE = re.compile(rf"^(.*?)\s+در\s+([^\s\-،]+)(?:\s*[-–]\s*(\d{{1,2}}\s+{_RE_MONTH}\s+(?:13\d{{2}}|14\d{{2}})))?", re.U)
_RE_BASE_TITLE_SPLIT = re.compile(r"^(.*?)\s+در\s+", re.U)

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


def _extract_fields_from_json(data: object) -> dict:
    out: dict = {}
    def walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                lk = str(k).lower()
                if isinstance(v, (dict, list)):
                    walk(v)
                else:
                    if isinstance(v, (int, float)):
                        vi = int(v)
                        if ("price" in lk or "toman" in lk) and vi >= 10000:
                            out.setdefault("price_toman", vi)
                        if ("year" in lk or "model_year" in lk) and 1200 <= vi <= 1600:
                            out.setdefault("model_year_jalali", vi)
                        if ("mileage" in lk or "kilometer" in lk or lk.endswith("km")) and vi >= 0:
                            out.setdefault("mileage_km", vi)
                    elif isinstance(v, str):
                        if "brand" in lk and v.strip():
                            out.setdefault("brand", clean_text(v))
        elif isinstance(obj, list):
            for it in obj:
                walk(it)
    try:
        walk(data)
    except Exception:
        pass
    return out


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


def scrape_post_details(url: str, headless: bool = True, non_negotiable: bool = True, http_timeout: float = 10.0) -> Optional[Dict[str, Any]]:
    http_first = scrape_post_details_http(url, non_negotiable, http_timeout=http_timeout)
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
        api_payloads: list[object] = []
        def _on_response(resp):
            try:
                u = resp.url
            except Exception:
                return
            if "api.divar.ir" in u:
                try:
                    data = resp.json()
                except Exception:
                    try:
                        data = json.loads(resp.text())
                    except Exception:
                        data = None
                if isinstance(data, (dict, list)):
                    api_payloads.append(data)
        try:
            page.on("response", _on_response)
        except Exception:
            pass
        t_nav = Timer()
        page.goto(url, wait_until="domcontentloaded")
        log_event("detail_playwright_goto", url=url, ms=t_nav.ms())
        try:
            page.wait_for_selector("h1", timeout=4000)
        except Exception:
            pass
        try:
            page.wait_for_selector("script#__NEXT_DATA__", timeout=3000)
        except Exception:
            pass

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
            title = clean_text(body_text.split("\n")[0]) if body_text else None
        if title:
            mtd = _RE_TITLE_CITY_DATE.match(title)
            if mtd:
                base = clean_text(mtd.group(1) or "")
                city_from_title = clean_text(mtd.group(2) or "")
                date_from_title = clean_text(mtd.group(3) or "") if mtd.lastindex and mtd.group(3) else None
                if base:
                    title = base
                if city_from_title:
                    city = city or city_from_title
                if date_from_title:
                    posted_line = date_from_title
        if title and title.strip() == "سایت دیوار":
            title = None

        city, district = parse_location_line(body_text)
        if not city:
            mcity = re.search(r"در\s+([^\s\-،]+)", body_text)
            if mcity:
                city = clean_text(mcity.group(1))

        # Attributes via text heuristics
        price_text = _value_after("قیمت", body_text)
        price_toman = parse_price_toman(price_text or "") if price_text else None

        mileage_text = _value_after("کارکرد", body_text)
        mileage_km = parse_mileage_km(mileage_text or "") if mileage_text else None

        year_text = _value_after("مدل (سال تولید)", body_text) or _value_after("مدل", body_text)
        model_year_jalali = parse_model_year_jalali(year_text or "") if year_text else None

        color_text = _value_after("رنگ", body_text)
        color = parse_color_name(color_text) if color_text else None

        brand_text = _value_after("برند", body_text)
        brand = clean_text(brand_text) if brand_text else None

        desc_text = _value_after("توضیحات", body_text)
        description = clean_text(desc_text) if desc_text else None

        posted_line = posted_line if 'posted_line' in locals() and posted_line else None
        if not posted_line:
            m_posted = re.search(rf"(\d{{1,2}}\s+{_RE_MONTH}\s+(?:13\d{{2}}|14\d{{2}}))", body_text)
            if m_posted:
                posted_line = clean_text(m_posted.group(1))

        try:
            next_raw = page.locator("script#__NEXT_DATA__").first.inner_text()
            if next_raw:
                jf = _extract_fields_from_json(json.loads(next_raw))
                if price_toman is None:
                    price_toman = jf.get("price_toman")
                if model_year_jalali is None:
                    model_year_jalali = jf.get("model_year_jalali")
                if mileage_km is None:
                    mileage_km = jf.get("mileage_km")
                if not brand:
                    brand = jf.get("brand")
        except Exception:
            pass
        # Merge API payload fields
        try:
            for pl in api_payloads:
                jf = _extract_fields_from_json(pl)
                if price_toman is None:
                    price_toman = jf.get("price_toman")
                if model_year_jalali is None:
                    model_year_jalali = jf.get("model_year_jalali")
                if mileage_km is None:
                    mileage_km = jf.get("mileage_km")
                if not brand:
                    brand = jf.get("brand")
        except Exception:
            pass
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


def scrape_post_details_http(url: str, non_negotiable: bool = True, http_timeout: float = 10.0) -> Optional[Dict[str, Any]]:
    sess = get_thread_session(timeout=http_timeout)
    if sess is None:
        return None

    ua = random_user_agent()
    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://divar.ir/",
    }

    try:
        t_req = Timer()
        resp = sess.get(url, headers=headers, timeout=http_timeout)
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
    city, district, posted_line = None, None, None
    # og:title
    m_og = _RE_OG_TITLE.search(html)
    if m_og:
        title = clean_text(m_og.group(1))
        mtd = _RE_TITLE_CITY_DATE.match(title)
        if mtd:
            base = clean_text(mtd.group(1) or "")
            city_from_title = clean_text(mtd.group(2) or "")
            date_from_title = clean_text(mtd.group(3) or "") if mtd.lastindex and mtd.group(3) else None
            if base:
                title = base
            if city_from_title:
                city = city or city_from_title
            if date_from_title:
                posted_line = date_from_title
        mtd = _RE_TITLE_CITY_DATE.match(title)
        if mtd:
            base = clean_text(mtd.group(1) or "")
            city_from_title = clean_text(mtd.group(2) or "")
            date_from_title = clean_text(mtd.group(3) or "") if mtd.lastindex and mtd.group(3) else None
            if base:
                title = base
            if city_from_title:
                city = city or city_from_title
            if date_from_title:
                posted_line = date_from_title
    # ld+json
    if not title:
        m_ld = _RE_LD_JSON.search(html)
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
    if title:
        mtd2 = _RE_TITLE_CITY_DATE.match(title)
        if mtd2:
            base = clean_text(mtd2.group(1) or "")
            city_from_title = clean_text(mtd2.group(2) or "")
            date_from_title = clean_text(mtd2.group(3) or "") if mtd2.lastindex and mtd2.group(3) else None
            if base:
                title = base
            if city_from_title:
                city = city or city_from_title
            if date_from_title:
                posted_line = posted_line or date_from_title
    if title:
        mtd2 = _RE_TITLE_CITY_DATE.match(title)
        if mtd2:
            base = clean_text(mtd2.group(1) or "")
            city_from_title = clean_text(mtd2.group(2) or "")
            date_from_title = clean_text(mtd2.group(3) or "") if mtd2.lastindex and mtd2.group(3) else None
            if base:
                title = base
            if city_from_title:
                city = city or city_from_title
            if date_from_title:
                posted_line = posted_line or date_from_title
    if title and title.strip() == "سایت دیوار":
        title = None

    city, district = parse_location_line(body_text)
    if not city:
        mcity = re.search(r"در\s+([^\s\-،]+)", body_text)
        if mcity:
            city = clean_text(mcity.group(1))
    if not city:
        mcity = re.search(r"در\s+([^\s\-،]+)", body_text)
        if mcity:
            city = clean_text(mcity.group(1))
    price_text = _value_after("قیمت", body_text)
    price_toman = parse_price_toman(price_text or "") if price_text else None
    mileage_text = _value_after("کارکرد", body_text)
    mileage_km = parse_mileage_km(mileage_text or "") if mileage_text else None
    year_text = _value_after("مدل (سال تولید)", body_text) or _value_after("مدل", body_text)
    model_year_jalali = parse_model_year_jalali(year_text or "") if year_text else None
    color_text = _value_after("رنگ", body_text)
    color = parse_color_name(color_text) if color_text else None
    brand_text = _value_after("برند", body_text)
    brand = clean_text(brand_text) if brand_text else None
    desc_text = _value_after("توضیحات", body_text)
    description = clean_text(desc_text) if desc_text else None
    if not posted_line:
        m_posted2 = re.search(rf"(\d{{1,2}}\s+{_RE_MONTH}\s+(?:13\d{{2}}|14\d{{2}}))", body_text)
        if m_posted2:
            posted_line = clean_text(m_posted2.group(1))
    if not posted_line:
        m_posted2 = re.search(rf"(\d{{1,2}}\s+{_RE_MONTH}\s+(?:13\d{{2}}|14\d{{2}}))", body_text)
        if m_posted2:
            posted_line = clean_text(m_posted2.group(1))

    try:
        m_next = re.search(r"<script id=\"__NEXT_DATA__\" type=\"application/json\">(.*?)</script>", html, re.S)
        if m_next:
            jf = _extract_fields_from_json(json.loads(m_next.group(1)))
            if price_toman is None:
                price_toman = jf.get("price_toman")
            if model_year_jalali is None:
                model_year_jalali = jf.get("model_year_jalali")
            if mileage_km is None:
                mileage_km = jf.get("mileage_km")
            if not brand:
                brand = jf.get("brand")
    except Exception:
        pass

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
        "posted_at": posted_line,
        "scraped_at": now_iso(),
    }
    log_event("detail_http_parsed", url=url, ok=bool(out.get("title")))
    return out
_RE_OG_TITLE = re.compile(r"<meta[^>]+property=\"og:title\"[^>]+content=\"(.*?)\"", re.I)
_RE_LD_JSON = re.compile(r"<script[^>]+type=\"application/ld\+json\"[^>]*>([\s\S]*?)</script>", re.I)
_RE_URL_ABS = re.compile(r"https://divar\.ir/v/[\w%\-_/]+")
_RE_URL_REL = re.compile(r"/v/[\w%\-_/]+")
