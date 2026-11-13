"""Runtime configuration, read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///data/technic.db")
    )
    raw_dir: Path = field(default_factory=lambda: Path(os.getenv("RAW_DIR", "data/raw")))
    base_url: str = field(
        default_factory=lambda: os.getenv(
            "REBRICKABLE_BASE_URL", "https://cdn.rebrickable.com/media/downloads/"
        )
    )
    focus_theme: str = field(default_factory=lambda: os.getenv("FOCUS_THEME", "Technic"))
    # Re-download a cached file once it is older than this many hours.
    max_cache_age_hours: float = field(
        default_factory=lambda: float(os.getenv("MAX_CACHE_AGE_HOURS", "20"))
    )


def get_settings() -> Settings:
    return Settings()
