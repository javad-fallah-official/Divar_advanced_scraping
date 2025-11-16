from lxml import html
from urllib.parse import urljoin
import re
from utils import id_from_url, persian_to_ascii

def extract_ad_hrefs(listing_html: str, base: str = "https://divar.ir") -> list[str]:
    tree = html.fromstring(listing_html)
    hrefs = tree.xpath("//a[contains(@href, '/v/')]/@href")
    normalized = []
    for h in hrefs:
        normalized.append(urljoin(base, h)) if h.startswith("/") else normalized.append(h)
    seen = set()
    out = []
    for h in normalized:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out

def parse_ad_page(html_text: str, url: str) -> dict:
    tree = html.fromstring(html_text)
    title = None
    t = tree.xpath("//h1/text()")
    if t:
        title = t[0].strip()
    else:
        t = tree.xpath("//meta[@property='og:title']/@content")
        title = t[0].strip() if t else None
    price = None
    p = tree.xpath("//*[contains(text(),'تومان') or contains(text(),'ریال')]/text()")
    if p:
        for cand in p:
            if re.search(r"\d", persian_to_ascii(cand)):
                price = cand.strip()
                break
    date_posted = None
    loc = None
    time_loc = tree.xpath("//text()[contains(., 'در')]/parent::*")
    if time_loc:
        text = "".join(time_loc[0].itertext()).strip()
        parts = text.split("در")
        if len(parts) >= 2:
            date_posted = parts[0].strip()
            loc = parts[1].strip()
    desc = None
    d = tree.xpath("//h2[contains(., 'توضیحات')]/following-sibling::*[1]//text()")
    if d:
        desc = " ".join([x.strip() for x in d if x.strip()])
    specs = {}
    for label in ["رنگ", "سال", "سال تولید", "کارکرد", "کیلومتر", "مدل"]:
        nodes = tree.xpath(f"//*[contains(text(), '{label}')]")
        if nodes:
            for node in nodes[:2]:
                txt = "".join(node.itertext()).strip()
                specs.setdefault(label, txt)
    normalized = {}
    normalized["color"] = specs.get("رنگ") or None
    normalized["year_made"] = specs.get("سال تولید") or specs.get("سال") or None
    normalized["mileage"] = specs.get("کارکرد") or specs.get("کیلومتر") or None
    return {
        "id": id_from_url(url),
        "url": url,
        "title": title,
        "price": price,
        "description": desc,
        "location": loc,
        "specs": normalized,
        "date_posted": None,
        "raw_html": html_text,
    }