"""Application paths and environment-based settings."""

import os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_DIR / "data" / "kukutrack.db"
DEFAULT_SCHEDULE_PATH = PROJECT_DIR / "config" / "default_schedule.json"
ALERT_THRESHOLDS_PATH = PROJECT_DIR / "config" / "alert_thresholds.json"
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "SET_MODEL_NAME_FROM_OLLAMA_LIST")
OLLAMA_TIMEOUT_S = float(os.environ.get("OLLAMA_TIMEOUT_S", "30"))
OLLAMA_MAX_FEED_KG = float(os.environ.get("OLLAMA_MAX_FEED_KG", "100"))
OLLAMA_MAX_DEAD_COUNT = int(os.environ.get("OLLAMA_MAX_DEAD_COUNT", "100000"))
OLLAMA_MAX_SAMPLE_SIZE = int(os.environ.get("OLLAMA_MAX_SAMPLE_SIZE", "100000"))
OLLAMA_MAX_AVERAGE_WEIGHT_G = float(os.environ.get("OLLAMA_MAX_AVERAGE_WEIGHT_G", "100000"))


def get_db_path() -> Path:
    """Return the configured SQLite database path."""
    configured_path = os.environ.get("KUKUTRACK_DB")
    return Path(configured_path) if configured_path else DEFAULT_DB_PATH
