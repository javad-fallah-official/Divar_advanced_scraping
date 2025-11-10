import argparse
from tqdm import tqdm

from .scrape_divar_lib import collect_tokens, scrape_post_details
from .db import Database


def parse_args():
    parser = argparse.ArgumentParser(description="Divar library-based scraper (comparison)")
    parser.add_argument("--city", default="tehran", help="City, e.g., tehran")
    parser.add_argument("--category", default="motorcycles", help="Category, e.g., motorcycles")
    parser.add_argument("--brand", default="honda", help="Brand filter via heuristics")
    parser.add_argument("--non-negotiable", dest="non_negotiable", default="true", choices=["true", "false"], help="Filter negotiable posts")
    parser.add_argument("--max-items", dest="max_items", type=int, default=200, help="Max posts to process")
    return parser.parse_args()


def main():
    args = parse_args()
    non_negotiable = args.non_negotiable.lower() == "true"
    print("Collecting tokens from library...")
    tokens = collect_tokens(
        city=args.city,
        category=args.category,
        brand=args.brand,
        non_negotiable=non_negotiable,
        max_items=args.max_items,
    )
    print(f"Collected {len(tokens)} tokens.")

    db = Database(db_path="data/divar_lib.db")
    inserted, updated, skipped = 0, 0, 0
    print("Fetching details and saving...")
    for tok in tqdm(tokens):
        try:
            details = scrape_post_details(token=tok, non_negotiable=non_negotiable)
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
            print(f"Error scraping token {tok}: {e}")

    print(
        f"Done (library). Inserted: {inserted}, Updated: {updated}, Skipped: {skipped}. DB: data/divar_lib.db"
    )


if __name__ == "__main__":
    main()

