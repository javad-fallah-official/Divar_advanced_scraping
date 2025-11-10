from perf_opt.parallel import parallel_map_process, parallel_map_thread


# Define at module scope so it's picklable for ProcessPoolExecutor on Windows
def square(x: int) -> int:
    return x * x


def test_parallel_map_process_cpu_bound():
    items = list(range(10))
    res = parallel_map_process(square, items, max_workers=2)
    assert res == [i * i for i in items]


def test_parallel_map_thread_io_bound():
    import time

    def sleepy(x: int) -> int:
        time.sleep(0.001)
        return x

    items = list(range(10))
    res = parallel_map_thread(sleepy, items, max_workers=4)
    assert res == items
