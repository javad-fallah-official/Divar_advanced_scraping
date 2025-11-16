import json
from typing import List, Optional
from selectolax.parser import HTMLParser
from urllib.parse import urljoin
import re

from ..scraper.utils import random_user_agent
from ..scraper.metrics import log_event
from ..scraper.api_listing import _extract_urls_from_json
from .http import fetch_text


def _build_listing_url(city: str, category: str, brand: str | None, non_negotiable: bool) -> str:
    base = f"https://divar.ir/s/{city}/{category}" + (f"/{brand}" if brand else "")
    if non_negotiable:
        sep = "?"
        base = f"{base}{sep}non-negotiable=true"
    return base


async def collect_listing_urls_async(city: str, category: str, brand: Optional[str], non_negotiable: bool, max_items: int = 200) -> List[str]:
    ua = random_user_agent()
    headers = {"User-Agent": ua, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
    url = _build_listing_url(city, category, brand, non_negotiable)
    log_event("listing_async_start", city=city, category=category, brand=brand)
    html = await fetch_text(url, headers=headers)
    if not html:
        return []
    urls: set[str] = set()
    tree = HTMLParser(html)
    anchor_count = 0
    for a in tree.css("a[href]"):
        href = a.attributes.get("href")
        if not href:
            continue
        anchor_count += 1
        if href.startswith("/v/"):
            urls.add(urljoin("https://divar.ir", href))
        elif href.startswith("https://divar.ir/v/"):
            urls.add(href)
    s = tree.css_first("script#__NEXT_DATA__")
    if s and s.text():
        try:
            data = json.loads(s.text())
            for u in _extract_urls_from_json(data):
                urls.add(u)
        except Exception:
            pass
    for m in re.findall(r"https://divar\.ir/v/[\w%\-_/]+", html):
        urls.add(m)
    out = list(urls)
    if len(out) > max_items:
        out = out[:max_items]
    log_event("listing_async_page_parsed", anchors=anchor_count, has_next=bool(s and s.text()), url_count=len(out))
    log_event("listing_async_done", url_count=len(out))
    return out
