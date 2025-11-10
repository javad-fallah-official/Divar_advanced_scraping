import os
import time
import sqlite3

from scraper.listing_scraper import collect_listing_urls
from scraper.detail_scraper import scrape_post_details_http
from scraper.db import Database


def main():
    cities = [
        "tehran",
        "karaj",
        "mashhad",
        "isfahan",
        "shiraz",
        "tabriz",
        "qom",
        "ahvaz",
        "kermanshah",
        "rasht",
    ]
    category = "motorcycles"

    urls = set()
    for city in cities:
        us = collect_listing_urls(city=city, category=category, brand=None, non_negotiable=False, max_items=60, headless=True)
        print(f"{city}: {len(us)} URLs")
        urls.update(us)

    urls = list(urls)
    print("Total unique URLs:", len(urls))
    if len(urls) > 200:
        urls = urls[:200]

    os.makedirs("data", exist_ok=True)
    db = Database(db_path="data/divar.db")

    inserted = 0
    for i, url in enumerate(urls, 1):
        d = scrape_post_details_http(url, non_negotiable=False)
        ok = bool(d)
        print(f"[{i}/{len(urls)}] detail ok={ok} {url}")
        if d:
            db.upsert_post(d)
            inserted += 1
        time.sleep(0.15)

    print("Inserted:", inserted)
    con = sqlite3.connect("data/divar.db")
    c = con.execute("select count(*) from posts").fetchone()[0]
    print("DB count now:", c)
    con.close()


if __name__ == "__main__":
    main()

