from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from typing import Callable, Iterable, List, Any, Optional


def parallel_map_process(fn: Callable[[Any], Any], items: Iterable[Any], max_workers: Optional[int] = None) -> List[Any]:
    """Run CPU-bound function `fn` across `items` using processes.

    Returns the results preserving the original order.
    """
    items_list = list(items)
    results: List[Any] = [None] * len(items_list)
    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        fut_to_idx = {ex.submit(fn, item): i for i, item in enumerate(items_list)}
        for fut in as_completed(fut_to_idx):
            i = fut_to_idx[fut]
            results[i] = fut.result()
    return results


def parallel_map_thread(fn: Callable[[Any], Any], items: Iterable[Any], max_workers: Optional[int] = None) -> List[Any]:
    """Run I/O-bound function `fn` across `items` using threads.

    Returns the results preserving the original order.
    """
    items_list = list(items)
    results: List[Any] = [None] * len(items_list)
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        fut_to_idx = {ex.submit(fn, item): i for i, item in enumerate(items_list)}
        for fut in as_completed(fut_to_idx):
            i = fut_to_idx[fut]
            results[i] = fut.result()
    return results

