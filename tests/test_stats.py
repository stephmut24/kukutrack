from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.stats import (
    TargetAnchor,
    daily_mortality_series,
    feed_series,
    latest_weight_vs_target,
    mortality_rate,
    target_weight_for_day,
    weight_series,
)

ANCHORS = [TargetAnchor(day=1, weight_g=1000), TargetAnchor(day=5, weight_g=3000)]
BATCH = {"start_date": "2026-01-01", "initial_count": 10, "target_weight_g": 3000}
LOGS = [
    {"log_date": "2026-01-01", "dead_count": 1, "feed_kg": 2},
    {"log_date": "2026-01-03", "dead_count": 2, "feed_kg": 3},
]
WEIGH_INS = [
    {"weigh_date": "2026-01-03", "sample_size": 4, "average_weight_g": 2200},
    {"weigh_date": "2026-01-02", "sample_size": 4, "average_weight_g": 1600},
]


def test_stats_series_with_a_gap_are_hand_computed() -> None:
    mortality = daily_mortality_series(BATCH, LOGS)
    feed = feed_series(BATCH, LOGS)

    assert mortality_rate(BATCH, LOGS) == 30.0
    assert mortality == [
        {"date": "2026-01-01", "day_number": 1, "dead_count": 1, "cumulative_dead": 1},
        {"date": "2026-01-02", "day_number": 2, "dead_count": 0, "cumulative_dead": 1},
        {"date": "2026-01-03", "day_number": 3, "dead_count": 2, "cumulative_dead": 3},
    ]
    assert feed[0]["feed_per_bird_kg"] == 0.222
    assert feed[1]["feed_kg"] == 0.0
    assert feed[2]["birds_alive"] == 7
    assert feed[2]["feed_per_bird_kg"] == 0.429
    assert feed[2]["cumulative_feed_per_initial_bird_kg"] == 0.5


def test_weight_target_and_empty_stats() -> None:
    weights = weight_series(BATCH, WEIGH_INS, ANCHORS)
    latest = latest_weight_vs_target(BATCH, WEIGH_INS, ANCHORS)

    assert target_weight_for_day(3, 3000, ANCHORS) == 2000.0
    assert [point["day_number"] for point in weights] == [2, 3]
    assert weights[0]["target_weight_g"] == 1500.0
    assert latest == {
        "day_number": 3,
        "average_weight_g": 2200.0,
        "target_weight_g": 2000.0,
        "gap_percent": 10.0,
    }
    assert mortality_rate(BATCH, []) == 0.0
    assert daily_mortality_series(BATCH, []) == []
    assert feed_series(BATCH, []) == []
    assert latest_weight_vs_target(BATCH, [], ANCHORS)["average_weight_g"] is None


def test_dashboard_endpoint_returns_all_series(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setenv("KUKUTRACK_DB", str(tmp_path / "test.db"))
    today = datetime.now(timezone.utc).date()
    start_date = (today - timedelta(days=2)).isoformat()

    with TestClient(app) as client:
        batch_response = client.post(
            "/api/batches",
            json={"name": "Lot tableau", "start_date": start_date, "initial_count": 10},
        )
        batch_id = batch_response.json()["id"]
        client.post(
            f"/api/batches/{batch_id}/logs",
            json={"log_date": start_date, "dead_count": 1, "feed_kg": 2},
        )
        client.post(
            f"/api/batches/{batch_id}/weigh-ins",
            json={"weigh_date": start_date, "sample_size": 3, "average_weight_g": 50},
        )
        response = client.get(f"/api/batches/{batch_id}/dashboard")

    body = response.json()
    assert response.status_code == 200
    assert body["birds_alive"] == 9
    assert body["total_dead"] == 1
    assert body["mortality_rate_percent"] == 10.0
    assert body["total_feed_kg"] == 2.0
    assert body["latest_weight_vs_target"]["average_weight_g"] == 50.0
    assert len(body["daily_mortality"]) == 1
    assert len(body["feed"]) == 1
    assert len(body["weight"]) == 1
