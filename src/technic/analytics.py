"""Analytics queries. Plain, portable SQL so the same code runs on SQLite and Postgres."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine, text


def _rows(engine: Engine, sql: str, **params: Any) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        return [dict(r._mapping) for r in conn.execute(text(sql), params)]


def _as_utc(value: datetime | str) -> datetime:
    """SQLite drops tz info and returns strings; runs are always recorded in UTC."""
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def summary(engine: Engine) -> dict[str, Any]:
    stats = _rows(
        engine,
        """
        SELECT COUNT(*) AS total_sets,
               COALESCE(SUM(CASE WHEN is_technic THEN 1 ELSE 0 END), 0) AS technic_sets,
               MIN(CASE WHEN is_technic THEN year END) AS first_technic_year,
               MAX(CASE WHEN is_technic THEN year END) AS latest_technic_year
        FROM sets
        """,
    )[0]
    stats["distinct_technic_parts"] = _rows(
        engine, "SELECT COUNT(DISTINCT part_num) AS n FROM inventory_parts"
    )[0]["n"]
    last = _rows(
        engine,
        "SELECT finished_at, source FROM pipeline_runs ORDER BY id DESC LIMIT 1",
    )
    stats["last_refreshed"] = _as_utc(last[0]["finished_at"]) if last else None
    stats["source"] = last[0]["source"] if last else None
    return stats


def yearly_trends(engine: Engine) -> list[dict[str, Any]]:
    """Per year: Technic set count and average part count, vs the whole catalogue."""
    rows = _rows(
        engine,
        """
        SELECT year,
               SUM(CASE WHEN is_technic THEN 1 ELSE 0 END) AS technic_sets,
               AVG(CASE WHEN is_technic THEN num_parts END) AS technic_avg_parts,
               AVG(num_parts) AS all_avg_parts
        FROM sets
        WHERE num_parts > 0
        GROUP BY year
        ORDER BY year
        """,
    )
    for r in rows:
        for key in ("technic_avg_parts", "all_avg_parts"):
            r[key] = round(float(r[key]), 1) if r[key] is not None else None
    return rows


def biggest_sets(engine: Engine, limit: int = 10) -> list[dict[str, Any]]:
    return _rows(
        engine,
        """
        SELECT s.set_num, s.name, s.year, s.num_parts, s.img_url, t.name AS theme
        FROM sets s JOIN themes t ON t.id = s.theme_id
        WHERE s.is_technic
        ORDER BY s.num_parts DESC, s.set_num
        LIMIT :limit
        """,
        limit=limit,
    )


def search_sets(engine: Engine, q: str, limit: int = 20) -> list[dict[str, Any]]:
    return _rows(
        engine,
        """
        SELECT set_num, name, year, num_parts, img_url
        FROM sets
        WHERE is_technic AND (LOWER(name) LIKE :q OR LOWER(set_num) LIKE :q)
        ORDER BY year DESC, set_num
        LIMIT :limit
        """,
        q=f"%{q.lower()}%",
        limit=limit,
    )


def get_set(engine: Engine, set_num: str) -> dict[str, Any] | None:
    rows = _rows(
        engine,
        """
        SELECT s.set_num, s.name, s.year, s.num_parts, s.img_url, s.is_technic,
               t.name AS theme,
               (SELECT COUNT(DISTINCT part_num) FROM inventory_parts ip
                WHERE ip.set_num = s.set_num) AS distinct_parts
        FROM sets s JOIN themes t ON t.id = s.theme_id
        WHERE s.set_num = :set_num
        """,
        set_num=set_num,
    )
    if not rows:
        return None
    row = rows[0]
    row["is_technic"] = bool(row["is_technic"])
    return row


def top_parts(engine: Engine, limit: int = 15) -> list[dict[str, Any]]:
    """Parts used most across Technic sets (spares excluded)."""
    return _rows(
        engine,
        """
        SELECT ip.part_num, p.name, pc.name AS category,
               SUM(ip.quantity) AS total_quantity,
               COUNT(DISTINCT ip.set_num) AS set_count
        FROM inventory_parts ip
        LEFT JOIN parts p ON p.part_num = ip.part_num
        LEFT JOIN part_categories pc ON pc.id = p.part_cat_id
        GROUP BY ip.part_num, p.name, pc.name
        ORDER BY total_quantity DESC, ip.part_num
        LIMIT :limit
        """,
        limit=limit,
    )


_SET_SIZES = """
    sizes AS (
        SELECT set_num, COUNT(DISTINCT part_num) AS n
        FROM inventory_parts GROUP BY set_num
    )
"""


def similar_sets(engine: Engine, set_num: str, limit: int = 10) -> list[dict[str, Any]]:
    """Sets ranked by Jaccard similarity of their distinct part numbers (colour ignored)."""
    rows = _rows(
        engine,
        f"""
        WITH target AS (
            SELECT DISTINCT part_num FROM inventory_parts WHERE set_num = :set_num
        ),
        shared AS (
            SELECT ip.set_num, COUNT(DISTINCT ip.part_num) AS shared_parts
            FROM inventory_parts ip JOIN target t ON t.part_num = ip.part_num
            WHERE ip.set_num <> :set_num
            GROUP BY ip.set_num
        ),
        {_SET_SIZES}
        SELECT s.set_num, s.name, s.year, s.num_parts, s.img_url, sh.shared_parts,
               1.0 * sh.shared_parts
                   / ((SELECT COUNT(*) FROM target) + sz.n - sh.shared_parts) AS similarity
        FROM shared sh
        JOIN sizes sz ON sz.set_num = sh.set_num
        JOIN sets s ON s.set_num = sh.set_num
        ORDER BY similarity DESC, sh.shared_parts DESC, s.set_num
        LIMIT :limit
        """,
        set_num=set_num,
        limit=limit,
    )
    for r in rows:
        r["similarity"] = round(float(r["similarity"]), 3)
    return rows


def compare_sets(engine: Engine, a: str, b: str, limit: int = 50) -> dict[str, Any]:
    """Overlap between two sets: Jaccard score and the shared parts."""
    sizes = {
        r["set_num"]: r["n"]
        for r in _rows(
            engine,
            """
            SELECT set_num, COUNT(DISTINCT part_num) AS n FROM inventory_parts
            WHERE set_num IN (:a, :b) GROUP BY set_num
            """,
            a=a,
            b=b,
        )
    }
    shared = _rows(
        engine,
        """
        SELECT x.part_num, p.name, x.qty AS qty_a, y.qty AS qty_b
        FROM (SELECT part_num, SUM(quantity) AS qty FROM inventory_parts
              WHERE set_num = :a GROUP BY part_num) x
        JOIN (SELECT part_num, SUM(quantity) AS qty FROM inventory_parts
              WHERE set_num = :b GROUP BY part_num) y ON y.part_num = x.part_num
        LEFT JOIN parts p ON p.part_num = x.part_num
        ORDER BY (x.qty + y.qty) DESC, x.part_num
        """,
        a=a,
        b=b,
    )
    n_a, n_b, n_shared = sizes.get(a, 0), sizes.get(b, 0), len(shared)
    union = n_a + n_b - n_shared
    return {
        "a": a,
        "b": b,
        "distinct_parts_a": n_a,
        "distinct_parts_b": n_b,
        "shared_parts": n_shared,
        "similarity": round(n_shared / union, 3) if union else 0.0,
        "shared": shared[:limit],
    }
