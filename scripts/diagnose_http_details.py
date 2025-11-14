import os
import time
import psycopg2

from scraper.listing_scraper import collect_listing_urls
from scraper.detail_scraper import scrape_post_details_http
from scraper.db import Database


def main():
    print("Collecting listing URLs (HTTP SSR)...")
    urls = collect_listing_urls(city="tehran", category="motorcycles", brand=None, non_negotiable=False, max_items=50, headless=True)
    print("Collected:", len(urls))
    print("Sample:", urls[:10])

    # Ensure DB exists
    db = Database()

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
