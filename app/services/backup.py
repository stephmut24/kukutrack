"""Create a consistent SQLite backup without interrupting the app."""

import os
import sqlite3
import tempfile
from pathlib import Path

from app.db import get_connection


def create_database_backup() -> Path:
    """Copy the live database through SQLite's backup API into a temporary file."""
    descriptor, temporary_name = tempfile.mkstemp(prefix="kukutrack-backup-", suffix=".db")
    os.close(descriptor)
    backup_path = Path(temporary_name)
    try:
        with get_connection() as source, sqlite3.connect(backup_path) as destination:
            source.backup(destination)
    except (OSError, sqlite3.Error):
        backup_path.unlink(missing_ok=True)
        raise
    return backup_path
