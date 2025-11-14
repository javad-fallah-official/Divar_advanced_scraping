import time
import os
import psycopg2

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

    db = Database()

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
    host = os.environ.get("DB_HOST", "localhost")
    port = int(os.environ.get("DB_PORT", "5432"))
    user = os.environ.get("DB_USER", "postgres")
    password = os.environ.get("DB_PASSWORD", "admin")
    name = os.environ.get("DB_NAME", "Divar")
    con = psycopg2.connect(host=host, port=port, user=user, password=password, dbname=name)
    with con.cursor() as cur:
        cur.execute("select count(*) from posts")
        c = cur.fetchone()[0]
    print("DB count now:", c)
    con.close()


if __name__ == "__main__":
    main()

