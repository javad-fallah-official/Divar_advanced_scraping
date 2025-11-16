## Project Overview
- Build an async scraper for `https://divar.ir/s/tehran/motorcycles` that collects `title, price, description, location, specs (color, year made, mileage), date`, stores records in PostgreSQL, and avoids duplicates using the ad token after `/v/` as `id`.
- Use Playwright (headless Chromium) for the listing load-more/scroll, parse HTML with `lxml`, and insert with `asyncpg`.

## Objectives
- Extract ≤ 2k ads reliably with robust selectors and fallbacks.
- Normalize Persian digits and spec keys and persist raw HTML for audit.
- Achieve fast runs (minutes), resilient error handling, and clean logs.

## Tech Stack
- Python `3.11` on Windows.
- Libraries: `playwright`, `lxml`, `asyncpg`, `aiohttp`, `python-dotenv`, `aiofiles`.
- Database: PostgreSQL 12+.

## Repository Layout
- `src/config.py` — env loading and config constants.
- `src/db.py` — schema init, connection, batch upsert.
- `src/scraper.py` — Playwright load-more/scroll and final HTML.
- `src/parser.py` — link extraction, ad-page parsing, normalization.
- `src/utils.py` — helpers for Persian digits, price/spec normalization.
- `src/run.py` — orchestration, batching, concurrency control.
- `tests/` — unit and integration tests with fixtures.

## Environment Setup (Windows)
- Create venv: `python -m venv .venv`
- Activate: `.venv\Scripts\activate`
- Install deps: `pip install playwright lxml asyncpg python-dotenv aiofiles aiohttp pytest`
- Install browsers: `python -m playwright install chromium`
- `.env` keys: `DB_USER, DB_PASS, DB_NAME, DB_HOST, DB_PORT, TARGET_URL, USER_AGENT, MAX_SCROLLS, BATCH_SIZE`.

## Data Model
- Table `motorcycles` with `id TEXT PRIMARY KEY, url, title, price, description, location, specs JSONB, date_posted TIMESTAMP NULL, scraped_at TIMESTAMP DEFAULT NOW(), raw_html TEXT`.
- Indexes: primary key on `id`; optional functional indexes later for analytics.

## Scraping Strategy
- Open listing page with Playwright, set `locale="fa-IR"` and custom `user_agent`.
- Loop: scroll to bottom, short wait, click `button[class*="post-list__load-more-btn"]` when present, stop when absent or cap with `MAX_SCROLLS`.
- Capture final HTML via `page.content()` once.

## Parsing Strategy
- Extract ad links via XPath `//a[contains(@href,'/v/')]/@href`, normalize relative paths.
- Derive `id` from last path segment of each ad URL.
- For each ad URL, fetch the ad page HTML with `aiohttp` (if listing HTML lacks required fields) and parse:
  - Title: `//h1/text()` fallback `//meta[@property='og:title']/@content`.
  - Price: nodes containing `تومان` or `ریال`; normalize digits and keep raw string.
  - Description: `//h2[contains(.,'توضیحات')]/following-sibling::*[1]//text()`.
  - Location and posted line: heuristics splitting the line containing `در` and city tokens; fallback `//time/@datetime`.
  - Specs: search labels `رنگ, سال تولید, کارکرد, کیلومتر` and map to `color, year_made, mileage`.
- Convert Persian numerals to ASCII for numeric fields.

## Concurrency & Rate Limiting
- Limit ad-page fetches using `asyncio.Semaphore(max=8)`.
- Short randomized delays on retries and between batches.
- Batch DB inserts with `BATCH_SIZE` (e.g., 100).

## Error Handling
- Catch Playwright timeouts and proceed with best-effort content.
- Wrap per-ad parsing in try/except; record failures and keep going.
- DB operations in transactions; `ON CONFLICT (id) DO NOTHING` for duplicates; reconnect with backoff on connection errors.
- Network fetch retries: up to 3 attempts with exponential backoff; slow down on `429`.

## Configuration & Secrets
- Read from `.env` via `python-dotenv`; never commit `.env`.
- Allow overriding `MAX_SCROLLS` and `BATCH_SIZE` for dry-runs.

## Development Workflow
- Implement modules in order: `config.py` → `db.py` → `scraper.py` → `parser.py` → `run.py`.
- Create HTML fixtures from manual runs to stabilize parser.
- Add unit tests for link extraction, id parsing, Persian digit conversion, and spec normalization.

## Implementation Phases
- Phase 1: Setup and DB
  - Initialize venv, install dependencies, implement `config.py` and `.env`.
  - Implement `db.py` and `init_db()`; verify schema.
- Phase 2: Scraper
  - Implement scroll + load-more loop in `scraper.py`; save one snapshot for fixture.
- Phase 3: Parser
  - Implement link extraction and `id_from_url`.
  - Implement `parse_ad_page` with selector fallbacks and normalization.
- Phase 4: Orchestration & Batching
  - Implement `run.py` to fetch ad pages with controlled concurrency and call `batch_upsert`.
- Phase 5: Testing & Hardening
  - Add unit tests and an integration test; refine selectors with fixtures.
- Phase 6: Performance & Observability
  - Tune waits and concurrency; add structured logging and counters.

## Testing
- Unit: parser selectors, id extraction, Persian numeral conversion, spec mapping.
- Integration: run `fetch_final_html()` with small `MAX_SCROLLS`, parse 10–20 ads, and assert DB insert counts.
- Fixtures: store `listing_snapshot.html` and 3–5 ad page HTML samples under `tests/fixtures/`.

## Logging & Metrics
- INFO logs for start, total scrolls, URLs found, batch inserts.
- ERROR logs for parse and DB failures.
- Counters: `found_urls, parsed_success, parse_failures, inserted_count, duplicates_skipped, runtime`.

## Performance Targets
- Listing-only parse: complete ≤ 2 minutes for ~2k ads.
- Ad-page fetch: ≤ 6–8 minutes with concurrency 8 and polite delays.

## Security & Compliance
- Respect Terms and `robots.txt`; one-off personal use only.
- No secrets in repo; use environment variables.

## Deployment
- One-off run: `python src/run.py`.
- Optional: Docker image with Playwright dependencies and scheduled run; ensure legal compliance and politeness.

## Deliverables
- Working Python modules in `src/` and tests in `tests/`.
- Configurable `.env` with parameters.
- PostgreSQL table with populated records and counts.
- Logs summarizing run outcomes.

## Risks & Mitigations
- DOM changes: use defensive selectors and maintain fixtures to update parser.
- Anti-bot triggers: minimize fingerprinting, moderate concurrency, keep headless realistic.
- Inconsistent fields: robust fallbacks and allow nulls.

## Acceptance Criteria
- Successfully scrapes and inserts ≥ 95% of accessible listing ads without crashing.
- Duplicates skipped via `id` primary key.
- Unit and integration tests pass.
- Logs show counts and runtime with parse failures ≤ 5%.
