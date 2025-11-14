import pytest

from perf_opt.engine import PostIndex


def sample_rows():
    return [
        {
            "url": "https://divar.ir/v/1",
            "title": "Yamaha",
            "city": "Tehran",
            "district": "D1",
            "brand": "Yamaha",
            "model_year_jalali": 1395,
            "mileage_km": 20000,
            "color": "Blue",
            "price_toman": 100_000_000,
            "negotiable": 1,
            "description": "",
            "posted_at": None,
            "scraped_at": "2024-01-01T00:00:00",
        },
        {
            "url": "https://divar.ir/v/2",
            "title": "Honda",
            "city": "Tehran",
            "district": "D2",
            "brand": "Honda",
            "model_year_jalali": 1392,
            "mileage_km": 5000,
            "color": "Red",
            "price_toman": 50_000_000,
            "negotiable": 0,
            "description": "",
            "posted_at": None,
            "scraped_at": "2024-01-02T00:00:00",
        },
    ]


def test_index_build_and_lookup():
    idx = PostIndex.from_rows(sample_rows())
    assert len(idx.urls) == 2
    assert idx.lookup_url("https://divar.ir/v/1") == 0
    assert idx.lookup_url("https://divar.ir/v/2") == 1
    assert idx.lookup_url("https://divar.ir/v/404") is None


def test_range_queries():
    idx = PostIndex.from_rows(sample_rows())
    pr = idx.search_price_range(60_000_000, 150_000_000)
    assert set(pr) == {0}
    yr = idx.search_year_range(1390, 1393)
    assert set(yr) == {1}
    mr = idx.search_mileage_range(0, 10000)
    assert set(mr) == {1}


def test_vector_filters():
    idx = PostIndex.from_rows(sample_rows())
    mask = idx.filter_numeric(min_price=40_000_000, max_year=1395)
    assert mask.sum() == 2
    mask2 = idx.filter_numeric(min_mileage=10000)
    assert mask2.sum() == 1

