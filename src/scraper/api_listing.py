from __future__ import annotations

from typing import List, Optional
import re

from .utils import random_user_agent
from .http_client import get_thread_session


def _extract_urls_from_json(data: object) -> List[str]:
    urls: set[str] = set()
    def walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, (dict, list)):
                    walk(v)
                elif isinstance(v, str):
                    if v.startswith("https://divar.ir/v/"):
                        urls.add(v)
        elif isinstance(obj, list):
            for it in obj:
                walk(it)
        elif isinstance(obj, str):
            for m in re.findall(r"https://divar\.ir/v/[\w%\-_/]+", obj):
                urls.add(m)

    walk(data)
    return list(urls)


def collect_listing_urls_via_api(
    city: str,
    category: str,
    brand: Optional[str],
    non_negotiable: bool,
    max_items: int = 200,
) -> List[str]:
    sess = get_thread_session()
    if sess is None:
        return []
    # Try a set of known endpoints observed in Divar clients
    endpoints = [
        f"https://api.divar.ir/v8/web-search/{city}/{category}",
        f"https://api.divar.ir/v8/web-search/{city}/{category}/{brand}" if brand else None,
        f"https://api.divar.ir/v8/search/{city}/{category}",
    ]
    endpoints = [e for e in endpoints if e]

    ua = random_user_agent()
    headers = {
        "User-Agent": ua,
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "https://divar.ir",
        "Referer": f"https://divar.ir/s/{city}/{category}" + (f"/{brand}" if brand else ""),
    }

    payload = {
        "query": {
            "category": category,
            "city": city,
            "brand": brand or None,
            "filters": {
                "non_negotiable": non_negotiable,
            },
        },
        "page": 1,
        "size": max_items,
    }

    errors = []
    for ep in endpoints:
        try:
            resp = sess.post(ep, json=payload, headers=headers, timeout=15)
            if resp.status_code != 200:
                errors.append(f"{ep} -> {resp.status_code}")
                continue
            data = resp.json()
            urls = _extract_urls_from_json(data)
            if urls:
                return urls[:max_items]
        except Exception as e:
            errors.append(f"{ep} -> {e}")

    # If API path fails, return empty list and let caller fallback to DOM scraping
    return []


def collect_listing_urls_via_http(
    city: str,
    category: str,
    brand: Optional[str],
    non_negotiable: bool,
    max_items: int = 200,
) -> List[str]:
    sess = get_thread_session()
    if sess is None:
        return []

    ua = random_user_agent()
    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://divar.ir/",
    }

    base = f"https://divar.ir/s/{city}/{category}" + (f"/{brand}" if brand else "")
    if non_negotiable:
        sep = "?"
        base = f"{base}{sep}non-negotiable=true"

    try:
        resp = sess.get(base, headers=headers, timeout=15)
        if resp.status_code != 200:
            return []
        html = resp.text
        urls: set[str] = set()
        # absolute
        for m in re.findall(r"https://divar\.ir/v/[\w%\-_/]+", html):
            urls.add(m)
        # relative
        for m in re.findall(r"/v/[\w%\-_/]+", html):
            urls.add(f"https://divar.ir{m}")

        # Parse Next.js SSR JSON if present
        m = re.search(r"<script id=\"__NEXT_DATA__\" type=\"application/json\">(.*?)</script>", html, re.S)
        if m:
            try:
                import json as _json
                data = _json.loads(m.group(1))
                for u in _extract_urls_from_json(data):
                    urls.add(u)
            except Exception:
                pass

        if urls:
            return list(urls)[:max_items]
    except Exception:
        return []

    return []
