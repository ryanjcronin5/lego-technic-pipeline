"""CLI entry point: ``technic-etl`` runs extract -> transform -> load."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from technic.config import get_settings
from technic.db import make_engine
from technic.extract import download_all, read_all
from technic.load import load
from technic.transform import transform

log = logging.getLogger("technic")


def run(
    database_url: str,
    source_dir: Path | None = None,
    force: bool = False,
    focus_theme: str | None = None,
) -> dict[str, int]:
    settings = get_settings()
    start = time.perf_counter()

    if source_dir is None:
        download_all(settings.base_url, settings.raw_dir, settings.max_cache_age_hours, force)
        source_dir, source = settings.raw_dir, settings.base_url
    else:
        source = str(source_dir)

    raw = read_all(source_dir)
    data = transform(raw, focus_theme or settings.focus_theme)
    counts = load(make_engine(database_url), data, source)

    log.info(
        "loaded %s in %.1fs",
        ", ".join(f"{k}={v}" for k, v in counts.items()),
        time.perf_counter() - start,
    )
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Rebrickable -> database pipeline.")
    parser.add_argument(
        "--source", type=Path, help="read CSVs from this folder instead of downloading"
    )
    parser.add_argument("--force", action="store_true", help="ignore the download cache")
    parser.add_argument("--database-url", help="override DATABASE_URL")
    parser.add_argument("--theme", help="override FOCUS_THEME (default: Technic)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        run(
            args.database_url or get_settings().database_url,
            source_dir=args.source,
            force=args.force,
            focus_theme=args.theme,
        )
    except Exception:
        log.exception("pipeline failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
