import os
import sqlite3
from typing import Dict, Any


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS posts (
    url TEXT PRIMARY KEY,
    title TEXT,
    city TEXT,
    district TEXT,
    brand TEXT,
    model_year_jalali INTEGER,
    mileage_km INTEGER,
    color TEXT,
    price_toman INTEGER,
    negotiable INTEGER,
    description TEXT,
    posted_at TEXT,
    scraped_at TEXT
);
"""


class Database:
    def __init__(self, db_path: str = "data/divar.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA foreign_keys=ON;")
        with self.conn:
            self.conn.executescript(SCHEMA_SQL)

    def upsert_post(self, post: Dict[str, Any]) -> str:
        # Check existence BEFORE upsert to correctly report inserted vs updated
        url = post.get("url")
        existed_before = self.exists(url)

        cols = [
            "url",
            "title",
            "city",
            "district",
            "brand",
            "model_year_jalali",
            "mileage_km",
            "color",
            "price_toman",
            "negotiable",
            "description",
            "posted_at",
            "scraped_at",
        ]
        values = [post.get(c) for c in cols]
        placeholders = ",".join(["?"] * len(cols))
        set_clause = ", ".join([f"{c}=excluded.{c}" for c in cols if c != "url"]) 
        sql = f"INSERT INTO posts ({','.join(cols)}) VALUES ({placeholders}) ON CONFLICT(url) DO UPDATE SET {set_clause};"
        with self.conn:
            self.conn.execute(sql, values)

        return "updated" if existed_before else "inserted"

    def exists(self, url: str) -> bool:
        cur = self.conn.execute("SELECT 1 FROM posts WHERE url=?", (url,))
        return cur.fetchone() is not None
