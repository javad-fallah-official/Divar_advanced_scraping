from perf_opt.profiling import run_cprofile, run_line_profiler, measure_memory


def small_func(n: int = 1000) -> int:
    s = 0
    for i in range(n):
        s += i
    return s


def test_cprofile_report():
    text = run_cprofile(small_func, 1000)
    assert isinstance(text, str) and len(text) > 0


def test_line_profiler_availability():
    # Should return a text report or a note about missing package
    text = run_line_profiler(small_func, 100)
    assert isinstance(text, str)


def test_tracemalloc_memory():
    mem = measure_memory(small_func, 1000)
    assert "current_bytes" in mem and "peak_bytes" in mem

