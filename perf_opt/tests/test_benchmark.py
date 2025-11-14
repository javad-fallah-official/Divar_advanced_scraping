from perf_opt.benchmark import run_bench


def test_run_bench_small():
    r = run_bench(1000)
    assert r.size == 1000
    assert r.build_ms >= 0
    assert r.price_query_ms >= 0
    assert r.year_query_ms >= 0
    assert r.mileage_query_ms >= 0
    assert r.mem_current >= 0 and r.mem_peak >= 0

