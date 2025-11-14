from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

try:  # Optional acceleration
    import numba as nb  # type: ignore
except Exception:  # pragma: no cover
    nb = None  # type: ignore

from .datastructures import pack_price_year_flags
from .parallel import parallel_map_process, parallel_map_thread


@dataclass
class PostIndex:
    """High-performance columnar index for Divar posts.

    - O(1) URL lookup via a hash map
    - O(log n) range queries via pre-sorted views and binary search
    - Vectorized filters using NumPy; optional Numba acceleration
    """

    urls: np.ndarray
    title: np.ndarray
    city: np.ndarray
    district: np.ndarray
    brand: np.ndarray
    year: np.ndarray
    mileage: np.ndarray
    price: np.ndarray
    negotiable: np.ndarray
    description: np.ndarray
    posted_at: np.ndarray
    scraped_at: np.ndarray

    # Derived structures
    _url_to_idx: Dict[str, int]
    _sorted_by_price: np.ndarray
    _sorted_by_year: np.ndarray
    _sorted_by_mileage: np.ndarray
    _packed_meta: np.ndarray

    @staticmethod
    def from_rows(rows: Sequence[Dict[str, object]]) -> "PostIndex":
        n = len(rows)
        urls = np.empty(n, dtype=object)
        title = np.empty(n, dtype=object)
        city = np.empty(n, dtype=object)
        district = np.empty(n, dtype=object)
        brand = np.empty(n, dtype=object)
        year = np.empty(n, dtype=np.int32)
        mileage = np.empty(n, dtype=np.int32)
        price = np.empty(n, dtype=np.int64)
        negotiable = np.empty(n, dtype=np.int8)
        description = np.empty(n, dtype=object)
        posted_at = np.empty(n, dtype=object)
        scraped_at = np.empty(n, dtype=object)

        for i, r in enumerate(rows):
            urls[i] = r.get("url")
            title[i] = r.get("title")
            city[i] = r.get("city")
            district[i] = r.get("district")
            brand[i] = r.get("brand")
            year[i] = int(r.get("model_year_jalali") or 0)
            mileage[i] = int(r.get("mileage_km") or 0)
            price[i] = int(r.get("price_toman") or 0)
            negotiable[i] = int(r.get("negotiable") or 0)
            description[i] = r.get("description")
            posted_at[i] = r.get("posted_at")
            scraped_at[i] = r.get("scraped_at")

        url_to_idx = {u: i for i, u in enumerate(urls)}

        # Pre-sorted index views
        sorted_by_price = np.argsort(price, kind="mergesort")
        sorted_by_year = np.argsort(year, kind="mergesort")
        sorted_by_mileage = np.argsort(mileage, kind="mergesort")

        packed_meta = np.empty(n, dtype=np.int64)
        for i in range(n):
            packed_meta[i] = pack_price_year_flags(int(price[i]), int(year[i]), int(negotiable[i]))

        return PostIndex(
            urls=urls,
            title=title,
            city=city,
            district=district,
            brand=brand,
            year=year,
            mileage=mileage,
            price=price,
            negotiable=negotiable,
            description=description,
            posted_at=posted_at,
            scraped_at=scraped_at,
            _url_to_idx=url_to_idx,
            _sorted_by_price=sorted_by_price,
            _sorted_by_year=sorted_by_year,
            _sorted_by_mileage=sorted_by_mileage,
            _packed_meta=packed_meta,
        )

    # O(1) lookup
    def lookup_url(self, url: str) -> Optional[int]:
        return self._url_to_idx.get(url)

    # O(log n) range searches via binary search over sorted views
    def search_price_range(self, min_price: int, max_price: int) -> List[int]:
        order = self._sorted_by_price
        vals = self.price[order]
        left = np.searchsorted(vals, min_price, side="left")
        right = np.searchsorted(vals, max_price, side="right")
        return order[left:right].tolist()

    def search_year_range(self, min_year: int, max_year: int) -> List[int]:
        order = self._sorted_by_year
        vals = self.year[order]
        left = np.searchsorted(vals, min_year, side="left")
        right = np.searchsorted(vals, max_year, side="right")
        return order[left:right].tolist()

    def search_mileage_range(self, min_mileage: int, max_mileage: int) -> List[int]:
        order = self._sorted_by_mileage
        vals = self.mileage[order]
        left = np.searchsorted(vals, min_mileage, side="left")
        right = np.searchsorted(vals, max_mileage, side="right")
        return order[left:right].tolist()

    # Vectorized filters with optional Numba
    def filter_numeric(
        self,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        min_year: Optional[int] = None,
        max_year: Optional[int] = None,
        min_mileage: Optional[int] = None,
        max_mileage: Optional[int] = None,
        use_numba: bool = False,
    ) -> np.ndarray:
        p = self.price
        y = self.year
        m = self.mileage

        if use_numba and nb is not None:
            return _filter_numba(p, y, m, min_price or -1, max_price or 2**63 - 1, min_year or -1, max_year or 2**31 - 1, min_mileage or -1, max_mileage or 2**31 - 1)

        mask = np.ones(len(p), dtype=bool)
        if min_price is not None:
            mask &= p >= min_price
        if max_price is not None:
            mask &= p <= max_price
        if min_year is not None:
            mask &= y >= min_year
        if max_year is not None:
            mask &= y <= max_year
        if min_mileage is not None:
            mask &= m >= min_mileage
        if max_mileage is not None:
            mask &= m <= max_mileage
        return mask

    def filter_numeric_parallel(
        self,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        min_year: Optional[int] = None,
        max_year: Optional[int] = None,
        min_mileage: Optional[int] = None,
        max_mileage: Optional[int] = None,
        mode: str = "process",
        workers: Optional[int] = None,
    ) -> np.ndarray:
        """Parallelize numeric filtering across chunks.

        Use processes for CPU-bound filters; threads for I/O-bound scenarios.
        """
        n = len(self.price)
        chunks: List[Tuple[int, int]] = []
        step = max(1, n // (workers or 4) or 1)
        start = 0
        while start < n:
            end = min(n, start + step)
            chunks.append((start, end))
            start = end

        def task(chunk: Tuple[int, int]) -> np.ndarray:
            s, e = chunk
            sl = slice(s, e)
            p = self.price[sl]
            y = self.year[sl]
            m = self.mileage[sl]
            mask = np.ones(e - s, dtype=bool)
            if min_price is not None:
                mask &= p >= min_price
            if max_price is not None:
                mask &= p <= max_price
            if min_year is not None:
                mask &= y >= min_year
            if max_year is not None:
                mask &= y <= max_year
            if min_mileage is not None:
                mask &= m >= min_mileage
            if max_mileage is not None:
                mask &= m <= max_mileage
            return mask

        if mode == "thread":
            parts = parallel_map_thread(task, chunks, max_workers=workers)
        else:
            parts = parallel_map_process(task, chunks, max_workers=workers)

        return np.concatenate(parts)

    def to_records(self, indices: Iterable[int]) -> List[Dict[str, object]]:
        out: List[Dict[str, object]] = []
        for i in indices:
            out.append({
                "url": self.urls[i],
                "title": self.title[i],
                "city": self.city[i],
                "district": self.district[i],
                "brand": self.brand[i],
                "model_year_jalali": int(self.year[i]),
                "mileage_km": int(self.mileage[i]),
                "price_toman": int(self.price[i]),
                "negotiable": int(self.negotiable[i]),
                "description": self.description[i],
                "posted_at": self.posted_at[i],
                "scraped_at": self.scraped_at[i],
            })
        return out


if nb is not None:  # Optional JIT for numerical filters
    @nb.njit(cache=True)
    def _filter_numba(p: np.ndarray, y: np.ndarray, m: np.ndarray,
                      min_p: int, max_p: int, min_y: int, max_y: int, min_m: int, max_m: int) -> np.ndarray:
        n = p.shape[0]
        out = np.ones(n, dtype=np.bool_)
        for i in range(n):
            if out[i]:
                if min_p != -1 and p[i] < min_p:
                    out[i] = False
                    continue
                if max_p != (2**63 - 1) and p[i] > max_p:
                    out[i] = False
                    continue
                if min_y != -1 and y[i] < min_y:
                    out[i] = False
                    continue
                if max_y != (2**31 - 1) and y[i] > max_y:
                    out[i] = False
                    continue
                if min_m != -1 and m[i] < min_m:
                    out[i] = False
                    continue
                if max_m != (2**31 - 1) and m[i] > max_m:
                    out[i] = False
                    continue
        return out
else:
    def _filter_numba(*args, **kwargs):  # type: ignore
        raise RuntimeError("Numba not available")

