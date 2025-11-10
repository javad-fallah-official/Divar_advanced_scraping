import re

PERSIAN_DIGITS = {
    "۰": "0",
    "۱": "1",
    "۲": "2",
    "۳": "3",
    "۴": "4",
    "۵": "5",
    "۶": "6",
    "۷": "7",
    "۸": "8",
    "۹": "9",
}


def normalize_persian_digits(text: str) -> str:
    if not text:
        return text
    for fa, en in PERSIAN_DIGITS.items():
        text = text.replace(fa, en)
    text = text.replace("٬", "").replace("،", "").replace(",", "")
    text = text.replace("\u200f", "").replace("\u200e", "")
    return text


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = normalize_persian_digits(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_int(text: str) -> int | None:
    if not text:
        return None
    text = normalize_persian_digits(text)
    m = re.search(r"(\d{1,3}(?:\d{3})+|\d+)", text)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def parse_price_toman(text: str) -> int | None:
    return extract_int(text)


def parse_mileage_km(text: str) -> int | None:
    return extract_int(text)


def parse_model_year_jalali(text: str) -> int | None:
    text = normalize_persian_digits(text)
    m = re.search(r"(13\d{2}|14\d{2})", text)
    if m:
        return int(m.group(1))
    return extract_int(text)


def parse_location_line(text: str) -> tuple[str | None, str | None]:
    text = clean_text(text)
    m = re.search(r"در\s+([^،]+)\s*،\s*([^\n]+)", text)
    if m:
        city = m.group(1).strip()
        district = m.group(2).strip()
        return city, district
    return None, None


def contains_brand(text: str, brand_slug: str) -> bool:
    if not text:
        return False
    text = clean_text(text).lower()
    brand_slug = brand_slug.lower()
    synonyms = [brand_slug, "honda", "هوندا"]
    return any(s in text for s in synonyms)

