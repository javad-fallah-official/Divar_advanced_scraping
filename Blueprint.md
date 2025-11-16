# Detailed blueprint — Divar motorcycles scraper (async Playwright + lxml + asyncpg)

This is a complete, **line-by-line**, no-ambiguity blueprint you can hand to your agent. It combines a formal technical specification with a step-by-step instructional manual and includes everything needed: environment, code scaffolding, selector strategy, parsing rules, DB schema, batching, error handling, tests, logging, CI/deployment hints, and operational notes.

> Target: scrape `https://divar.ir/s/tehran/motorcycles` (only this URL for now).
> Goals: extract `Title, Price, Description, Location, Specs, Date, Color, Year made, Mileage` and store in PostgreSQL. Use the last part of each ad URL (the token after `/v/`) as a unique `id`. Use async Playwright (headless), parse final HTML with `lxml`, insert with `asyncpg`. Expect ≤ 2k ads, one-time scrape.

All field examples and DOM evidence below are taken from a sample ad page I inspected; see the cited source for the ad content used while writing this blueprint. ([سایت دیوار][1])

---

# 0 — Important legal & operational note

1. **Check legality & terms**: before running a scraper against a site in production, the agent must review Divar’s Terms of Service and `robots.txt`. This blueprint assumes a one-time personal use scrape. If you intend repeated or large-scale scraping you must confirm you are allowed to by site policy or contact the site.
2. **Politeness**: even if you only scrape once, implement rate-limiting and avoid aggressive parallel requests. Use headless browser automation to mimic normal user behavior (scroll + click), not raw flood of requests.

---

# 1 — Environment & prerequisites

1. **System requirements**

   * Python 3.11+ (3.10 acceptable)
   * PostgreSQL 12+
   * Enough RAM (for up to ~2k cached ad HTMLs; 1–2 GB free should be OK)

2. **Project layout (recommended)**

```
divar_motor_scraper/
├─ venv/                     # virtualenv
├─ README.md
├─ requirements.txt
├─ .env                      # DB and config values (gitignored)
├─ src/
│  ├─ __init__.py
│  ├─ config.py
│  ├─ db.py
│  ├─ scraper.py
│  ├─ parser.py
│  ├─ models.py
│  ├─ utils.py
│  └─ run.py
└─ tests/
   ├─ test_parser.py
   └─ test_scraper_simulation.py
```

3. **Install packages**

```bash
python -m venv venv
source venv/bin/activate
pip install playwright lxml asyncpg python-dotenv aiofiles
# Install playwright browsers
python -m playwright install
```

4. **requirements.txt** (example)

```
playwright>=1.40
lxml>=4.9
asyncpg>=0.27
python-dotenv
aiofiles
```

5. **.env** (example — **do not** commit)

```
DB_USER=youruser
DB_PASS=yourpass
DB_NAME=divar_db
DB_HOST=127.0.0.1
DB_PORT=5432
TARGET_URL=https://divar.ir/s/tehran/motorcycles
USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...
```

6. **Coding conventions**

   * Async functions prefixed with `async_` where appropriate.
   * snake_case for files, functions, variables.
   * Clear logging via Python `logging` module (INFO/DEBUG/ERROR).

---

# 2 — High-level architecture and flow (textual diagram)

1. Start `run.py` → loads config → opens DB connection (`asyncpg`) → launches Playwright (chromium headless).
2. Navigate to `https://divar.ir/s/tehran/motorcycles`.
3. Repeatedly scroll and click the “load more” button until it disappears (or max iterations reached).
4. After final load, call `page.content()` once → pass HTML to `parser.py`.
5. `parser.py` extracts ad URLs, dedupes them by ID (last token of `/v/...`), and for each ad URL extracts required fields (Title, Price, ...).

   * Option A (fast): parse everything from the final listing HTML if the listing includes all fields/links.
   * Option B (more consistent): fetch individual ad pages (only if necessary to get full Description/Specs). For speed, prefer parsing fields available in the listing page; fetch details only for missing fields.
6. Batch-insert records into PostgreSQL with `INSERT ... ON CONFLICT DO NOTHING` using `asyncpg` and parameterized queries.
7. Log summary and close connections.

---

# 3 — Selectors & DOM strategy (robust approach)

**Notes from inspecting a real ad page**: the page contains Title, time/location line, specs block with "کارکرد", "سال تولید", "رنگ", price block, and a description section. Example values exist on the sample ad. ([سایت دیوار][1])

## 3.1 Load-more button (listing page)

The “load more” button HTML you gave (and typically present on the listing page) looks like:

```html
<button class="kt-button kt-button--primary kt-button--outlined post-list__load-more-btn-be092" ...>
  <span class="kt-text-truncate no-pointer-event">آگهی‌های بیشتر</span>
</button>
```

**Use this exact class substring** to click. CSS selector to use:

```css
button.post-list__load-more-btn-be092
```

or more defensive:

```css
button[class*="post-list__load-more-btn"]
```

## 3.2 Ad links selector (listing)

Collect ad links from the listing with a robust XPath/CSS that finds anchors containing `/v/`:

* XPath:

```xpath
//a[contains(@href, '/v/')]/@href
```

* CSS approach (Playwright):

```python
await page.query_selector_all("a[href*='/v/']")
```

**Then normalize hrefs**:

* If href is relative (starts with `/v/...`) prefix with `https://divar.ir`.

**Unique ID**:

* Extract the last path segment after the final `/`. Example:

  * `https://divar.ir/v/.../Aalrwjwc` → id = `Aalrwjwc`.

## 3.3 Fields in an ad page — suggested selectors & fallback rules

The ad page structure can vary; use primary + fallback selectors and string cleanup. Examples below are robust patterns; the agent should implement fallback chains for each field.

### Title

Primary:

```xpath
//h1[normalize-space()]//text()
```

Fallback:

```xpath
//meta[@property='og:title']/@content
```

### Price

Primary:

```xpath
//text()[contains(.,'تومان') or contains(.,'ريال') or contains(.,'قیمت')]/parent::*
```

Better reliable:

```xpath
//section//strong[contains(.,'قیمت')]/text()
```

Fallback:

```xpath
//meta[@property='product:price:amount']/@content
```

### Date & Location (often in the same line)

The sample shows a line like: `۱۷ ساعت پیش در تهران، شهرک غرب`
Primary:

```xpath
//div[contains(.,'در') and contains(.,'تهران')]/text()
```

Or:

```xpath
//time/@datetime           # if available
```

Parser must split that line into `date_posted` and `location_text`.

### Description

Primary:

```xpath
//h2[contains(., 'توضیحات')]/following-sibling::div[1]//text()
```

Fallback:

```xpath
//div[@class and contains(.,'توضیحات')]/text()
```

### Specs (key-value block)

Divar often renders specs as a horizontal list or table. Strategy:

* Locate the specs container by looking for keywords like `"کارکرد"`, `"سال تولید"`, `"رنگ"`:

```xpath
//div[contains(., 'کارکرد') or contains(., 'سال تولید') or contains(., 'رنگ')]
```

* OR select a spec list:

```xpath
//ul[contains(@class,'ad-params') or contains(@class,'ad-specs')]/li
```

* For each spec `li`, try to split by `:` or newline, or parse two spans (label/value).

From the sample, the spec line content looks like:

```
کارکرد مدل (سال تولید)رنگ
۰ ۱۴۰۳ مشکی
```

So you may need to:

* Read labels separately (possibly in the DOM above or as the previous sibling), then read values; if labels are not directly linked to values, rely on positional mapping.

**Key spec keys to map**:

* `color` ← `"رنگ"`
* `year_made` ← `"سال تولید"`, `"مدل (سال تولید)"`, or numeric year in Persian digits (convert to Gregorian if needed).
* `mileage` ← `"کارکرد"` or `"کارکرد مدل"`

### Images (optional)

Image count can be useful. Selector:

```xpath
//img[contains(@src,'/images')]/@src
```

---

# 4 — Data model (Postgres schema)

Design for flexibility, keep raw HTML for audit and `specs` as JSONB.

```sql
CREATE TABLE IF NOT EXISTS motorcycles (
  id TEXT PRIMARY KEY,            -- token after /v/
  url TEXT NOT NULL,
  title TEXT,
  price TEXT,
  description TEXT,
  location TEXT,
  specs JSONB,                    -- { "color": "...", "year": "...", "mileage": "...", ... }
  date_posted TIMESTAMP,
  scraped_at TIMESTAMP DEFAULT NOW(),
  raw_html TEXT
);
```

**Indexes**:

* `PRIMARY KEY (id)` prevents duplicates.
* If you need queries by price or year, create indexes on `((specs->>'year')::int)` or specific columns after normalization.

---

# 5 — Implementation: code scaffolding (line-by-line guidance)

Below is a detailed scaffolding for files and functions, with pseudo-code / realistic code snippets the agent should implement. The blueprint is explicit so the agent can paste and run with minimal changes.

> All code below is async, Playwright-based, and uses `lxml` for parsing and `asyncpg` for DB.

---

## `src/config.py`

```python
from dotenv import load_dotenv
import os
load_dotenv()

DB = {
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASS"),
    "database": os.getenv("DB_NAME"),
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", 5432))
}
TARGET_URL = os.getenv("TARGET_URL", "https://divar.ir/s/tehran/motorcycles")
USER_AGENT = os.getenv("USER_AGENT", "Mozilla/5.0 ...")
MAX_SCROLLS = int(os.getenv("MAX_SCROLLS", 200))  # safety cap
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 100))
```

---

## `src/db.py`

```python
import asyncpg
from config import DB

async def init_db():
    conn = await asyncpg.connect(**DB)
    await conn.execute("""
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
    """)
    await conn.close()

async def get_conn():
    return await asyncpg.connect(**DB)

async def batch_upsert(conn, rows):
    # rows: list of dicts matching table columns
    # use transaction and executemany style with ON CONFLICT DO NOTHING
    async with conn.transaction():
        stmt = """
        INSERT INTO motorcycles (id, url, title, price, description, location, specs, date_posted, raw_html)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
        ON CONFLICT (id) DO NOTHING
        """
        for r in rows:
            await conn.execute(stmt, r['id'], r['url'], r.get('title'), r.get('price'),
                               r.get('description'), r.get('location'), r.get('specs'),
                               r.get('date_posted'), r.get('raw_html'))
```

---

## `src/scraper.py`

This file runs Playwright, performs scroll/click loop, returns final content or list of ad URLs.

```python
import asyncio
from playwright.async_api import async_playwright, TimeoutError as PWTimeout
from config import TARGET_URL, USER_AGENT, MAX_SCROLLS
import logging

LOAD_MORE_SELECTOR = "button.post-list__load-more-btn-be092"  # defensive selector

async def fetch_final_html():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(user_agent=USER_AGENT, locale="fa-IR")
        page = await context.new_page()
        await page.goto(TARGET_URL, wait_until="load", timeout=60000)

        scroll_count = 0
        while scroll_count < MAX_SCROLLS:
            scroll_count += 1
            # scroll to bottom
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            # small pause to allow lazy loading
            await page.wait_for_timeout(800)  # tweak as necessary
            # try click load-more if present (defensive)
            try:
                btn = await page.wait_for_selector(LOAD_MORE_SELECTOR, timeout=1500)
                if btn:
                    try:
                        await btn.click()
                        # wait for new content to appear (heuristic: wait for network idle or small delay)
                        await page.wait_for_timeout(1200)
                    except Exception as e:
                        logging.warning("Load-more click failed: %s", e)
                        break
            except PWTimeout:
                # no load-more found in this iteration -> treat as finished
                break

        content = await page.content()
        await browser.close()
        return content
```

**Notes**:

* `MAX_SCROLLS` is a safety cap in case site uses infinite loading.
* Use short waits to preserve speed but be conservative enough to let content load.

---

## `src/parser.py`

Use `lxml.html.fromstring` for speed. Parsing strategy: extract ad hrefs first, dedupe by ID, then for each ad either parse from listing blob (if full fields present) or fetch ad page.

```python
from lxml import html
from urllib.parse import urljoin, urlparse
import re
import logging
from datetime import datetime

def extract_ad_hrefs(listing_html, base="https://divar.ir"):
    tree = html.fromstring(listing_html)
    hrefs = tree.xpath("//a[contains(@href, '/v/')]/@href")
    normalized = []
    for h in hrefs:
        if h.startswith("/"):
            normalized.append(urljoin(base, h))
        else:
            normalized.append(h)
    # dedupe while preserving order
    seen = set()
    out = []
    for h in normalized:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out

def id_from_url(url):
    parsed = urlparse(url)
    segs = parsed.path.rstrip("/").split("/")
    if segs:
        return segs[-1]
    return None

def parse_ad_page(html_text, url):
    tree = html.fromstring(html_text)
    # Title
    title = None
    t = tree.xpath("//h1/text()")
    if t:
        title = t[0].strip()
    else:
        t = tree.xpath("//meta[@property='og:title']/@content")
        title = t[0].strip() if t else None

    # Price
    price = None
    p = tree.xpath("//*[contains(text(),'تومان') or contains(text(),'ریال')]/text()")
    if p:
        # pick the first that looks like a price (heuristic)
        for cand in p:
            if re.search(r'\d', cand):
                price = cand.strip()
                break

    # Date & location (heuristic)
    date_posted = None
    loc = None
    time_loc = tree.xpath("//text()[contains(., 'در') and contains(., 'تهران')]/parent::*")
    if time_loc:
        text = ''.join(time_loc[0].itertext()).strip()
        # try to parse time and location with simple heuristics
        # Example: "۱۷ ساعت پیش در تهران، شهرک غرب"
        loc_parts = text.split("در")
        if len(loc_parts) >= 2:
            date_posted = loc_parts[0].strip()
            loc = loc_parts[1].strip()

    # Description
    desc = None
    d = tree.xpath("//h2[contains(., 'توضیحات')]/following-sibling::*[1]//text()")
    if d:
        desc = " ".join([x.strip() for x in d if x.strip()])

    # Specs: attempt to find key-value pairs
    specs = {}
    # common labels to look for (Persian)
    for label in ['رنگ','سال','سال تولید','کارکرد','کیلومتر','مدل']:
        nodes = tree.xpath(f"//*[contains(text(), '{label}')]")
        if nodes:
            for node in nodes[:2]:
                txt = ''.join(node.itertext()).strip()
                specs.setdefault(label, txt)

    # map specs to normalized keys
    normalized = {}
    normalized['color'] = specs.get('رنگ') or None
    normalized['year_made'] = specs.get('سال تولید') or specs.get('سال') or None
    normalized['mileage'] = specs.get('کارکرد') or specs.get('کیلومتر') or None

    return {
        "id": id_from_url(url),
        "url": url,
        "title": title,
        "price": price,
        "description": desc,
        "location": loc,
        "specs": normalized,
        "date_posted": None,  # optional: leave None unless parsed to real timestamp
        "raw_html": html_text
    }
```

**Implementation notes**:

* This parser uses heuristics for Persian labels. It must be extended and refined using real examples (test against several ad pages).
* Convert Persian digits (۰۱۲۳...) to ASCII digits if numeric processing is needed.

---

## `src/run.py` (or main orchestration)

```python
import asyncio
from scraper import fetch_final_html
from parser import extract_ad_hrefs, parse_ad_page
from db import get_conn, batch_upsert, init_db
import logging
import aiohttp  # if fetching individual ad pages
from config import BATCH_SIZE

async def main():
    logging.basicConfig(level=logging.INFO)
    await init_db()
    listing_html = await fetch_final_html()
    ad_urls = extract_ad_hrefs(listing_html)
    logging.info("Found %d ad URLs", len(ad_urls))

    conn = await get_conn()
    batch = []
    async with aiohttp.ClientSession() as sess:
        for i, url in enumerate(ad_urls):
            # For speed, we can try to parse some fields from listing HTML if possible.
            # If we need full ad page, fetch it.
            async with sess.get(url, timeout=30) as resp:
                html_text = await resp.text()
            parsed = parse_ad_page(html_text, url)
            batch.append(parsed)
            if len(batch) >= BATCH_SIZE:
                await batch_upsert(conn, batch)
                batch = []
        if batch:
            await batch_upsert(conn, batch)
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
```

**Speed-focused notes**:

* We call `fetch_final_html()` once (fast). If the listing contains enough data, avoid fetching each ad individually — that is the biggest speed saver. If the listing does not contain full description/specs, fetch ad pages in parallel but limit concurrency (e.g., semaphores for up to 10 concurrent requests).
* Use `aiohttp` for fetching ad pages (if needed) — faster than opening new Playwright tabs.

---

# 6 — Performance & concurrency plan (numbers and percentages)

* **Single `page.content()` approach**: fastest — do all parsing in memory. (Recommended if listing includes fields.) Expect 60–80% speed advantage over fetching N individual pages.
* **Fetching individual ad pages**:

  * Use `aiohttp` + concurrency semaphore (e.g., `max_tasks=8`) to balance speed and politeness.
  * Batch DB inserts in groups of 50–200 for throughput. `asyncpg` can insert tens to hundreds of rows per second depending on DB.
* **Estimated throughput** (rough heuristics):

  * If parsing only the listing HTML: processing 2k ad entries in ~30–120 seconds (parse and DB ops dependent).
  * If fetching each ad page: add ~0.12–0.6s per ad with concurrency; with concurrency 10, ~2k ads could take several minutes.
* **Batch size**: 100 recommended for a balance of memory & performance.

---

# 7 — Error handling & robustness (must-implement)

1. **Timeouts**:

   * Playwright navigation & waits: set sensible timeouts (30–60s). Catch `playwright.TimeoutError`.
2. **Load-more missing**:

   * After N scrolls without finding the button, break and continue parsing.
3. **Partial HTML / parse failures**:

   * Wrap parsing for each ad in try/except; on exception, log ad URL & error and continue.
4. **DB errors**:

   * Use transactions for batch inserts.
   * On conflict, ignore duplicates (`ON CONFLICT DO NOTHING`).
   * On connection failure, attempt a limited reconnect (3 retries with backoff).
5. **Network failures when fetching ad pages**:

   * Retry up to 3 times with exponential backoff.
6. **Rate limiting and 429s**:

   * If site responds with 429 or rate-limit signals, slow down: add delays and reduce concurrency.

---

# 8 — Testing & validation plan

1. **Unit tests**

   * `test_parser.py`: feed saved HTML samples (listing + ad pages) and assert parser extracts expected fields and correct `id_from_url`.
2. **Integration test**

   * `test_scraper_simulation.py`: use a small local HTML fixture to simulate scroll + load-more button behavior and assert `fetch_final_html()` returns combined HTML.
3. **Manual testing**

   * Run the scraper with `MAX_SCROLLS=3` and `BATCH_SIZE=10` for a dry-run. Validate DB entries for correctness.
4. **Edge cases**

   * Ads missing fields should still insert with nulls in optional columns.
   * Ensure Persian numerals are handled (create helper to convert Persian digits to ASCII).

---

# 9 — Observability: logging & metrics

1. **Logging**

   * Use `logging` module; write INFO messages for startup, number of ads found, number inserted, number skipped, and DEBUG for per-ad parsing (optional).
   * Write ERROR logs with tracebacks for unexpected exceptions.
2. **Metrics**

   * Count: `found_urls`, `parsed_success`, `parse_failures`, `inserted_count`, `duplicates_skipped`.
   * Track runtime (`start_time`, `end_time`) and average parse time per ad.
3. **Export logs**

   * For production runs, write logs to a rotating file (`logging.handlers.RotatingFileHandler`) or use a log aggregator.

---

# 10 — Deployment & repeatability

1. **One-off run**: execute `python src/run.py` in the virtualenv.
2. **Repeatable runs**: if you want to run periodically later, deploy to a server and schedule with `cron` or a job scheduler. Keep in mind politeness with repeat scrapes.
3. **Dockerization** (optional)

   * Create `Dockerfile` with Python image, install Playwright, copy code, set environment variables, and run `python -m playwright install` at build time or entrypoint. Note Playwright requires extra dependencies; see Playwright docs.
4. **Secrets**

   * Store DB credentials in environment variables or a secrets manager; never put them in git.

---

# 11 — Detailed testing checklist for the agent (step-by-step)

1. Create virtualenv and install dependencies.
2. Implement `config.py` and `.env`.
3. Implement `db.py` and run `init_db()` to confirm the schema is created.
4. Implement `scraper.py` and run `fetch_final_html()`:

   * Validate it returns HTML that includes multiple ad entries and the load-more process executed.
5. Save returned HTML to file `samples/listing_snapshot.html`.
6. Implement `parser.extract_ad_hrefs()` and assert it returns unique normalized URLs.
7. Pick 5 sample ad URLs and implement `parse_ad_page()`; assert extraction of `title`, `price`, `description`, and `specs`.
8. Implement `run.py`, run end-to-end for the first 50 ads, and check DB for inserted rows.
9. Add unit tests for Persian numeral conversion and spec normalization.
10. Run the full 2k (or fewer) scrape with debug logging off and confirm DB counts match.

---

# 12 — Extra helper utilities (strongly recommended)

* **Persian numeral conversion**:

```python
PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
def persian_to_ascii(s):
    return s.translate(PERSIAN_DIGITS)
```

* **Normalize price string**: remove non-digits except separators; convert Persian digits; store both raw price and normalized integer price if possible.
* **Spec normalization map**:

```python
SPEC_KEY_MAP = {
  "رنگ": "color",
  "سال": "year_made",
  "سال تولید": "year_made",
  "کارکرد": "mileage",
  "کیلومتر": "mileage"
}
```

* **ID validation**: ensure extracted `id` matches expected pattern (e.g., alphanumeric token). Skip malformed ids.

---

# 13 — Example: concrete extraction rules (do exactly this in code)

For each ad URL:

1. `id = id_from_url(url)` — if `id` is None or contains `/` or whitespace, skip and log.
2. `html_text = fetch(url)` — fetch via `aiohttp` with timeout & 3 retries (only if needed).
3. `data = parse_ad_page(html_text, url)`
4. `data['specs']` — run normalization: map Persian keys to `color`, `year_made`, `mileage`.
5. Convert Persian digits to ASCII for price/year/mileage values.
6. If `date_posted` is a relative string like `"۱۷ ساعت پیش"`, store raw string in `date_posted_raw` and leave `date_posted` null, or attempt to resolve to timestamp if required.
7. Add `raw_html` trimmed to a reasonable size (e.g., first 500k chars) to DB.
8. Add to batch for DB insert. When batch full, call `batch_upsert`.

---

# 14 — Logging messages & exit codes (agent should implement)

* On start: `INFO: Starting scraping run TARGET_URL=...`
* After load: `INFO: finished loading page, total_scrolls=X`
* After collecting URLs: `INFO: found N ad URLs`
* Per batch inserted: `INFO: inserted M records (batch)`
* On parse error: `ERROR: parse error for URL ...: traceback`
* On DB error: `ERROR: DB error: traceback, will retry` (and attempt reconnect)
* Exit codes:

  * `0` success,
  * `2` partial failure (some parse errors),
  * `3` fatal (DB down or Playwright fail).

---

# 15 — Final checklist you hand to the agent (copy-paste)

1. Create project structure and virtualenv; install packages.
2. Implement `config.py` and `.env`.
3. Implement `db.py` and run `init_db()`.
4. Implement `scraper.py` using Playwright async; use `button[class*="post-list__load-more-btn"]` to click load-more; scroll to bottom and wait between iterations.
5. Implement `parser.py` using `lxml`. Use `//a[contains(@href,'/v/')]/@href` to collect ad URLs.
6. Implement `id_from_url()` as last path segment extractor.
7. Implement `parse_ad_page()` with heuristics for Title, Price, Description, Location, Date, and Specs. Convert Persian digits and normalize spec keys.
8. Implement `run.py` to orchestrate scraping, parsing, and batch DB insertion with `asyncpg`.
9. Add robust logging, error handling, retry logic, and unit tests.
10. Run a small dry-run (MAX_SCROLLS=3, BATCH_SIZE=10), validate the DB, then run full scrape.
11. Keep code in a git repo but do NOT commit `.env`.
12. If deploying, provide Dockerfile and schedule responsibly (respect robots.txt & Terms).

---

# 16 — Quick reference of selectors & examples (copy-paste for agent)

* Load-more button (listing): `button[class*="post-list__load-more-btn"]` or `button.post-list__load-more-btn-be092`
* Ad hrefs (listing): XPath: `//a[contains(@href, '/v/')]/@href`
* Title (ad page): `//h1/text()` or `//meta[@property='og:title']/@content`
* Price: find nodes containing `'تومان'` or `'ریال'` and parse numeric substring
* Description: `//h2[contains(., 'توضیحات')]/following-sibling::*[1]//text()`
* Specs: search for `'رنگ'`, `'سال'`, `'کارکرد'` labels; fallback to a spec `ul/li` list if present

Evidence of Title/Price/Specs on a sample ad page used to craft selectors: sample ad content examined. ([سایت دیوار][1])

---

# 17 — Troubleshooting guide (common problems & fixes)

* **No load-more button found**: Increase short wait times (e.g., `wait_for_timeout(1500)`), or scroll a bit slower. If still not found, inspect DOM (the class name might change); use defensive CSS `button[class*="load-more"]`.
* **Too few ad hrefs**: Ensure the listing fully loaded; check lazy-loading; increase scroll/wait cycles.
* **Fields missing / inconsistent**: The page sometimes uses different templates; implement fallback selectors and use raw HTML inspection for edge cases.
* **Duplicate IDs**: If same ID appears multiple times, `ON CONFLICT DO NOTHING` will skip duplicates. Investigate duplicates to ensure IDs are correct.
* **Site blocks / CAPTCHA**: If you encounter anti-bot behavior, stop and reassess. Consider rotating proxies and headless fingerprinting only if allowed and ethical.

---

# 18 — Future enhancements (after MVP)

1. Add proxy pool and user-agent rotation (if scale requires this and allowed).
2. Add automatic conversion of Persian (Solar Hijri) date strings to UTC timestamps.
3. Build an incremental scraper that only fetches new ads by checking latest `id`s in DB.
4. Build a simple web UI to view scraped ads, filters, and export to CSV.

---

# 19 — Closing summary (one-paragraph)

Implement an async Playwright scraper that scrolls and clicks the provided load-more button until no more content, grabs the final HTML, extracts `/v/` ad links and their unique IDs (last path token), parses each ad (title, price, description, location, specs including color/year/mileage), normalizes Persian digits and spec keys, and batch-inserts into PostgreSQL with `id` as the primary key to avoid duplicates. Use `lxml` for fast parsing and `asyncpg` for high-performance insertion. Follow the precise file structure, selectors, and error-handling rules above. Example ad content used to create the parser heuristics was inspected from a sample ad page. ([سایت دیوار][1])

---

If you want, I can now:

* produce a **fully implemented runnable repo** (complete `.py` files) that the agent can copy/paste, or
* produce **unit tests** and a small set of saved HTML fixtures for testing the parser.

Which of those do you want next?

[1]: https://divar.ir/v/%D8%A8%D9%86%D9%84%DB%8C-%DB%B1%DB%B5%DB%B0-%D9%86%DB%8C%D9%88%D9%81%D8%B3-%D8%AC%D8%B4%D9%86%D9%88%D8%A7%D8%B1%D9%87-%D9%88%DB%8C%DA%98%D9%87-%D9%81%D8%B1%D9%88%D8%B4-%D9%86%D9%82%D8%AF%DB%8C-%D8%B2%DB%8C%D8%B1-%D9%82%DB%8C%D9%85%D8%AA/Aalrwjwc "بنلی ۱۵۰ نیوفس جشنواره ویژه فروش نقدی زیر قیمت در تهران - ۲۴ آبان ۱۴۰۴"
