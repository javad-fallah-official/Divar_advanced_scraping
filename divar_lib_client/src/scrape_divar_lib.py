from typing import List, Dict, Any, Optional
from tqdm import tqdm
from datetime import datetime
import sqlite3
from pathlib import Path

try:
    from divar import sync_client
except Exception:  # pragma: no cover
    sync_client = None

try:
    from .utils import (
        clean_text,
        parse_price_toman,
        parse_mileage_km,
        parse_model_year_jalali,
        parse_location_line,
        contains_brand,
    )
except ImportError:
    # Allow running as a script: python divar_lib_client/src/main.py
    from utils import (
        clean_text,
        parse_price_toman,
        parse_mileage_km,
        parse_model_year_jalali,
        parse_location_line,
        contains_brand,
    )


def _find_any_key(data: Any, keys: List[str]) -> Optional[Any]:
    if isinstance(data, dict):
        for k, v in data.items():
            if k in keys:
                return v
            found = _find_any_key(v, keys)
            if found is not None:
                return found
    elif isinstance(data, list):
        for item in data:
            found = _find_any_key(item, keys)
            if found is not None:
                return found
    return None


def _token_from_post(post: Dict[str, Any]) -> Optional[str]:
    for key in ["token", "Token", "post_token", "id", "Id"]:
        tok = post.get(key)
        if tok:
            return str(tok)
    # Sometimes token is present nested
    tok = _find_any_key(post, ["token", "Token"])
    return str(tok) if tok else None


def _is_negotiable(post: Dict[str, Any]) -> Optional[bool]:
    neg = _find_any_key(post, ["negotiable", "is_negotiable", "price_negotiable"])
    if isinstance(neg, bool):
        return neg
    price_text = _find_any_key(post, ["price", "قیمت"])
    if isinstance(price_text, str):
        t = clean_text(price_text)
        if "توافق" in t or "توافقی" in t:
            return True
    return None


def collect_tokens(city: str, category: str, brand: Optional[str], non_negotiable: bool, max_items: int) -> List[str]:
    if sync_client is None:
        raise RuntimeError("divar library not installed. Please install requirements.")
    client = sync_client()

    # Robust category fallback: handle plural/singular differences and common aliases
    cat_lower = (category or "").lower()
    candidates: List[str] = [category]
    if cat_lower.endswith("s"):
        candidates.append(cat_lower[:-1])
    # Known alias for motorcycles on Divar
    if cat_lower == "motorcycles":
        candidates.append("motorcycle")

    posts = None
    for cat in candidates:
        try:
            posts = client.GetCategory(city.title(), cat)
            if isinstance(posts, list) and posts:
                break
        except KeyError:
            # Library expected 'web_widgets' but response changed; try next candidate
            continue
        except Exception:
            continue
    if posts is None:
        # Fallback: collect tokens from Playwright DB if available
        tokens_db = _collect_tokens_from_playwright_db(city=city, brand=brand, non_negotiable=non_negotiable, max_items=max_items)
        if tokens_db:
            return tokens_db
        raise RuntimeError(
            f"Failed to fetch category '{category}'. Try '--category motorcycle' or update the library."
        )

    tokens: List[str] = []
    for post in posts:
        tok = _token_from_post(post)
        if not tok:
            continue
        if brand:
            title = clean_text(post.get("title") or post.get("name") or "")
            brand_value = _find_any_key(post, ["brand", "برند"]) or ""
            if not (contains_brand(title, brand) or contains_brand(str(brand_value), brand)):
                continue
        if non_negotiable:
            neg = _is_negotiable(post)
            if neg is True:
                continue
        tokens.append(tok)
        if len(tokens) >= max_items:
            break
    return tokens


def _collect_tokens_from_playwright_db(city: str, brand: Optional[str], non_negotiable: bool, max_items: int) -> List[str]:
    """Fallback: read tokens from Playwright scraper DB (data/divar.db)."""
    db_path = Path("data") / "divar.db"
    if not db_path.exists():
        return []
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        clauses = []
        params: List[Any] = []
        if city:
            clauses.append("city LIKE ?")
            params.append(f"%{city}%")
        if brand:
            clauses.append("brand LIKE ?")
            params.append(f"%{brand}%")
        if non_negotiable:
            clauses.append("negotiable = 0")
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"SELECT url FROM posts{where} ORDER BY scraped_at DESC LIMIT ?"
        params2 = params + [max_items]
        rows = conn.execute(sql, params2).fetchall()
        conn.close()
        tokens: List[str] = []
        seen = set()
        for r in rows:
            url = r["url"]
            if not isinstance(url, str):
                continue
            # Extract token from URL like https://divar.ir/v/<token>
            try:
                token = url.rstrip("/").split("/")[-1]
            except Exception:
                token = None
            if token and token not in seen:
                seen.add(token)
                tokens.append(token)
        return tokens
    except Exception:
        return []


def scrape_post_details(token: str, non_negotiable: bool) -> Optional[Dict[str, Any]]:
    if sync_client is None:
        raise RuntimeError("divar library not installed. Please install requirements.")
    client = sync_client()
    info = client.GetPost(token)

    # Build url
    url = f"https://divar.ir/v/{token}"

    # Title
    title = clean_text(info.get("title") or info.get("name") or "")
    if not title:
        return None

    # Location
    city = _find_any_key(info, ["city", "location_city", "شهر"]) or None
    district = _find_any_key(info, ["district", "location_district", "محله"]) or None
    # If raw location line exists, parse it
    loc_text = _find_any_key(info, ["location", "مکان"]) or ""
    if not (city and district) and isinstance(loc_text, str):
        c2, d2 = parse_location_line(loc_text)
        city = city or c2
        district = district or d2

    # Price
    price_raw = _find_any_key(info, ["price", "قیمت", "amount", "value", "toman"]) 
    price_toman = None
    if isinstance(price_raw, (int, float)):
        price_toman = int(price_raw)
    elif isinstance(price_raw, str):
        price_toman = parse_price_toman(price_raw)

    # Attributes
    mileage_raw = _find_any_key(info, ["mileage", "کارکرد"]) or None
    mileage_km = None
    if isinstance(mileage_raw, (int, float)):
        mileage_km = int(mileage_raw)
    elif isinstance(mileage_raw, str):
        mileage_km = parse_mileage_km(mileage_raw)

    year_raw = _find_any_key(info, ["model_year", "year", "مدل", "سال تولید"]) or None
    model_year_jalali = None
    if isinstance(year_raw, (int, float)):
        model_year_jalali = int(year_raw)
    elif isinstance(year_raw, str):
        model_year_jalali = parse_model_year_jalali(year_raw)

    color_raw = _find_any_key(info, ["color", "رنگ"]) or None
    color = clean_text(color_raw) if isinstance(color_raw, str) else None

    brand_raw = _find_any_key(info, ["brand", "برند"]) or None
    brand = clean_text(brand_raw) if isinstance(brand_raw, str) else None

    description_raw = _find_any_key(info, ["description", "توضیحات"]) or None
    description = clean_text(description_raw) if isinstance(description_raw, str) else None

    # Posted at line might not be available via library; set None
    posted_at = _find_any_key(info, ["posted_at", "زمان انتشار"]) or None

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
        "posted_at": posted_at,
        "scraped_at": datetime.utcnow().isoformat(),
    }
    return result
