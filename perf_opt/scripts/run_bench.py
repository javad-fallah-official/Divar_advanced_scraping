from __future__ import annotations

import argparse
from pathlib import Path

from perf_opt.benchmark import run_multi
from perf_opt.viz import plot_bench_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Run perf_opt benchmarks and plots")
    parser.add_argument("out_json", type=str, help="Output JSON path")
    parser.add_argument("out_png", type=str, help="Output plot PNG path")
    parser.add_argument("sizes", nargs="+", type=int, help="Sizes e.g. 1000 10000 100000")
    args = parser.parse_args()

    Path(args.out_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_png).parent.mkdir(parents=True, exist_ok=True)
    run_multi(args.sizes, out_path=args.out_json)
    plot_bench_json(args.out_json, args.out_png)
    print("Done:", args.out_json, args.out_png)


if __name__ == "__main__":
    main()

