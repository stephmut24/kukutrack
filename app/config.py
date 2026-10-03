"""Application paths and environment-based settings."""

import os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_DIR / "data" / "kukutrack.db"
DEFAULT_SCHEDULE_PATH = PROJECT_DIR / "config" / "default_schedule.json"


def get_db_path() -> Path:
    """Return the configured SQLite database path."""
    configured_path = os.environ.get("KUKUTRACK_DB")
    return Path(configured_path) if configured_path else DEFAULT_DB_PATH
