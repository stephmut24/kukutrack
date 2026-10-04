"""Read-only alert and weekly-summary HTTP endpoints."""

from fastapi import APIRouter, HTTPException

from app.routers.batches import DatabaseConnection
from app.schemas import AlertResponse, WeeklySummaryResponse
from app.services.alerts import compute_alerts
from app.services.dashboard import load_batch_records
from app.services.logs import BatchNotFoundError, current_utc_date
from app.services.stats import load_target_curve
from app.services.summary import build_summary_facts, render_ai_summary

router = APIRouter(tags=["alerts"])


def _records_and_alerts(connection: DatabaseConnection, batch_id: int) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Read a batch once and apply its deterministic alert rules."""
    records = load_batch_records(connection, batch_id)
    batch = records["batch"]
    daily_logs = records["daily_logs"]
    weigh_ins = records["weigh_ins"]
    reminders = records["reminders"]
    if not all(isinstance(value, list) for value in (daily_logs, weigh_ins, reminders)) or not isinstance(batch, dict):
        raise RuntimeError("Les données du lot sont invalides.")
    alerts = compute_alerts(
        batch,
        daily_logs,
        weigh_ins,
        reminders,
        today=current_utc_date(),
        anchors=load_target_curve(),
    )
    return records, alerts


@router.get("/api/batches/{batch_id}/alerts", response_model=list[AlertResponse])
def read_alerts(batch_id: int, connection: DatabaseConnection) -> list[dict[str, object]]:
    """Return deterministic alerts for one batch without contacting the model."""
    try:
        _, alerts = _records_and_alerts(connection, batch_id)
        return alerts
    except BatchNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/api/batches/{batch_id}/summary", response_model=WeeklySummaryResponse)
def read_weekly_summary(batch_id: int, connection: DatabaseConnection) -> dict[str, str]:
    """Return a safe local-AI weekly wording, or its deterministic fallback."""
    try:
        records, alerts = _records_and_alerts(connection, batch_id)
        batch = records["batch"]
        daily_logs = records["daily_logs"]
        weigh_ins = records["weigh_ins"]
        reminders = records["reminders"]
        if (
            not isinstance(batch, dict)
            or not isinstance(daily_logs, list)
            or not isinstance(weigh_ins, list)
            or not isinstance(reminders, list)
        ):
            raise TypeError("Les données du lot sont invalides.")
        facts = build_summary_facts(
            batch,
            daily_logs,
            weigh_ins,
            reminders,
            alerts,
            today=current_utc_date(),
            anchors=load_target_curve(),
        )
        summary = render_ai_summary(facts)
        return {"text": summary.text, "source": summary.source}
    except BatchNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
