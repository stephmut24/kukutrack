from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def test_create_batch_saves_calendar(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setenv("KUKUTRACK_DB", str(tmp_path / "test.db"))

    with TestClient(app) as client:
        response = client.post(
            "/api/batches",
            json={
                "name": "Lot test",
                "start_date": "2026-01-01",
                "initial_count": 100,
            },
        )
        assert response.status_code == 201
        batch = response.json()
        assert batch["id"] > 0
        assert batch["target_weight_g"] == 3000

        detail_response = client.get(f"/api/batches/{batch['id']}")
        reminder = detail_response.json()["reminders"][0]
        reminder_response = client.patch(
            f"/api/reminders/{reminder['id']}", json={"done": True}
        )

    assert detail_response.status_code == 200
    assert len(detail_response.json()["reminders"]) == 41
    assert reminder_response.status_code == 200
    assert reminder_response.json()["done"] is True
    assert reminder_response.json()["done_at"] is not None


def test_create_batch_rejects_non_positive_count(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setenv("KUKUTRACK_DB", str(tmp_path / "test.db"))

    with TestClient(app) as client:
        response = client.post(
            "/api/batches",
            json={"name": "Lot invalide", "start_date": "2026-01-01", "initial_count": 0},
        )

    assert response.status_code == 422
