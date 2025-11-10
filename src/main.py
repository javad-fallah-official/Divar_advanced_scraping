import argparse
from datetime import datetime
from tqdm import tqdm

from scraper.listing_scraper import collect_listing_urls
from scraper.detail_scraper import scrape_post_details
from scraper.db import Database


def parse_args():
    parser = argparse.ArgumentParser(description="Divar Tehran motorcycles (Honda) scraper")
    parser.add_argument("--city", default="tehran", help="City slug, e.g., tehran")
    parser.add_argument("--category", default="motorcycles", help="Category slug, e.g., motorcycles")
    parser.add_argument("--brand", default="honda", help="Brand slug under category, e.g., honda")
    parser.add_argument("--non-negotiable", dest="non_negotiable", default="true", choices=["true", "false"], help="Filter out negotiables")
    parser.add_argument("--max-items", dest="max_items", type=int, default=200, help="Max listing URLs to collect")
    parser.add_argument("--headless", default="true", choices=["true", "false"], help="Run browser headless or not")
    return parser.parse_args()


def main():
    args = parse_args()
    non_negotiable = args.non_negotiable.lower() == "true"
    headless = args.headless.lower() == "true"

    print("Collecting listing URLs...")
    listing_urls = collect_listing_urls(
        city=args.city,
        category=args.category,
        brand=args.brand,
        non_negotiable=non_negotiable,
        max_items=args.max_items,
        headless=headless,
    )
    print(f"Collected {len(listing_urls)} unique listing URLs.")

    db = Database(db_path="data/divar.db")
    inserted, updated, skipped = 0, 0, 0

    print("Scraping detail pages and saving to DB...")
    for url in tqdm(listing_urls):
        try:
            details = scrape_post_details(url=url, headless=headless, non_negotiable=non_negotiable)
            if not details:
                skipped += 1
                continue
            res = db.upsert_post(details)
            if res == "inserted":
                inserted += 1
            elif res == "updated":
                updated += 1
            else:
                skipped += 1
        except Exception as e:
            skipped += 1
            print(f"Error scraping {url}: {e}")

    print(
        f"Done. Inserted: {inserted}, Updated: {updated}, Skipped: {skipped}. DB: data/divar.db"
    )


if __name__ == "__main__":
    main()

