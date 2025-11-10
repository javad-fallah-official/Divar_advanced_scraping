from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

from .benchmark import run_multi
from .viz import plot_bench_json


def main() -> None:
    parser = argparse.ArgumentParser(prog="perf_opt", description="High-performance indexing and benchmarks")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_bench = sub.add_parser("bench", help="Run synthetic benchmarks and generate plot")
    p_bench.add_argument("sizes", nargs="+", type=int, help="Input sizes, e.g. 1_000 10_000 100_000")
    p_bench.add_argument("out_json", type=str, help="Path to write benchmark JSON")
    p_bench.add_argument("out_png", type=str, help="Path to write plot PNG")

    args = parser.parse_args()

    if args.cmd == "bench":
        # Ensure output directories exist
        Path(args.out_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out_png).parent.mkdir(parents=True, exist_ok=True)
        results = run_multi(args.sizes, out_path=args.out_json)
        plot_bench_json(args.out_json, args.out_png)
        print("Benchmark results saved:", args.out_json)
        print("Plot saved:", args.out_png)


if __name__ == "__main__":
    main()
