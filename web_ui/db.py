import os
from typing import Any, Dict, List, Optional
import psycopg2
import psycopg2.extras


def _rows_to_dicts(cur, rows) -> List[Dict[str, Any]]:
    cols = [d[0] for d in cur.description]
    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append({cols[i]: r[i] for i in range(len(cols))})
    return out


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
    host = os.environ.get("DB_HOST", "localhost")
    port = int(os.environ.get("DB_PORT", "5432"))
    user = os.environ.get("DB_USER", "postgres")
    password = os.environ.get("DB_PASSWORD", "admin")
    name = os.environ.get("DB_NAME", "Divar")
    conn = psycopg2.connect(host=host, port=port, user=user, password=password, dbname=name)
    where, params = _build_where_and_params(filters)
    sql = f"SELECT * FROM posts{where} ORDER BY scraped_at DESC LIMIT %s"
    params2 = params + [limit]
    with conn.cursor() as cur:
        cur.execute(sql, params2)
        rows = cur.fetchall()
        out = _rows_to_dicts(cur, rows)
    conn.close()
    return out


