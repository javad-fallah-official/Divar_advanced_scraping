# Divar Library Comparison Project

This subproject uses the unofficial `divar` PyPI library to fetch category posts and post details, then writes them into the same SQLite schema as the Playwright scraper for comparison.

Important: This is a third-party library; methods and endpoints may change. Some methods (e.g., getting a seller’s number) require authentication.

## Setup
1. Create and activate a virtual environment (optional):
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
2. Install dependencies:
   ```powershell
   pip install -r divar_lib_client\requirements.txt
   ```

## Run
```powershell
python divar_lib_client\src\main.py --city tehran --category motorcycles --brand honda --non-negotiable true --max-items 200
```

Arguments:
- `--city` default `tehran`
- `--category` default `motorcycles`
- `--brand` default `honda` (brand filter is heuristic via title/attributes)
- `--non-negotiable` `true|false` default `true` (filters posts marked or parsed as negotiable)
- `--max-items` integer limit for posts to process (default 200)

## Output
- SQLite DB at `data/divar_lib.db` using the same schema as the Playwright project.
- Compare records between `data/divar_lib.db` and `data/divar.db`.

## Library Reference
- PyPI: https://pypi.org/project/divar/

