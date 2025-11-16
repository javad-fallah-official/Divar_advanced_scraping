import asyncpg
from config import DB

async def init_db() -> None:
    conn = await asyncpg.connect(**DB)
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS motorcycles (
          id TEXT PRIMARY KEY,
          url TEXT NOT NULL,
          title TEXT,
          price TEXT,
          description TEXT,
          location TEXT,
          specs JSONB,
          date_posted TIMESTAMP,
          scraped_at TIMESTAMP DEFAULT NOW(),
          raw_html TEXT
        );
        """
    )
    await conn.close()

async def get_conn() -> asyncpg.Connection:
    return await asyncpg.connect(**DB)

async def batch_upsert(conn: asyncpg.Connection, rows: list[dict]) -> None:
    async with conn.transaction():
        stmt = (
            """
            INSERT INTO motorcycles (id, url, title, price, description, location, specs, date_posted, raw_html)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
            ON CONFLICT (id) DO NOTHING
            """
        )
        for r in rows:
            await conn.execute(
                stmt,
                r["id"],
                r["url"],
                r.get("title"),
                r.get("price"),
                r.get("description"),
                r.get("location"),
                r.get("specs"),
                r.get("date_posted"),
                r.get("raw_html"),
            )