from urllib.parse import urlparse

PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")

def persian_to_ascii(s: str) -> str:
    return s.translate(PERSIAN_DIGITS)

def id_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    segs = parsed.path.rstrip("/").split("/")
    return segs[-1] if segs else None

SPEC_KEY_MAP = {
    "رنگ": "color",
    "سال": "year_made",
    "سال تولید": "year_made",
    "کارکرد": "mileage",
    "کیلومتر": "mileage",
}

def normalize_price(s: str) -> str:
    ascii_s = persian_to_ascii(s)
    return ascii_s.strip()
