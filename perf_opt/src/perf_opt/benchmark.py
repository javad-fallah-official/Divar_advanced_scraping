from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

from .engine import PostIndex
from .profiling import measure_memory


@dataclass
class BenchResult:
    size: int
    build_ms: float
    price_query_ms: float
    year_query_ms: float
    mileage_query_ms: float
    mem_current: int
    mem_peak: int


def synthetic_rows(n: int) -> List[Dict[str, object]]:
    rng = np.random.default_rng(42)
    rows: List[Dict[str, object]] = []
    for i in range(n):
        rows.append({
            "url": f"https://divar.ir/v/{i}",
            "title": f"Honda Motorcycle {i}",
            "city": "Tehran",
            "district": "District",
            "brand": "Honda",
            "model_year_jalali": int(1390 + int(rng.integers(0, 15))),
            "mileage_km": int(rng.integers(0, 100_000)),
            "color": "Red",
            "price_toman": int(rng.integers(10_000_000, 300_000_000)),
            "negotiable": int(rng.integers(0, 2)),
            "description": "Synthetic",
            "posted_at": None,
            "scraped_at": "2024-01-01T00:00:00",
        })
    return rows


def run_bench(size: int) -> BenchResult:
    rows = synthetic_rows(size)

    t0 = time.perf_counter()
    idx = PostIndex.from_rows(rows)
    build_ms = (time.perf_counter() - t0) * 1000.0

    # Ranged queries
    t1 = time.perf_counter()
    _ = idx.search_price_range(20_000_000, 200_000_000)
    price_query_ms = (time.perf_counter() - t1) * 1000.0

    t2 = time.perf_counter()
    _ = idx.search_year_range(1392, 1399)
    year_query_ms = (time.perf_counter() - t2) * 1000.0

    t3 = time.perf_counter()
    _ = idx.search_mileage_range(10_000, 80_000)
    mileage_query_ms = (time.perf_counter() - t3) * 1000.0

    mem = measure_memory(lambda: idx.filter_numeric(min_price=10_000_000, max_price=150_000_000))

    return BenchResult(
        size=size,
        build_ms=build_ms,
        price_query_ms=price_query_ms,
        year_query_ms=year_query_ms,
        mileage_query_ms=mileage_query_ms,
        mem_current=mem["current_bytes"],
        mem_peak=mem["peak_bytes"],
    )


def run_multi(sizes: List[int], out_path: Optional[str] = None) -> List[BenchResult]:
    results = [run_bench(s) for s in sizes]
    if out_path:
        data = [r.__dict__ for r in results]
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    return results


# --- Comparative baseline vs optimized ---

@dataclass
class CompareResult:
    size: int
    optimized_build_ms: float
    optimized_price_query_ms: float
    optimized_year_query_ms: float
    optimized_mileage_query_ms: float
    naive_price_query_ms: float
    naive_year_query_ms: float
    naive_mileage_query_ms: float


def _naive_search_range(rows: List[Dict[str, object]], key: str, lo: int, hi: int) -> List[int]:
    out = []
    for i, r in enumerate(rows):
        v = int(r.get(key) or 0)
        if lo <= v <= hi:
            out.append(i)
    return out


def run_bench_compare(size: int) -> CompareResult:
    rows = synthetic_rows(size)

    t0 = time.perf_counter()
    idx = PostIndex.from_rows(rows)
    opt_build_ms = (time.perf_counter() - t0) * 1000.0

    # Optimized
    t1 = time.perf_counter()
    _ = idx.search_price_range(20_000_000, 200_000_000)
    opt_price_ms = (time.perf_counter() - t1) * 1000.0

    t2 = time.perf_counter()
    _ = idx.search_year_range(1392, 1399)
    opt_year_ms = (time.perf_counter() - t2) * 1000.0

    t3 = time.perf_counter()
    _ = idx.search_mileage_range(10_000, 80_000)
    opt_mileage_ms = (time.perf_counter() - t3) * 1000.0

    # Naive scans
    t4 = time.perf_counter()
    _ = _naive_search_range(rows, "price_toman", 20_000_000, 200_000_000)
    naive_price_ms = (time.perf_counter() - t4) * 1000.0

    t5 = time.perf_counter()
    _ = _naive_search_range(rows, "model_year_jalali", 1392, 1399)
    naive_year_ms = (time.perf_counter() - t5) * 1000.0

    t6 = time.perf_counter()
    _ = _naive_search_range(rows, "mileage_km", 10_000, 80_000)
    naive_mileage_ms = (time.perf_counter() - t6) * 1000.0

    return CompareResult(
        size=size,
        optimized_build_ms=opt_build_ms,
        optimized_price_query_ms=opt_price_ms,
        optimized_year_query_ms=opt_year_ms,
        optimized_mileage_query_ms=opt_mileage_ms,
        naive_price_query_ms=naive_price_ms,
        naive_year_query_ms=naive_year_ms,
        naive_mileage_query_ms=naive_mileage_ms,
    )


def run_multi_compare(sizes: List[int], out_path: Optional[str] = None) -> List[CompareResult]:
    results = [run_bench_compare(s) for s in sizes]
    if out_path:
        data = [r.__dict__ for r in results]
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    return results
