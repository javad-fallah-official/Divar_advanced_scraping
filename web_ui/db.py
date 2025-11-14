import sqlite3
from typing import Any, Dict, List, Optional


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def _build_where_and_params(filters: Dict[str, Any]) -> tuple[str, List[Any]]:
    clauses = []
    params: List[Any] = []

    if filters.get("city"):
        clauses.append("city LIKE ?")
        params.append(f"%{filters['city']}%")

    if filters.get("district"):
        clauses.append("district LIKE ?")
        params.append(f"%{filters['district']}%")

    if filters.get("brand"):
        clauses.append("brand LIKE ?")
        params.append(f"%{filters['brand']}%")

    if filters.get("search"):
        clauses.append("(title LIKE ? OR description LIKE ?)")
        params.extend([f"%{filters['search']}%", f"%{filters['search']}%"])

    # Price range
    if filters.get("min_price") is not None:
        clauses.append("price_toman >= ?")
        params.append(filters["min_price"])
    if filters.get("max_price") is not None:
        clauses.append("price_toman <= ?")
        params.append(filters["max_price"])

    # Year range
    if filters.get("min_year") is not None:
        clauses.append("model_year_jalali >= ?")
        params.append(filters["min_year"])
    if filters.get("max_year") is not None:
        clauses.append("model_year_jalali <= ?")
        params.append(filters["max_year"])

    # Mileage range
    if filters.get("min_mileage") is not None:
        clauses.append("mileage_km >= ?")
        params.append(filters["min_mileage"])
    if filters.get("max_mileage") is not None:
        clauses.append("mileage_km <= ?")
        params.append(filters["max_mileage"])

    # Negotiable filter (our DB saves 0 for non-negotiable; null otherwise)
    nego = filters.get("negotiable")
    if nego == "nonneg":
        clauses.append("negotiable = 0")
    elif nego == "unknown":
        clauses.append("negotiable IS NULL")

    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    return where, params


def query_posts_single(db_path: str, filters: Dict[str, Any], limit: int = 1000) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    where, params = _build_where_and_params(filters)
    sql = f"SELECT * FROM posts{where} ORDER BY scraped_at DESC LIMIT ?"  # cap to avoid huge memory
    params2 = params + [limit]
    rows = conn.execute(sql, params2).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


