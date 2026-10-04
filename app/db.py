"""SQLite connection and schema setup helpers."""

import sqlite3
from pathlib import Path

from app.config import get_db_path

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    start_date TEXT NOT NULL,
    initial_count INTEGER NOT NULL CHECK (initial_count > 0),
    target_weight_g INTEGER NOT NULL DEFAULT 3000 CHECK (target_weight_g > 0),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'closed')),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL,
    log_date TEXT NOT NULL,
    dead_count INTEGER NOT NULL DEFAULT 0 CHECK (dead_count >= 0),
    feed_kg REAL NOT NULL DEFAULT 0 CHECK (feed_kg >= 0),
    water_note TEXT,
    note TEXT,
    FOREIGN KEY (batch_id) REFERENCES batches(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS weigh_ins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL,
    weigh_date TEXT NOT NULL,
    sample_size INTEGER NOT NULL CHECK (sample_size > 0),
    average_weight_g REAL NOT NULL CHECK (average_weight_g > 0),
    FOREIGN KEY (batch_id) REFERENCES batches(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL,
    due_date TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN (
        'heating', 'vaccine', 'vitamin', 'protein', 'booster', 'other'
    )),
    title TEXT NOT NULL,
    details TEXT,
    done INTEGER NOT NULL DEFAULT 0 CHECK (done IN (0, 1)),
    done_at TEXT,
    FOREIGN KEY (batch_id) REFERENCES batches(id) ON DELETE CASCADE
);
"""


def get_connection(path: Path | None = None) -> sqlite3.Connection:
    """Open a SQLite connection configured to return named rows."""
    database_path = path or get_db_path()
    connection = sqlite3.connect(database_path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(path: Path | None = None) -> None:
    """Create the database directory and tables when they do not yet exist."""
    database_path = path or get_db_path()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with get_connection(database_path) as connection:
        connection.executescript(SCHEMA)
