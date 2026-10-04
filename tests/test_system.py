import sqlite3
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from app.db import get_connection
from app.main import app
from app.services.system_status import ollama_is_available


def test_ollama_status_accepts_the_configured_model() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [{"name": "gemma3:4b"}]})

    assert ollama_is_available(
        model="gemma3:4b", transport=httpx.MockTransport(handler)
    )


def test_ollama_status_handles_an_unreachable_server() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    assert not ollama_is_available(
        model="gemma3:4b", transport=httpx.MockTransport(handler)
    )


def test_status_endpoint_reports_mocked_assistant_state(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setenv("KUKUTRACK_DB", str(tmp_path / "test.db"))
    monkeypatch.setattr(
        "app.routers.status.get_system_status",
        lambda: {"server": "ok", "database": "ok", "assistant": "unavailable"},
    )

    with TestClient(app) as client:
        response = client.get("/api/status")

    assert response.status_code == 200
    assert response.json() == {"server": "ok", "database": "ok", "assistant": "unavailable"}


def test_backup_download_can_be_reopened(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setenv("KUKUTRACK_DB", str(tmp_path / "test.db"))

    with TestClient(app) as client:
        create_response = client.post(
            "/api/batches",
            json={"name": "Lot sauvegardé", "start_date": "2026-01-01", "initial_count": 12},
        )
        backup_response = client.get("/api/backup")

    restored_path = tmp_path / "restored.db"
    restored_path.write_bytes(backup_response.content)
    with sqlite3.connect(restored_path) as connection:
        batch_count = connection.execute("SELECT COUNT(*) FROM batches").fetchone()[0]

    assert create_response.status_code == 201
    assert backup_response.status_code == 200
    assert backup_response.headers["content-type"] == "application/x-sqlite3"
    assert batch_count == 1


def test_connections_use_wal_and_busy_timeout(tmp_path: Path) -> None:
    database_path = tmp_path / "test.db"
    with get_connection(database_path) as connection:
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        busy_timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]

    assert journal_mode == "wal"
    assert busy_timeout == 5000
