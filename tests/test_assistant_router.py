from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import assistant as assistant_router
from app.schemas import ParsedEntry
from app.services.assistant import AssistantBadOutput, AssistantUnavailable
from app.services.logs import current_utc_date


def create_batch(client: TestClient, initial_count: int = 10) -> tuple[int, str]:
    """Create a current active batch for assistant endpoint tests."""
    log_date = (current_utc_date() - timedelta(days=2)).isoformat()
    response = client.post(
        "/api/batches",
        json={"name": "Lot assistant", "start_date": log_date, "initial_count": initial_count},
    )
    assert response.status_code == 201
    return response.json()["id"], log_date


def test_parse_returns_proposal_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KUKUTRACK_DB", str(tmp_path / "test.db"))
    log_date = current_utc_date() - timedelta(days=1)
    monkeypatch.setattr(
        assistant_router,
        "parse_entry",
        lambda _text, _today: ParsedEntry(log_date=log_date, dead_count=2, feed_kg=4),
    )

    with TestClient(app) as client:
        batch_id, _ = create_batch(client)
        response = client.post(
            f"/api/batches/{batch_id}/assistant/parse", json={"text": "2 morts et 4 kg"}
        )
        logs = client.get(f"/api/batches/{batch_id}/logs")
        weigh_ins = client.get(f"/api/batches/{batch_id}/weigh-ins")

    assert response.status_code == 200
    assert response.json()["proposal"]["dead_count"] == 2
    assert response.json()["existing_log"] is None
    assert logs.json() == []
    assert weigh_ins.json() == []


def test_confirm_add_and_replace_daily_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KUKUTRACK_DB", str(tmp_path / "test.db"))

    with TestClient(app) as client:
        batch_id, log_date = create_batch(client)
        proposal = {"log_date": log_date, "dead_count": 1, "feed_kg": 2, "unclear": []}
        add_response = client.post(
            f"/api/batches/{batch_id}/assistant/confirm", json={"proposal": proposal, "mode": "add"}
        )
        duplicate_response = client.post(
            f"/api/batches/{batch_id}/assistant/confirm", json={"proposal": proposal, "mode": "add"}
        )
        replace_response = client.post(
            f"/api/batches/{batch_id}/assistant/confirm",
            json={
                "proposal": {"log_date": log_date, "dead_count": 2, "unclear": []},
                "mode": "replace",
            },
        )
        logs = client.get(f"/api/batches/{batch_id}/logs")

    assert add_response.status_code == 200
    assert add_response.json()["daily_log"]["feed_kg"] == 2
    assert duplicate_response.status_code == 422
    assert replace_response.status_code == 200
    assert replace_response.json()["daily_log"]["dead_count"] == 2
    assert len(logs.json()) == 1
    assert logs.json()[0]["feed_kg"] == 2


def test_confirm_rejects_deaths_above_alive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KUKUTRACK_DB", str(tmp_path / "test.db"))

    with TestClient(app) as client:
        batch_id, log_date = create_batch(client, initial_count=2)
        response = client.post(
            f"/api/batches/{batch_id}/assistant/confirm",
            json={
                "proposal": {"log_date": log_date, "dead_count": 3, "feed_kg": 1, "unclear": []},
                "mode": "add",
            },
        )

    assert response.status_code == 422
    assert "dépasse" in response.json()["detail"]


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [(AssistantUnavailable("offline"), 503), (AssistantBadOutput("bad json"), 422)],
)
def test_parse_maps_assistant_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: Exception, expected_status: int
) -> None:
    monkeypatch.setenv("KUKUTRACK_DB", str(tmp_path / "test.db"))

    def raise_error(_text: str, _today: object) -> ParsedEntry:
        raise error

    monkeypatch.setattr(assistant_router, "parse_entry", raise_error)
    with TestClient(app) as client:
        batch_id, _ = create_batch(client)
        response = client.post(
            f"/api/batches/{batch_id}/assistant/parse", json={"text": "1 mort"}
        )

    assert response.status_code == expected_status
