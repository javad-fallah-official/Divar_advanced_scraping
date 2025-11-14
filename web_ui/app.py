from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import List, Dict, Any

from .db import query_posts_single

app = FastAPI(title="Divar Posts UI")
app.mount("/static", StaticFiles(directory="web_ui/static"), name="static")
templates = Jinja2Templates(directory="web_ui/templates")


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/posts")
def list_posts(
    request: Request,
    source: str = "playwright",  # playwright | lib | both
    city: str | None = None,
    district: str | None = None,
    brand: str | None = None,
    search: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    min_year: int | None = None,
    max_year: int | None = None,
    min_mileage: int | None = None,
    max_mileage: int | None = None,
    negotiable: str | None = None,  # nonneg | unknown | any
):
    filters: Dict[str, Any] = {
        "city": city,
        "district": district,
        "brand": brand,
        "search": search,
        "min_price": min_price,
        "max_price": max_price,
        "min_year": min_year,
        "max_year": max_year,
        "min_mileage": min_mileage,
        "max_mileage": max_mileage,
        "negotiable": negotiable if negotiable in {"nonneg", "unknown"} else None,
    }

    sources: List[str] = []
    if source == "both":
        sources = ["playwright", "lib"]
    elif source == "lib":
        sources = ["lib"]
    else:
        sources = ["playwright"]

    items: List[Dict[str, Any]] = []
    for s in sources:
        db_path = "data/divar.db" if s == "playwright" else "data/divar_lib.db"
        try:
            rows = query_posts_single(db_path, filters, limit=100000)
            for r in rows:
                r["source"] = s
            items.extend(rows)
        except Exception:
            # If DB missing, just continue
            pass

    # Sort combined by scraped_at desc
    def sort_key(x):
        return x.get("scraped_at") or ""

    items.sort(key=sort_key, reverse=True)

    total = len(items)

    return JSONResponse({
        "items": items,
        "total": total,
    })

