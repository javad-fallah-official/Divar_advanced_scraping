import asyncio
import logging
import aiohttp
from scraper import fetch_final_html
from parser import extract_ad_hrefs, parse_ad_page
from db import get_conn, batch_upsert, init_db
from config import BATCH_SIZE

async def fetch_and_parse(sess: aiohttp.ClientSession, url: str) -> dict:
    async with sess.get(url, timeout=30) as resp:
        html_text = await resp.text()
    return parse_ad_page(html_text, url)

async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    await init_db()
    listing_html = await fetch_final_html()
    ad_urls = extract_ad_hrefs(listing_html)
    logging.info("found %d ad URLs", len(ad_urls))
    conn = await get_conn()
    batch: list[dict] = []
    sem = asyncio.Semaphore(8)
    async with aiohttp.ClientSession() as sess:
        async def bound_task(u: str) -> dict:
            async with sem:
                return await fetch_and_parse(sess, u)
        tasks = [asyncio.create_task(bound_task(u)) for u in ad_urls]
        for coro in asyncio.as_completed(tasks):
            parsed = await coro
            batch.append(parsed)
            if len(batch) >= BATCH_SIZE:
                await batch_upsert(conn, batch)
                batch = []
        if batch:
            await batch_upsert(conn, batch)
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())