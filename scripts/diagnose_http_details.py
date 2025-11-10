import os
import sqlite3
import time

from scraper.listing_scraper import collect_listing_urls
from scraper.detail_scraper import scrape_post_details_http
from scraper.db import Database


def main():
    print("Collecting listing URLs (HTTP SSR)...")
    urls = collect_listing_urls(city="tehran", category="motorcycles", brand=None, non_negotiable=False, max_items=50, headless=True)
    print("Collected:", len(urls))
    print("Sample:", urls[:10])

    # Ensure DB exists
    os.makedirs("data", exist_ok=True)
    db = Database(db_path="data/divar.db")

    inserted = 0
    # Try to insert up to 100 posts via HTTP-only details
    for url in urls[:100]:
        d = scrape_post_details_http(url, non_negotiable=False)
        print("HTTP detail ok:", bool(d), "for", url)
        if d:
            db.upsert_post(d)
            inserted += 1
            time.sleep(0.2)
    print("Inserted via HTTP:", inserted)

    con = sqlite3.connect("data/divar.db")
    c = con.execute("select count(*) from posts").fetchone()[0]
    print("DB count now:", c)
    con.close()


if __name__ == "__main__":
    main()
