from __future__ import annotations

import cProfile
import pstats
import io
from typing import Callable, Any, Dict

import tracemalloc

try:
    # Optional line profiler
    from line_profiler import LineProfiler
except Exception:  # pragma: no cover
    LineProfiler = None  # type: ignore


def run_cprofile(func: Callable[..., Any], *args: Any, **kwargs: Any) -> str:
    """Run cProfile on `func` and return a textual report as a string."""
    pr = cProfile.Profile()
    pr.enable()
    func(*args, **kwargs)
    pr.disable()
    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats("tottime")
    ps.print_stats(50)
    return s.getvalue()


def run_line_profiler(func: Callable[..., Any], *args: Any, **kwargs: Any) -> str:
    """Run line_profiler on `func` if available; return text report or a note."""
    if LineProfiler is None:
        return "line_profiler not installed; skipping."
    lp = LineProfiler()
    lp.add_function(func)
    lp_wrapper = lp(func)
    lp_wrapper(*args, **kwargs)
    s = io.StringIO()
    lp.print_stats(stream=s)
    return s.getvalue()


def measure_memory(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Dict[str, Any]:
    """Measure peak and current memory via tracemalloc for `func` execution."""
    tracemalloc.start()
    func(*args, **kwargs)
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {"current_bytes": current, "peak_bytes": peak}

