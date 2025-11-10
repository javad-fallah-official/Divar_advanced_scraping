# Divar Advanced Scraping (Tehran Motorcycles > Honda)

This project scrapes listings from Divar for Tehran city, focusing on `motorcycles` → `honda` and filtering out negotiable ads (`non-negotiable=true`). It extracts structured data from each product page and saves it into a local SQLite database.

Important: Please review Divar's Terms of Service and robots.txt. Use sensible rate limiting and avoid excessive requests.

## Features
- Collects listing URLs from `https://divar.ir/s/tehran/motorcycles/honda?non-negotiable=true`
- Parses product details: title, price (toman), usage (km), model year (Jalali), color, brand, location, description
- Saves to SQLite with upsert (deduplicates by `url`)
- Simple CLI with progress and basic resilience

## Setup
1. Create a virtual environment (recommended):
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```

3. Install Playwright browser binaries (first run only):
   ```powershell
   python -m playwright install chromium
   ```

## Usage
Run the scraper with default focus on Honda motorcycles (non-negotiable) in Tehran:
```powershell
python src\main.py --city tehran --category motorcycles --brand honda --non-negotiable true --max-items 200
```

Arguments:
- `--city` default `tehran`
- `--category` default `motorcycles`
- `--brand` default `honda` (omit to scrape all brands in the category)
- `--non-negotiable` `true|false` default `true`
- `--max-items` integer limit for listing URLs to collect (default 200)
- `--headless` `true|false` default `true`

Output DB file: `data/divar.db`

## Notes
- Divar is a dynamic PWA. The scraper uses Playwright to render and scroll the listing page and then navigates product pages to extract data. It attempts multiple strategies (JSON/script tags and text parsing) to be resilient.
- Persian digits and punctuation are normalized before parsing numbers.
- Model year is saved as Jalali integer (e.g., `1398`).

## Next Steps
- Add concurrency for detail page scraping
- Use Divar's internal JSON endpoints if stable and accessible
- Expand schema (images, seller, token, etc.)

## Comparison Project (Divar library)
A separate project using the unofficial `divar` PyPI library is available under `divar_lib_client/`. It uses the library’s sync client to fetch category posts and post details, then maps them to the same SQLite schema for side-by-side comparison.

Setup:
- `python -m venv .venv && .\\.venv\\Scripts\\Activate.ps1`
- `pip install -r divar_lib_client\\requirements.txt`
- Run: `python divar_lib_client\\src\\main.py --city tehran --category motorcycles --brand honda --non-negotiable true --max-items 200`

Notes:
- The `divar` library is third-party and unofficial; APIs may change and some features require authentication.
- Output DB: `data/divar_lib.db`. Compare with `data/divar.db` from the Playwright scraper.

## Optional Libraries
There is an unofficial Divar client library on PyPI that may use internal endpoints and provide structured access. Evaluate feasibility and compliance before using in production.
