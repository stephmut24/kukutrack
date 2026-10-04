"""Configurable, deterministic alerts based only on stored farm data."""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from app.config import ALERT_THRESHOLDS_PATH
from app.services.stats import TargetAnchor, latest_weight_vs_target, mortality_rate


@dataclass(frozen=True)
class AlertThresholds:
    """Editable limits that decide whether an alert is shown."""

    daily_mortality_percent: float
    cumulative_mortality_percent: float
    weight_below_target_percent: float
    no_log_days: int
    overdue_reminders_count: int


def load_alert_thresholds(path: Path = ALERT_THRESHOLDS_PATH) -> AlertThresholds:
    """Load and validate the farmer-editable alert limits."""
    with path.open(encoding="utf-8") as thresholds_file:
        data: Any = json.load(thresholds_file)
    if not isinstance(data, dict):
        raise TypeError("Les seuils d'alerte doivent être un objet JSON.")

    percentage_keys = (
        "daily_mortality_percent",
        "cumulative_mortality_percent",
        "weight_below_target_percent",
    )
    values: dict[str, float | int] = {}
    for key in percentage_keys:
        value = data.get(key)
        if not isinstance(value, (int, float)) or value < 0:
            raise ValueError(f"Le seuil {key} doit être un nombre positif.")
        values[key] = float(value)
    for key in ("no_log_days", "overdue_reminders_count"):
        value = data.get(key)
        if not isinstance(value, int) or value < 1:
            raise ValueError(f"Le seuil {key} doit être un entier supérieur à zéro.")
        values[key] = value
    return AlertThresholds(**values)  # type: ignore[arg-type]


def _alert(
    code: str, level: str, message: str, **values: float | str
) -> dict[str, object]:
    """Build one response-ready alert with its measured values."""
    return {"code": code, "level": level, "message": message, "values": values}


def _daily_mortality_alerts(
    batch: Mapping[str, object],
    daily_logs: Sequence[Mapping[str, object]],
    threshold: float,
) -> list[dict[str, object]]:
    """Return an alert for each logged day above the configured mortality limit."""
    alive_before_day = int(batch["initial_count"])
    alerts: list[dict[str, object]] = []
    for log in sorted(daily_logs, key=lambda item: str(item["log_date"])):
        dead_count = int(log["dead_count"])
        mortality_percent = round(dead_count / alive_before_day * 100, 2) if alive_before_day else 0.0
        if mortality_percent > threshold:
            alerts.append(
                _alert(
                    "daily_mortality_high",
                    "warning",
                    "La mortalité du jour est plus élevée que le seuil configuré. "
                    "Vérifie la température, l'eau et l'aliment, et demande l'avis "
                    "d'un vétérinaire si cela continue.",
                    date=str(log["log_date"]),
                    dead_count=dead_count,
                    birds_alive_before=alive_before_day,
                    mortality_percent=mortality_percent,
                    threshold_percent=threshold,
                )
            )
        alive_before_day -= dead_count
    return alerts


def _days_without_log(
    batch: Mapping[str, object], daily_logs: Sequence[Mapping[str, object]], today: date
) -> int:
    """Count complete calendar days since the latest log or the batch start."""
    start_date = date.fromisoformat(str(batch["start_date"]))
    log_dates = [date.fromisoformat(str(log["log_date"])) for log in daily_logs]
    latest_log_date = max(log_dates) if log_dates else start_date
    return max(0, (today - latest_log_date).days)


def compute_alerts(
    batch: Mapping[str, object],
    daily_logs: Sequence[Mapping[str, object]] = (),
    weigh_ins: Sequence[Mapping[str, object]] = (),
    reminders: Sequence[Mapping[str, object]] = (),
    *,
    today: date,
    thresholds: AlertThresholds | None = None,
    anchors: Sequence[TargetAnchor] = (),
) -> list[dict[str, object]]:
    """Apply only configurable deterministic rules and return their French alerts."""
    configured_thresholds = thresholds or load_alert_thresholds()
    alerts = _daily_mortality_alerts(
        batch, daily_logs, configured_thresholds.daily_mortality_percent
    )
    cumulative_percent = mortality_rate(batch, daily_logs)
    total_dead = sum(int(log["dead_count"]) for log in daily_logs)
    if cumulative_percent > configured_thresholds.cumulative_mortality_percent:
        alerts.append(
            _alert(
                "cumulative_mortality_high",
                "warning",
                "La mortalité cumulée est plus élevée que le seuil configuré. "
                "Vérifie la température, l'eau et l'aliment, et demande l'avis "
                "d'un vétérinaire si cela continue.",
                total_dead=total_dead,
                mortality_percent=cumulative_percent,
                threshold_percent=configured_thresholds.cumulative_mortality_percent,
            )
        )

    if weigh_ins and anchors:
        latest_weight = latest_weight_vs_target(batch, weigh_ins, anchors)
        gap_percent = latest_weight["gap_percent"]
        if (
            gap_percent is not None
            and float(gap_percent) < -configured_thresholds.weight_below_target_percent
        ):
            alerts.append(
                _alert(
                    "weight_below_target",
                    "warning",
                    "Le dernier poids mesuré est inférieur à la cible configurée. "
                    "Vérifiez les données de pesée et le plan d'élevage.",
                    day_number=int(latest_weight["day_number"]),
                    average_weight_g=float(latest_weight["average_weight_g"]),
                    target_weight_g=float(latest_weight["target_weight_g"]),
                    gap_percent=float(gap_percent),
                    threshold_percent=configured_thresholds.weight_below_target_percent,
                )
            )

    days_without_log = _days_without_log(batch, daily_logs, today)
    if days_without_log >= configured_thresholds.no_log_days:
        alerts.append(
            _alert(
                "missing_logs",
                "info",
                "Aucun journal n'a été enregistré depuis plusieurs jours.",
                days_without_log=days_without_log,
                threshold_days=configured_thresholds.no_log_days,
            )
        )

    overdue_reminders = [
        reminder
        for reminder in reminders
        if not bool(reminder["done"]) and date.fromisoformat(str(reminder["due_date"])) < today
    ]
    if len(overdue_reminders) >= configured_thresholds.overdue_reminders_count:
        alerts.append(
            _alert(
                "overdue_reminders",
                "info",
                "Des rappels sont en retard.",
                overdue_reminders=len(overdue_reminders),
                threshold_count=configured_thresholds.overdue_reminders_count,
            )
        )
    return alerts
