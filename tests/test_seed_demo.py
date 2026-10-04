import sqlite3
from datetime import timedelta
from pathlib import Path

import pytest

from app.db import get_connection, initialize_database
from app.schemas import BatchCreate
from app.services.batches import create_batch
from app.services.logs import current_utc_date
from scripts.seed_demo import DEMO_BATCH_NAME, DemoBatchExistsError, seed_demo


def _count(connection: sqlite3.Connection, table: str, batch_id: int) -> int:
    """Count records belonging to one batch in a known schema table."""
    row = connection.execute(f"SELECT COUNT(*) AS total FROM {table} WHERE batch_id = ?", (batch_id,)).fetchone()
    return int(row["total"])


def test_seed_demo_creates_deterministic_data(tmp_path: Path) -> None:
    database_path = tmp_path / "demo.db"
    batch_id = seed_demo(database_path)
    today = current_utc_date()

    with get_connection(database_path) as connection:
        batch = connection.execute("SELECT * FROM batches WHERE id = ?", (batch_id,)).fetchone()
        total_dead = connection.execute(
            "SELECT COALESCE(SUM(dead_count), 0) AS total FROM daily_logs WHERE batch_id = ?",
            (batch_id,),
        ).fetchone()
        overdue = connection.execute(
            """
            SELECT COUNT(*) AS total FROM reminders
            WHERE batch_id = ? AND due_date < ? AND done = 0
            """,
            (batch_id, today.isoformat()),
        ).fetchone()

        assert batch["name"] == DEMO_BATCH_NAME
        assert batch["initial_count"] == 100
        assert _count(connection, "daily_logs", batch_id) == 45
        assert _count(connection, "weigh_ins", batch_id) == 7
        assert _count(connection, "reminders", batch_id) == 41
        assert 15 <= total_dead["total"] <= 20
        assert overdue["total"] == 2

    with pytest.raises(DemoBatchExistsError):
        seed_demo(database_path)


def test_seed_reset_preserves_non_demo_batches(tmp_path: Path) -> None:
    database_path = tmp_path / "demo.db"
    first_demo_id = seed_demo(database_path)
    today = current_utc_date()

    initialize_database(database_path)
    with get_connection(database_path) as connection:
        other_batch = create_batch(
            connection,
            BatchCreate(
                name="Lot réel",
                start_date=today - timedelta(days=1),
                initial_count=25,
            ),
        )
        other_batch_id = int(other_batch["id"])

    new_demo_id = seed_demo(database_path, reset=True)

    with get_connection(database_path) as connection:
        demo_count = connection.execute(
            "SELECT COUNT(*) AS total FROM batches WHERE name = ?", (DEMO_BATCH_NAME,)
        ).fetchone()
        other_batch = connection.execute(
            "SELECT * FROM batches WHERE id = ?", (other_batch_id,)
        ).fetchone()

    assert new_demo_id != first_demo_id
    assert demo_count["total"] == 1
    assert other_batch["name"] == "Lot réel"
