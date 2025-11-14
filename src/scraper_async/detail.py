import json
import re
from typing import Dict, Any, Optional
from selectolax.parser import HTMLParser

from ..scraper.utils import clean_text, parse_price_toman, parse_mileage_km, parse_model_year_jalali, parse_location_line, now_iso, random_user_agent, parse_color_name
from ..scraper.metrics import log_event
from .http import fetch_text

_RE_OG_TITLE = re.compile(r"<meta[^>]+property=\"og:title\"[^>]+content=\"(.*?)\"", re.I)
_RE_LD_JSON = re.compile(r"<script[^>]+type=\"application/ld\+json\"[^>]*>([\s\S]*?)</script>", re.I)
_RE_MONTH = r"(فروردین|اردیبهشت|خرداد|تیر|مرداد|شهریور|مهر|آبان|آذر|دی|بهمن|اسفند)"
_RE_TITLE_CITY_DATE = re.compile(rf"^(.*?)\s+در\s+([^\s\-،]+)(?:\s*[-–]\s*(\d{{1,2}}\s+{_RE_MONTH}\s+(?:13\d{{2}}|14\d{{2}})))?", re.U)


async def scrape_post_details_async(url: str, non_negotiable: bool = True, timeout: float = 10.0) -> Optional[Dict[str, Any]]:
    ua = random_user_agent()
    headers = {"User-Agent": ua, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
    html = await fetch_text(url, headers=headers)
    if not html:
        return None
    title = None
    city, district, posted_line = None, None, None
    m_og = _RE_OG_TITLE.search(html)
    if m_og:
        title = clean_text(m_og.group(1))
        mtd = _RE_TITLE_CITY_DATE.match(title)
        if mtd:
            base = clean_text(mtd.group(1) or "")
            ct = clean_text(mtd.group(2) or "")
            dt = clean_text(mtd.group(3) or "") if mtd.lastindex and mtd.group(3) else None
            if base:
                title = base
            if ct:
                city = city or ct
            if dt:
                posted_line = dt
    if not title:
        m_ld = _RE_LD_JSON.search(html)
        if m_ld:
            try:
                data = json.loads(m_ld.group(1))
                if isinstance(data, dict):
                    for k in ("name", "headline", "title"):
                        val = data.get(k)
                        if isinstance(val, str) and val.strip():
                            title = clean_text(val)
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
    tree = HTMLParser(html)
    body_text = tree.body.text(separator=" ") if tree.body else ""
    if not title and body_text:
        title = clean_text(body_text.split(" ")[0])
    if title:
        mtd2 = _RE_TITLE_CITY_DATE.match(title)
        if mtd2:
            base = clean_text(mtd2.group(1) or "")
            ct = clean_text(mtd2.group(2) or "")
            dt = clean_text(mtd2.group(3) or "") if mtd2.lastindex and mtd2.group(3) else None
            if base:
                title = base
            if ct:
                city = city or ct
            if dt:
                posted_line = posted_line or dt
    c2, d2 = parse_location_line(body_text)
    city = city or c2
    district = district or d2
    price_text = None
    mileage_text = None
    year_text = None
    color_text = None
    for el in tree.css("body"):
        t = clean_text(el.text(separator=" "))
        if not price_text:
            m = re.search(r"قیمت\s+([^\n]+)", t)
            if m:
                price_text = m.group(1)
        if not mileage_text:
            m = re.search(r"کارکرد\s+([^\n]+)", t)
            if m:
                mileage_text = m.group(1)
        if not year_text:
            m = re.search(r"مدل\s+\(سال تولید\)\s+([^\n]+)", t)
            if m:
                year_text = m.group(1)
        if not color_text:
            m = re.search(r"رنگ\s+([^\n]+)", t)
            if m:
                color_text = m.group(1)
    price_toman = parse_price_toman(price_text or "") if price_text else None
    mileage_km = parse_mileage_km(mileage_text or "") if mileage_text else None
    model_year_jalali = parse_model_year_jalali(year_text or "") if year_text else None
    color = parse_color_name(color_text) if color_text else None
    brand = None
    s = tree.css_first("script#__NEXT_DATA__")
    if s and s.text():
        try:
            data2 = json.loads(s.text())
            def walk(obj):
                nonlocal brand, price_toman, model_year_jalali, mileage_km
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        lk = str(k).lower()
                        if isinstance(v, (dict, list)):
                            walk(v)
                        else:
                            if isinstance(v, (int, float)):
                                vi = int(v)
                                if price_toman is None and ("price" in lk or "toman" in lk) and vi >= 10000:
                                    price_toman = vi
                                if model_year_jalali is None and ("year" in lk or "model_year" in lk) and 1200 <= vi <= 1600:
                                    model_year_jalali = vi
                                if mileage_km is None and ("mileage" in lk or lk.endswith("km")) and vi >= 0:
                                    mileage_km = vi
                            elif isinstance(v, str):
                                if not brand and "brand" in lk and v.strip():
                                    brand = clean_text(v)
                elif isinstance(obj, list):
                    for it in obj:
                        walk(it)
            walk(data2)
        except Exception:
            pass
    if not title:
        return None
    res: Dict[str, Any] = {
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
        "description": None,
        "posted_at": posted_line,
        "scraped_at": now_iso(),
    }
    log_event("detail_async_parsed", url=url, ok=bool(res["title"]))
    return res

