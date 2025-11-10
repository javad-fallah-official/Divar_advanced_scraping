import re
import random
from datetime import datetime


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
    # Remove Persian thousands separators and commas
    text = text.replace("٬", "").replace("،", "").replace(",", "")
    # Remove left-to-right marks
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
    # Examples: "دقایقی پیش در تهران، امامت" → (تهران, امامت)
    text = clean_text(text)
    m = re.search(r"در\s+([^،]+)\s*،\s*([^\n]+)", text)
    if m:
        city = m.group(1).strip()
        district = m.group(2).strip()
        return city, district
    return None, None


USER_AGENTS = [
    # Desktop Chrome UAs
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    # Mobile Chrome UAs
    "Mozilla/5.0 (Linux; Android 10; Pixel 3 XL) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1",
]


def random_user_agent() -> str:
    return random.choice(USER_AGENTS)


def now_iso() -> str:
    return datetime.utcnow().isoformat()
