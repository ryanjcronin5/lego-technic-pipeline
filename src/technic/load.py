"""Load: replace the data tables atomically and record the run."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Engine, insert

from technic.db import DATA_TABLES, init_schema, pipeline_runs
from technic.transform import Transformed


def load(engine: Engine, data: Transformed, source: str) -> dict[str, int]:
    """Swap in the new data inside one transaction so readers never see a half-load."""
    init_schema(engine)
    frames = data.as_tables()
    counts: dict[str, int] = {}
    with engine.begin() as conn:
        for table in reversed(DATA_TABLES):
            conn.execute(table.delete())
        for table in DATA_TABLES:
            df = frames[table.name]
            df.to_sql(
                table.name, conn, if_exists="append", index=False, chunksize=1000, method="multi"
            )
            counts[table.name] = len(df)
        conn.execute(
            insert(pipeline_runs).values(
                finished_at=datetime.now(UTC),
                source=source,
                sets_loaded=counts["sets"],
                technic_sets=int(data.sets["is_technic"].sum()),
                inventory_rows=counts["inventory_parts"],
            )
        )
    return counts
