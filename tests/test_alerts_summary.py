from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.alerts import AlertThresholds, compute_alerts
from app.services.logs import current_utc_date
from app.services.stats import TargetAnchor
from app.services.summary import SummaryResult, render_ai_summary

THRESHOLDS = AlertThresholds(
    daily_mortality_percent=3,
    cumulative_mortality_percent=10,
    weight_below_target_percent=10,
    no_log_days=3,
    overdue_reminders_count=1,
)
BATCH = {"start_date": "2026-10-01", "initial_count": 100, "target_weight_g": 3000}
ANCHORS = [TargetAnchor(day=1, weight_g=1000), TargetAnchor(day=10, weight_g=3000)]


def codes(alerts: list[dict[str, object]]) -> list[str]:
    """Extract alert codes for concise deterministic assertions."""
    return [str(alert["code"]) for alert in alerts]


def test_daily_and_cumulative_mortality_threshold_boundaries() -> None:
    boundary_logs = [{"log_date": "2026-10-02", "dead_count": 3, "feed_kg": 1}]
    triggered_logs = [{"log_date": "2026-10-02", "dead_count": 11, "feed_kg": 1}]

    boundary_alerts = compute_alerts(
        BATCH,
        boundary_logs,
        today=date(2026, 10, 2),
        thresholds=THRESHOLDS,
    )
    triggered_alerts = compute_alerts(
        BATCH,
        triggered_logs,
        today=date(2026, 10, 2),
        thresholds=THRESHOLDS,
    )

    assert "daily_mortality_high" not in codes(boundary_alerts)
    assert "cumulative_mortality_high" not in codes(boundary_alerts)
    assert "daily_mortality_high" in codes(triggered_alerts)
    assert "cumulative_mortality_high" in codes(triggered_alerts)


def test_weight_missing_logs_and_overdue_reminder_threshold_boundaries() -> None:
    boundary_weight = [{"weigh_date": "2026-10-10", "sample_size": 5, "average_weight_g": 2700}]
    low_weight = [{"weigh_date": "2026-10-10", "sample_size": 5, "average_weight_g": 2690}]
    no_alerts = compute_alerts(
        BATCH,
        [{"log_date": "2026-10-08", "dead_count": 0, "feed_kg": 1}],
        boundary_weight,
        [{"due_date": "2026-10-10", "done": False}],
        today=date(2026, 10, 10),
        thresholds=THRESHOLDS,
        anchors=ANCHORS,
    )
    alerts = compute_alerts(
        BATCH,
        [],
        low_weight,
        [{"due_date": "2026-10-09", "done": False}],
        today=date(2026, 10, 10),
        thresholds=THRESHOLDS,
        anchors=ANCHORS,
    )
    exact_missing_log_boundary = compute_alerts(
        BATCH,
        [],
        today=date(2026, 10, 4),
        thresholds=THRESHOLDS,
    )

    assert "weight_below_target" not in codes(no_alerts)
    assert "missing_logs" not in codes(no_alerts)
    assert "overdue_reminders" not in codes(no_alerts)
    assert {"weight_below_target", "missing_logs", "overdue_reminders"} <= set(codes(alerts))
    assert "missing_logs" in codes(exact_missing_log_boundary)


def summary_facts() -> dict[str, object]:
    """Provide hand-written facts for summary guardrail tests."""
    return {
        "dead_this_week": 2,
        "mortality_this_week_percent": 2.0,
        "feed_this_week_kg": 4.0,
        "feed_per_bird_kg": 0.04,
        "birds_alive": 98,
        "latest_weight": {
            "day_number": 7,
            "average_weight_g": 700.0,
            "target_weight_g": 800.0,
            "gap_percent": -12.5,
        },
        "overdue_reminders": 1,
        "alerts": [],
    }


def test_summary_guardrail_rejects_invented_number_and_forbidden_word() -> None:
    facts = summary_facts()

    invented_number = render_ai_summary(
        facts, lambda _system, _facts: "Cette semaine, 999 morts."
    )
    forbidden_word = render_ai_summary(
        facts, lambda _system, _facts: "Un antibiotique est nécessaire."
    )

    assert invented_number.source == "template"
    assert forbidden_word.source == "template"


def test_summary_uses_template_when_ollama_is_unavailable() -> None:
    def unavailable(_system: str, _facts: str) -> str:
        from app.services.ollama_client import AssistantUnavailable

        raise AssistantUnavailable("hors ligne")

    result = render_ai_summary(summary_facts(), unavailable)

    assert result.source == "template"
    assert "Cette semaine" in result.text


def test_alert_and_summary_endpoints(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setenv("KUKUTRACK_DB", str(tmp_path / "test.db"))
    monkeypatch.setattr(
        "app.routers.alerts.render_ai_summary",
        lambda _facts: SummaryResult(text="Résumé validé.", source="template"),
    )
    today = current_utc_date()
    start_date = (today - timedelta(days=4)).isoformat()

    with TestClient(app) as client:
        batch_response = client.post(
            "/api/batches",
            json={"name": "Lot alertes", "start_date": start_date, "initial_count": 10},
        )
        batch_id = batch_response.json()["id"]
        client.post(
            f"/api/batches/{batch_id}/logs",
            json={"log_date": start_date, "dead_count": 1, "feed_kg": 2},
        )
        alerts_response = client.get(f"/api/batches/{batch_id}/alerts")
        summary_response = client.get(f"/api/batches/{batch_id}/summary")

    assert alerts_response.status_code == 200
    assert isinstance(alerts_response.json(), list)
    assert summary_response.json() == {"text": "Résumé validé.", "source": "template"}
