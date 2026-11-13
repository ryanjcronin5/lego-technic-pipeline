from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import Engine

from technic.db import make_engine, metadata
from technic.extract import read_all
from technic.load import load
from technic.transform import transform

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def raw():
    return read_all(FIXTURES)


@pytest.fixture
def engine(tmp_path) -> Engine:
    """SQLite by default; set TEST_DATABASE_URL to run the same tests on Postgres."""
    url = os.getenv("TEST_DATABASE_URL") or f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    eng = make_engine(url)
    metadata.drop_all(eng)
    yield eng
    metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def loaded(engine, raw) -> Engine:
    load(engine, transform(raw), source="fixtures")
    return engine
