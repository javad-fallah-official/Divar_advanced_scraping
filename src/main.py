import argparse
from datetime import datetime
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import asyncio
import time

from .scraper.listing_scraper import collect_listing_urls
from .scraper.detail_scraper import scrape_post_details
from .scraper.db import Database
from .scraper.metrics import log_event, sample_system
from .scraper_async.http import init_client, close_client
from .scraper_async.listing import collect_listing_urls_async
from .scraper_async.detail import scrape_post_details_async


def parse_args():
    parser = argparse.ArgumentParser(description="Divar Tehran motorcycles scraper")
    parser.add_argument("--city", default="tehran", help="City slug, e.g., tehran")
    parser.add_argument("--category", default="motorcycles", help="Category slug, e.g., motorcycles")
    parser.add_argument(
        "--brand",
        default="honda",
        help="Brand slug under category (e.g., honda). Use 'none' or 'all' to scrape all brands.",
    )
    parser.add_argument("--non-negotiable", dest="non_negotiable", default="true", choices=["true", "false"], help="Filter out negotiables")
    parser.add_argument("--max-items", dest="max_items", type=int, default=200, help="Max listing URLs to collect")
    parser.add_argument("--headless", default="true", choices=["true", "false"], help="Run browser headless or not")
    parser.add_argument("--workers", dest="workers", type=int, default=8, help="Concurrent detail fetch workers")
    parser.add_argument("--bulk-size", dest="bulk_size", type=int, default=50, help="Batch size for DB upserts")
    parser.add_argument("--http-timeout", dest="http_timeout", type=float, default=10.0, help="HTTP request timeout seconds")
    parser.add_argument("--single-url", dest="single_url", type=str, default="", help="Scrape only this post URL and print JSON")
    parser.add_argument("--no-db", dest="no_db", default="true", choices=["true", "false"], help="Skip DB writes in single mode")
    parser.add_argument("--async", dest="use_async", default="false", choices=["true", "false"], help="Use aiohttp+selectolax pipeline")
    parser.add_argument("--concurrency", dest="concurrency", type=int, default=20, help="Async concurrency")
    parser.add_argument("--async-fallback-playwright", dest="async_fallback", default="false", choices=["true", "false"], help="Retry failed async details with Playwright")
    parser.add_argument("--listing-mode", dest="listing_mode", default="auto", choices=["auto", "playwright", "api"], help="Choose listing collection strategy")
    return parser.parse_args()


def main():
    args = parse_args()
    non_negotiable = args.non_negotiable.lower() == "true"
    headless = args.headless.lower() == "true"
    no_db = args.no_db.lower() == "true"
    use_async = args.use_async.lower() == "true"
    async_fallback = args.async_fallback.lower() == "true"
    # Allow disabling brand filter with --brand none|all or empty string
    brand_arg = (args.brand or "").strip().lower()
    brand = None if brand_arg in {"", "none", "all"} else args.brand

    log_event("run_start", args=vars(args))
    if args.single_url and not use_async:
        url = args.single_url.strip()
        details = scrape_post_details(url=url, headless=headless, non_negotiable=non_negotiable, http_timeout=float(args.http_timeout))
        if not details:
            print("Failed to scrape details for:", url)
            return
        print(json.dumps(details, ensure_ascii=False))
        if not no_db:
            db = Database()
            db.upsert_post(details)
        return

    if args.single_url and use_async:
        async def run_single():
            await init_client(concurrency=args.concurrency, timeout=float(args.http_timeout), headers={"User-Agent": "Mozilla/5.0"})
            try:
                d = await scrape_post_details_async(args.single_url.strip(), non_negotiable=non_negotiable, timeout=float(args.http_timeout))
                if not d:
                    print("Failed to scrape details for:", args.single_url.strip())
                    return
                print(json.dumps(d, ensure_ascii=False))
                if not no_db:
                    db = Database()
                    db.upsert_post(d)
            finally:
                await close_client()
        asyncio.run(run_single())
        return

    print("Collecting listing URLs...")
    if use_async:
        mode = args.listing_mode
        if mode == "playwright":
            listing_urls = collect_listing_urls(
                city=args.city,
                category=args.category,
                brand=brand,
                non_negotiable=non_negotiable,
                max_items=args.max_items,
                headless=headless,
            )
        elif mode == "api":
            async def run_list():
                await init_client(concurrency=args.concurrency, timeout=float(args.http_timeout), headers={"User-Agent": "Mozilla/5.0"})
                try:
                    ls = await collect_listing_urls_async(args.city, args.category, brand, non_negotiable, max_items=args.max_items)
                    return ls
                finally:
                    await close_client()
            listing_urls = asyncio.run(run_list())
        else:
            async def run_list():
                await init_client(concurrency=args.concurrency, timeout=float(args.http_timeout), headers={"User-Agent": "Mozilla/5.0"})
                try:
                    ls = await collect_listing_urls_async(args.city, args.category, brand, non_negotiable, max_items=args.max_items)
                    return ls
                finally:
                    await close_client()
            listing_urls = asyncio.run(run_list())
            if len(listing_urls) < min(args.max_items, 300):
                listing_urls = collect_listing_urls(
                    city=args.city,
                    category=args.category,
                    brand=brand,
                    non_negotiable=non_negotiable,
                    max_items=args.max_items,
                    headless=headless,
                )
    else:
        listing_urls = collect_listing_urls(
            city=args.city,
            category=args.category,
            brand=brand,
            non_negotiable=non_negotiable,
            max_items=args.max_items,
            headless=headless,
        )
    print(f"Collected {len(listing_urls)} unique listing URLs.")
    log_event("listing_count", count=len(listing_urls))

    db = Database()
    inserted, updated, skipped = 0, 0, 0

    print("Scraping detail pages and saving to DB...")
    log_event("scrape_start", total=len(listing_urls))
    bulk_size = max(1, args.bulk_size)
    http_timeout = float(args.http_timeout)
    buffer = []
    t0 = time.perf_counter()
    if use_async:
        async def run_details():
            nonlocal inserted, updated, skipped
            await init_client(concurrency=args.concurrency, timeout=http_timeout, headers={"User-Agent": "Mozilla/5.0"})
            try:
                async def one(u):
                    d = await scrape_post_details_async(u, non_negotiable=non_negotiable, timeout=http_timeout)
                    return u, d
                tasks = [asyncio.create_task(one(u)) for u in listing_urls]
                pbar = tqdm(total=len(tasks))
                for t in asyncio.as_completed(tasks):
                    url, d = await t
                    if not d:
                        if async_fallback:
                            log_event("detail_fallback_start", url=url)
                            loop = asyncio.get_running_loop()
                            d2 = await loop.run_in_executor(None, lambda: scrape_post_details(url, headless, non_negotiable, http_timeout))
                            if d2:
                                buffer.append(d2)
                                log_event("detail_fallback_result", url=url, ok=True)
                            else:
                                skipped += 1
                                log_event("detail_fallback_result", url=url, ok=False)
                        else:
                            skipped += 1
                    else:
                        buffer.append(d)
                        if len(buffer) >= bulk_size:
                            res_ins, res_upd = db.upsert_posts_bulk(buffer)
                            inserted += res_ins
                            updated += res_upd
                            buffer.clear()
                    if (inserted + updated + skipped) % 20 == 0:
                        m = sample_system()
                        log_event("system_sample", **m)
                    pbar.update(1)
                pbar.close()
            finally:
                await close_client()
        asyncio.run(run_details())
    else:
        workers = max(1, args.workers)
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(scrape_post_details, url, headless, non_negotiable, http_timeout) for url in listing_urls]
            for fut in tqdm(as_completed(futs), total=len(futs)):
                try:
                    details = fut.result()
                    if not details:
                        skipped += 1
                        continue
                    buffer.append(details)
                    if len(buffer) >= bulk_size:
                        res_ins, res_upd = db.upsert_posts_bulk(buffer)
                        inserted += res_ins
                        updated += res_upd
                        buffer.clear()
                except Exception as e:
                    skipped += 1
                    print(f"Error scraping detail: {e}")
                if (inserted + updated + skipped) % 20 == 0:
                    m = sample_system()
                    log_event("system_sample", **m)
    if buffer:
        res_ins, res_upd = db.upsert_posts_bulk(buffer)
        inserted += res_ins
        updated += res_upd

    print(
        f"Done. Inserted: {inserted}, Updated: {updated}, Skipped: {skipped}. DB: postgres"
    )
    elapsed = time.perf_counter() - t0
    total = inserted + updated
    per_min = (total / elapsed) * 60 if elapsed > 0 else 0.0
    print(f"Elapsed: {elapsed:.2f}s, Throughput: {per_min:.2f} items/min")
    log_event("run_done", inserted=inserted, updated=updated, skipped=skipped)


if __name__ == "__main__":
    main()
