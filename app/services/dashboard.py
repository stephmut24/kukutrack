"""Database assembly for the dashboard response."""

import sqlite3

from app.services.logs import BatchNotFoundError, current_utc_date, summary_counts
from app.services.stats import (
    daily_mortality_series,
    feed_series,
    latest_weight_vs_target,
    load_target_curve,
    mortality_rate,
    weight_series,
)


def load_batch_records(connection: sqlite3.Connection, batch_id: int) -> dict[str, object]:
    """Load the local records shared by dashboard, alerts, and weekly summary."""
    batch_row = connection.execute("SELECT * FROM batches WHERE id = ?", (batch_id,)).fetchone()
    if batch_row is None:
        raise BatchNotFoundError("Lot introuvable.")
    daily_logs = [
        dict(row)
        for row in connection.execute(
            "SELECT * FROM daily_logs WHERE batch_id = ? ORDER BY log_date, id", (batch_id,)
        ).fetchall()
    ]
    weigh_ins = [
        dict(row)
        for row in connection.execute(
            "SELECT * FROM weigh_ins WHERE batch_id = ? ORDER BY weigh_date, id", (batch_id,)
        ).fetchall()
    ]
    reminders = [
        dict(row)
        for row in connection.execute(
            "SELECT * FROM reminders WHERE batch_id = ? ORDER BY due_date, id", (batch_id,)
        ).fetchall()
    ]
    return {
        "batch": dict(batch_row),
        "daily_logs": daily_logs,
        "weigh_ins": weigh_ins,
        "reminders": reminders,
    }


def get_dashboard(connection: sqlite3.Connection, batch_id: int) -> dict[str, object]:
    """Build all dashboard values for one batch from local SQLite records."""
    records = load_batch_records(connection, batch_id)
    batch = records["batch"]
    daily_logs = records["daily_logs"]
    weigh_ins = records["weigh_ins"]
    if not isinstance(batch, dict) or not isinstance(daily_logs, list) or not isinstance(weigh_ins, list):
        raise TypeError("Les données du lot sont invalides.")
    anchors = load_target_curve()
    feed = feed_series(batch, daily_logs)
    counts = summary_counts(connection, batch_id)
    overdue_reminders = connection.execute(
        """
        SELECT COUNT(*) AS total FROM reminders
        WHERE batch_id = ? AND done = 0 AND due_date < ?
        """,
        (batch_id, current_utc_date().isoformat()),
    ).fetchone()

    return {
        **counts,
        "mortality_rate_percent": mortality_rate(batch, daily_logs),
        "total_feed_kg": feed[-1]["cumulative_feed_kg"] if feed else 0.0,
        "latest_weight_vs_target": latest_weight_vs_target(batch, weigh_ins, anchors),
        "overdue_reminders": int(overdue_reminders["total"]),
        "daily_mortality": daily_mortality_series(batch, daily_logs),
        "feed": feed,
        "weight": weight_series(batch, weigh_ins, anchors),
    }
