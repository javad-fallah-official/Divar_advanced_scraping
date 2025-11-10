"""perf_opt: High-performance indexing and query toolkit.

This package provides:
- PostIndex: columnar arrays with O(1) lookups and O(log n) range searches
- Low-level utilities: bit-packing and memoryview helpers
- Profiling and benchmarking harnesses

The code is designed to run with or without optional accelerators (Numba, line_profiler).
"""

__all__ = [
    "PostIndex",
]

from .engine import PostIndex

