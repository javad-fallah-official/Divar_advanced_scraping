from pathlib import Path
from src.parser import extract_ad_hrefs, parse_ad_page
from datetime import datetime, timezone

BASE = Path(__file__).parent / "fixtures"

def read(name: str) -> str:
    return (BASE / name).read_text(encoding="utf-8")

def test_extract_ad_hrefs_listing():
    html_text = read("listing_snapshot.html")
    urls = extract_ad_hrefs(html_text)
    assert any(u.endswith("Token001") for u in urls)
    assert any(u.endswith("Token002") for u in urls)

def test_parse_ad_page_ad_sample():
    html_text = read("ad_sample.html")
    url = "https://divar.ir/v/tehran/motorcycle/Token003"
    data = parse_ad_page(html_text, url)
    assert data["title"]
    assert "تومان" in data["price"]
    assert data["specs"]["color"]
    assert data["specs"]["year_made"]
    assert data["specs"]["mileage"]
    assert isinstance(data["date_posted"], datetime)
    assert data["date_posted"].astimezone(timezone.utc).isoformat().startswith("2024-11-14T10:00:00")