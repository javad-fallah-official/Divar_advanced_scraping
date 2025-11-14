import os
from typing import Dict, Any
import psycopg2
import psycopg2.extras


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS posts (
    url TEXT PRIMARY KEY,
    title TEXT,
    city TEXT,
    district TEXT,
    brand TEXT,
    model_year_jalali INT,
    mileage_km INT,
    color TEXT,
    price_toman BIGINT,
    negotiable INT,
    description TEXT,
    posted_at TEXT,
    scraped_at TEXT
);
"""


class Database:
    def __init__(self, db_path: str = ""):
        host = os.environ.get("DB_HOST", "localhost")
        port = int(os.environ.get("DB_PORT", "5432"))
        user = os.environ.get("DB_USER", "postgres")
        password = os.environ.get("DB_PASSWORD", "admin")
        name = os.environ.get("DB_NAME", "Divar")
        self.conn = psycopg2.connect(host=host, port=port, user=user, password=password, dbname=name)
        self.conn.autocommit = True
        with self.conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)

    def upsert_post(self, post: Dict[str, Any]) -> str:
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
        set_clause = ", ".join([f"{c}=excluded.{c}" for c in cols if c != "url"]) 
        sql = f"INSERT INTO posts ({','.join(cols)}) VALUES ({','.join(['%s'] * len(cols))}) ON CONFLICT (url) DO UPDATE SET {set_clause}"
        from .metrics import log_event, Timer
        t = Timer()
        with self.conn.cursor() as cur:
            cur.execute(sql, values)
        log_event("db_upsert", url=url, ms=t.ms())
        return "updated" if existed_before else "inserted"

    def exists(self, url: str) -> bool:
        with self.conn.cursor() as cur:
            cur.execute("SELECT 1 FROM posts WHERE url=%s", (url,))
            return cur.fetchone() is not None
