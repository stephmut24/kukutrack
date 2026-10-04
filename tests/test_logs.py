import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import get_connection, initialize_database
from app.main import app
from app.schemas import BatchCreate, DailyLogCreate
from app.services.batches import create_batch
from app.services.logs import (
    LogValidationError,
    add_daily_log,
    birds_alive,
    summary_counts,
)

TODAY = datetime.now(timezone.utc).date()


def create_test_batch(connection: sqlite3.Connection, initial_count: int = 10) -> int:
    """Create a batch that started early enough for daily-log tests."""
    batch = create_batch(
        connection,
        BatchCreate(
            name="Lot journal",
            start_date=TODAY - timedelta(days=5),
            initial_count=initial_count,
        ),
    )
    return int(batch["id"])


def test_birds_alive_after_several_logs(tmp_path: Path) -> None:
    database_path = tmp_path / "test.db"
    initialize_database(database_path)
    connection = get_connection(database_path)
    batch_id = create_test_batch(connection)
    start_date = TODAY - timedelta(days=5)

    add_daily_log(
        connection, batch_id, DailyLogCreate(log_date=start_date, dead_count=2, feed_kg=1)
    )
    add_daily_log(
        connection,
        batch_id,
        DailyLogCreate(log_date=start_date + timedelta(days=1), dead_count=1, feed_kg=1),
    )

    assert birds_alive(connection, batch_id, start_date) == 8
    assert birds_alive(connection, batch_id) == 7
    assert summary_counts(connection, batch_id)["total_dead"] == 3
    connection.close()


def test_daily_log_rules_reject_invalid_records(tmp_path: Path) -> None:
    database_path = tmp_path / "test.db"
    initialize_database(database_path)
    connection = get_connection(database_path)
    batch_id = create_test_batch(connection)
    start_date = TODAY - timedelta(days=5)
    add_daily_log(
        connection, batch_id, DailyLogCreate(log_date=start_date, dead_count=3, feed_kg=1)
    )

    with pytest.raises(LogValidationError, match="existe déjà"):
        add_daily_log(
            connection, batch_id, DailyLogCreate(log_date=start_date, dead_count=0, feed_kg=1)
        )
    with pytest.raises(LogValidationError, match="dépasse"):
        add_daily_log(
            connection,
            batch_id,
            DailyLogCreate(log_date=start_date + timedelta(days=1), dead_count=8, feed_kg=1),
        )
    with pytest.raises(LogValidationError, match="négative"):
        add_daily_log(
            connection,
            batch_id,
            DailyLogCreate.model_construct(log_date=start_date + timedelta(days=1), dead_count=0, feed_kg=-1),
        )
    with pytest.raises(LogValidationError, match="avant"):
        add_daily_log(
            connection,
            batch_id,
            DailyLogCreate(log_date=start_date - timedelta(days=1), dead_count=0, feed_kg=1),
        )
    with pytest.raises(LogValidationError, match="futur"):
        add_daily_log(
            connection,
            batch_id,
            DailyLogCreate(log_date=TODAY + timedelta(days=1), dead_count=0, feed_kg=1),
        )

    with connection:
        connection.execute("UPDATE batches SET status = 'closed' WHERE id = ?", (batch_id,))
    with pytest.raises(LogValidationError, match="fermé"):
        add_daily_log(
            connection,
            batch_id,
            DailyLogCreate(log_date=start_date + timedelta(days=1), dead_count=0, feed_kg=1),
        )
    connection.close()


def test_log_and_weigh_in_api_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KUKUTRACK_DB", str(tmp_path / "test.db"))
    start_date = (TODAY - timedelta(days=2)).isoformat()

    with TestClient(app) as client:
        batch_response = client.post(
            "/api/batches",
            json={"name": "Lot API", "start_date": start_date, "initial_count": 20},
        )
        batch_id = batch_response.json()["id"]
        log_response = client.post(
            f"/api/batches/{batch_id}/logs",
            json={"log_date": start_date, "dead_count": 2, "feed_kg": 4.5, "note": "RAS"},
        )
        duplicate_response = client.post(
            f"/api/batches/{batch_id}/logs",
            json={"log_date": start_date, "dead_count": 0, "feed_kg": 2},
        )
        weigh_in_response = client.post(
            f"/api/batches/{batch_id}/weigh-ins",
            json={"weigh_date": start_date, "sample_size": 5, "average_weight_g": 550},
        )
        summary_response = client.get(f"/api/batches/{batch_id}/summary-counts")
        update_response = client.patch(
            f"/api/logs/{log_response.json()['id']}", json={"dead_count": 1}
        )
        delete_weigh_in_response = client.delete(
            f"/api/weigh-ins/{weigh_in_response.json()['id']}"
        )
        delete_log_response = client.delete(f"/api/logs/{log_response.json()['id']}")

    assert batch_response.status_code == 201
    assert log_response.status_code == 201
    assert duplicate_response.status_code == 422
    assert "existe déjà" in duplicate_response.json()["detail"]
    assert weigh_in_response.status_code == 201
    assert summary_response.json() == {"birds_alive": 18, "total_dead": 2, "day_number": 3}
    assert update_response.status_code == 200
    assert update_response.json()["dead_count"] == 1
    assert delete_weigh_in_response.status_code == 204
    assert delete_log_response.status_code == 204
