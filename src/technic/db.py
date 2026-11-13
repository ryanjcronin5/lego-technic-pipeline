"""Database schema and engine helpers (works with SQLite and Postgres)."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Engine,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
)

metadata = MetaData()

themes = Table(
    "themes",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=False),
    Column("name", Text, nullable=False),
    Column("parent_id", Integer, nullable=True),
)

sets = Table(
    "sets",
    metadata,
    Column("set_num", String(32), primary_key=True),
    Column("name", Text, nullable=False),
    Column("year", Integer, nullable=False),
    Column("theme_id", Integer, nullable=False, index=True),
    Column("num_parts", Integer, nullable=False),
    Column("img_url", Text, nullable=True),
    Column("is_technic", Boolean, nullable=False, index=True),
)

part_categories = Table(
    "part_categories",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=False),
    Column("name", Text, nullable=False),
)

parts = Table(
    "parts",
    metadata,
    Column("part_num", String(64), primary_key=True),
    Column("name", Text, nullable=False),
    Column("part_cat_id", Integer, nullable=True),
    Column("part_material", Text, nullable=True),
)

inventory_parts = Table(
    "inventory_parts",
    metadata,
    Column("set_num", String(32), primary_key=True),
    Column("part_num", String(64), primary_key=True),
    Column("color_id", Integer, primary_key=True, autoincrement=False),
    Column("quantity", Integer, nullable=False),
    Index("ix_inventory_parts_part_num", "part_num"),
)

pipeline_runs = Table(
    "pipeline_runs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("finished_at", DateTime(timezone=True), nullable=False),
    Column("source", Text, nullable=False),
    Column("sets_loaded", Integer, nullable=False),
    Column("technic_sets", Integer, nullable=False),
    Column("inventory_rows", Integer, nullable=False),
)

# Tables fully replaced on every run, in load order.
DATA_TABLES = [themes, sets, part_categories, parts, inventory_parts]


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite:///"):
        db_path = Path(url.removeprefix("sqlite:///"))
        if str(db_path) != ":memory:":
            db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(url, future=True)


def init_schema(engine: Engine) -> None:
    metadata.create_all(engine)
