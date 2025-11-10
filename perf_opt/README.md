# perf_opt

High-performance indexing and query toolkit demonstrating practical speedups over naive Python implementations.

Features
- Columnar `PostIndex` with O(1) URL lookup and O(log n) range queries.
- Vectorized numeric filters with optional Numba acceleration.
- Parallel filtering via processes or threads.
- Low-level bit-packing and zero-copy memoryview helpers.
- Profiling utilities: cProfile, line_profiler (optional), tracemalloc.
- Benchmarks with synthetic datasets and visualization graphs.
- Packaging: wheel build (`pyproject.toml`) and single-file zipapp (`perf_opt.pyz`).

Quick Start
- Install: `pip install -e perf_opt` or `pip install .` from `perf_opt`.
- CLI: `python -m perf_opt --help` or `perf_opt bench 1000 10000 50000 out/bench.json out/bench.png`.
- Run script: `python perf_opt/scripts/run_bench.py out/bench.json out/bench.png 1000 10000 50000`.

Profiling
- cProfile: use `perf_opt.profiling.run_cprofile(func, *args)`.
- line_profiler: install `line_profiler`, then `perf_opt.profiling.run_line_profiler(func, *args)`.
- Memory: `perf_opt.profiling.measure_memory(func, *args)` returns current and peak bytes.

Benchmarks
- Programmatic: `perf_opt.benchmark.run_multi([1000, 10000, 50000], out_path="out/bench.json")`.
- Visualization: `perf_opt.viz.plot_bench_json("out/bench.json", "out/bench.png")`.

Packaging
- Wheel: from `perf_opt/`, run `python -m build` (requires `build`). Output in `dist/`.
- Zipapp: `python perf_opt/scripts/build_zipapp.py` creates `perf_opt/dist/perf_opt.pyz`.

Design Highlights
- Data locality: numeric columns in contiguous NumPy arrays for cache-friendly scans.
- Pre-sorted views: uses `np.argsort` and `np.searchsorted` for logarithmic range lookups.
- Optional JIT: Numba kernel for tight numeric filter loops.
- Parallelism: chunked filtering via `concurrent.futures` wrappers.

Testing
- Run `pytest` inside `perf_opt/`. Tests cover `engine`, low-level utils, profiling, parallelism, and benchmarks.

