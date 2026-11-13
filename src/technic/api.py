"""FastAPI app: JSON analytics endpoints plus the static dashboard."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import Engine
from sqlalchemy.exc import DBAPIError

from technic import __version__, analytics
from technic.config import get_settings
from technic.db import make_engine

STATIC_DIR = Path(__file__).parent / "static"


class Summary(BaseModel):
    total_sets: int
    technic_sets: int
    first_technic_year: int | None
    latest_technic_year: int | None
    distinct_technic_parts: int
    last_refreshed: datetime | None
    source: str | None


class YearTrend(BaseModel):
    year: int
    technic_sets: int
    technic_avg_parts: float | None
    all_avg_parts: float | None


class SetRow(BaseModel):
    set_num: str
    name: str
    year: int
    num_parts: int
    img_url: str | None = None


class BigSet(SetRow):
    theme: str


class SetDetail(BigSet):
    is_technic: bool
    distinct_parts: int


class SimilarSet(SetRow):
    shared_parts: int
    similarity: float


class PartUsage(BaseModel):
    part_num: str
    name: str | None
    category: str | None
    total_quantity: int
    set_count: int


class SharedPart(BaseModel):
    part_num: str
    name: str | None
    qty_a: int
    qty_b: int


class Comparison(BaseModel):
    a: str
    b: str
    distinct_parts_a: int
    distinct_parts_b: int
    shared_parts: int
    similarity: float
    shared: list[SharedPart]


def create_app(engine: Engine | None = None) -> FastAPI:
    engine = engine or make_engine(get_settings().database_url)
    app = FastAPI(
        title="Technic Insights API",
        version=__version__,
        description="Analytics over the Rebrickable LEGO catalogue, focused on Technic.",
    )

    @app.exception_handler(DBAPIError)
    async def db_unavailable(_: Request, exc: DBAPIError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={"detail": "Database not ready. Run `technic-etl` to load data first."},
        )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/api/summary", response_model=Summary)
    def summary():
        return analytics.summary(engine)

    @app.get("/api/trends", response_model=list[YearTrend])
    def trends():
        return analytics.yearly_trends(engine)

    @app.get("/api/sets/biggest", response_model=list[BigSet])
    def biggest(limit: int = Query(10, ge=1, le=100)):
        return analytics.biggest_sets(engine, limit)

    @app.get("/api/sets/search", response_model=list[SetRow])
    def search(q: str = Query(..., min_length=2), limit: int = Query(20, ge=1, le=100)):
        return analytics.search_sets(engine, q, limit)

    @app.get("/api/sets/{set_num}", response_model=SetDetail)
    def set_detail(set_num: str):
        row = analytics.get_set(engine, set_num)
        if row is None:
            raise HTTPException(404, f"set {set_num} not found")
        return row

    @app.get("/api/sets/{set_num}/similar", response_model=list[SimilarSet])
    def similar(set_num: str, limit: int = Query(10, ge=1, le=50)):
        if analytics.get_set(engine, set_num) is None:
            raise HTTPException(404, f"set {set_num} not found")
        return analytics.similar_sets(engine, set_num, limit)

    @app.get("/api/compare", response_model=Comparison)
    def compare(a: str, b: str):
        for s in (a, b):
            if analytics.get_set(engine, s) is None:
                raise HTTPException(404, f"set {s} not found")
        return analytics.compare_sets(engine, a, b)

    @app.get("/api/parts/top", response_model=list[PartUsage])
    def parts_top(limit: int = Query(15, ge=1, le=100)):
        return analytics.top_parts(engine, limit)

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app


app = create_app()
