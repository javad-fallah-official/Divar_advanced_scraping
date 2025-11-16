import asyncio
import logging
import aiohttp
import random
from .scraper import fetch_final_html
from .parser import extract_ad_hrefs, parse_ad_page
from .db import get_conn, batch_upsert, init_db
from .config import BATCH_SIZE

async def retry_fetch(sess: aiohttp.ClientSession, url: str, attempts: int = 3) -> str:
    delay = 0.5
    for i in range(attempts):
        try:
            async with sess.get(url, timeout=30) as resp:
                if resp.status == 429:
                    raise Exception("rate limited")
                return await resp.text()
        except Exception:
            if i == attempts - 1:
                raise
            jitter = random.uniform(0, 0.2)
            await asyncio.sleep(delay + jitter)
            delay *= 2

async def fetch_and_parse(sess: aiohttp.ClientSession, url: str) -> dict:
    html_text = await retry_fetch(sess, url)
    return parse_ad_page(html_text, url)

async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    await init_db()
    listing_html = await fetch_final_html()
    ad_urls = extract_ad_hrefs(listing_html)
    logging.info("found %d ad URLs", len(ad_urls))
    counters = {
        "found_urls": len(ad_urls),
        "parsed_success": 0,
        "parse_failures": 0,
        "inserted_count": 0,
    }
    conn = await get_conn()
    batch: list[dict] = []
    sem = asyncio.Semaphore(8)
    async with aiohttp.ClientSession() as sess:
        async def bound_task(u: str) -> dict:
            async with sem:
                return await fetch_and_parse(sess, u)
        tasks = [asyncio.create_task(bound_task(u)) for u in ad_urls]
        for coro in asyncio.as_completed(tasks):
            try:
                parsed = await coro
                counters["parsed_success"] += 1
                batch.append(parsed)
            except Exception:
                counters["parse_failures"] += 1
            if len(batch) >= BATCH_SIZE:
                await batch_upsert(conn, batch)
                counters["inserted_count"] += len(batch)
                batch = []
        if batch:
            await batch_upsert(conn, batch)
            counters["inserted_count"] += len(batch)
    await conn.close()
    logging.info(
        "summary: found_urls=%d parsed_success=%d parse_failures=%d inserted_count=%d",
        counters["found_urls"],
        counters["parsed_success"],
        counters["parse_failures"],
        counters["inserted_count"],
    )

if __name__ == "__main__":
    asyncio.run(main())
