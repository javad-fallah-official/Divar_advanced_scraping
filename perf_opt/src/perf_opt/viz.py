from __future__ import annotations

import json
from typing import List

import matplotlib.pyplot as plt
import seaborn as sns


def plot_bench_json(input_json_path: str, output_png_path: str) -> None:
    """Generate comparative performance plot from benchmark JSON."""
    with open(input_json_path, "r", encoding="utf-8") as f:
        data: List[dict] = json.load(f)

    sizes = [d["size"] for d in data]
    build = [d["build_ms"] for d in data]
    price_q = [d["price_query_ms"] for d in data]
    year_q = [d["year_query_ms"] for d in data]
    mileage_q = [d["mileage_query_ms"] for d in data]

    sns.set(style="whitegrid")
    plt.figure(figsize=(8, 5))
    plt.plot(sizes, build, label="build_ms", marker="o")
    plt.plot(sizes, price_q, label="price_query_ms", marker="o")
    plt.plot(sizes, year_q, label="year_query_ms", marker="o")
    plt.plot(sizes, mileage_q, label="mileage_query_ms", marker="o")
    plt.xlabel("Dataset size (rows)")
    plt.ylabel("Time (ms)")
    plt.title("perf_opt benchmark results")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_png_path)


def plot_compare_json(input_json_path: str, output_png_path: str) -> None:
    """Plot optimized vs naive query times across sizes."""
    with open(input_json_path, "r", encoding="utf-8") as f:
        data: List[dict] = json.load(f)

    sizes = [d["size"] for d in data]
    opt_price = [d["optimized_price_query_ms"] for d in data]
    opt_year = [d["optimized_year_query_ms"] for d in data]
    opt_mileage = [d["optimized_mileage_query_ms"] for d in data]
    naive_price = [d["naive_price_query_ms"] for d in data]
    naive_year = [d["naive_year_query_ms"] for d in data]
    naive_mileage = [d["naive_mileage_query_ms"] for d in data]

    sns.set(style="whitegrid")
    plt.figure(figsize=(9, 6))
    plt.plot(sizes, opt_price, label="opt_price", marker="o")
    plt.plot(sizes, naive_price, label="naive_price", marker="x")
    plt.plot(sizes, opt_year, label="opt_year", marker="o")
    plt.plot(sizes, naive_year, label="naive_year", marker="x")
    plt.plot(sizes, opt_mileage, label="opt_mileage", marker="o")
    plt.plot(sizes, naive_mileage, label="naive_mileage", marker="x")
    plt.xlabel("Dataset size (rows)")
    plt.ylabel("Query time (ms)")
    plt.title("Optimized vs Naive query performance")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_png_path)
