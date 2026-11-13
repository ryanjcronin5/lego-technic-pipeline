"""Extract: download Rebrickable CSV dumps (with a local cache) and read them."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import httpx
import pandas as pd

log = logging.getLogger(__name__)

# Rebrickable dump name -> columns the pipeline relies on (the "data contract").
# Extra upstream columns are ignored; missing ones fail the run loudly.
REQUIRED_COLUMNS: dict[str, list[str]] = {
    "themes": ["id", "name", "parent_id"],
    "sets": ["set_num", "name", "year", "theme_id", "num_parts", "img_url"],
    "part_categories": ["id", "name"],
    "parts": ["part_num", "name", "part_cat_id"],
    "inventories": ["id", "version", "set_num"],
    "inventory_parts": ["inventory_id", "part_num", "color_id", "quantity", "is_spare"],
}
# Columns kept when present but not required (older dumps lack them).
OPTIONAL_COLUMNS: dict[str, list[str]] = {"parts": ["part_material"]}


class SchemaError(ValueError):
    """Raised when an upstream file no longer matches the expected columns."""


def download_all(base_url: str, raw_dir: Path, max_age_hours: float, force: bool = False) -> None:
    """Download every required dump into ``raw_dir`` unless a fresh copy is cached."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=120, follow_redirects=True) as client:
        for name in REQUIRED_COLUMNS:
            target = raw_dir / f"{name}.csv.gz"
            if not force and _is_fresh(target, max_age_hours):
                log.info("cache hit: %s", target.name)
                continue
            url = base_url.rstrip("/") + f"/{name}.csv.gz"
            log.info("downloading %s", url)
            tmp = target.with_suffix(".part")
            with client.stream("GET", url) as resp:
                resp.raise_for_status()
                with tmp.open("wb") as fh:
                    for chunk in resp.iter_bytes():
                        fh.write(chunk)
            tmp.replace(target)  # atomic: never leave a half-written file behind


def _is_fresh(path: Path, max_age_hours: float) -> bool:
    return path.exists() and (time.time() - path.stat().st_mtime) < max_age_hours * 3600


def read_all(source_dir: Path) -> dict[str, pd.DataFrame]:
    """Read every required dump from ``source_dir`` (``.csv.gz`` or plain ``.csv``)."""
    frames: dict[str, pd.DataFrame] = {}
    for name, required in REQUIRED_COLUMNS.items():
        path = _find(source_dir, name)
        df = pd.read_csv(path, dtype={"set_num": str, "part_num": str}, keep_default_na=True)
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise SchemaError(f"{path.name} is missing expected columns: {missing}")
        optional = [c for c in OPTIONAL_COLUMNS.get(name, []) if c in df.columns]
        frames[name] = df[required + optional]
        log.info("read %s: %d rows", path.name, len(df))
    return frames


def _find(source_dir: Path, name: str) -> Path:
    for candidate in (source_dir / f"{name}.csv.gz", source_dir / f"{name}.csv"):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"no {name}.csv(.gz) in {source_dir}")
