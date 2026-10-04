"""Pure calculations for batch statistics and target-weight comparisons."""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from itertools import pairwise
from pathlib import Path
from typing import Any

from app.config import PROJECT_DIR

TARGET_CURVE_PATH = PROJECT_DIR / "config" / "target_curve.json"


@dataclass(frozen=True)
class TargetAnchor:
    """One editable target-weight point from the configuration file."""

    day: int
    weight_g: float


def load_target_curve(path: Path = TARGET_CURVE_PATH) -> list[TargetAnchor]:
    """Load and validate editable target-weight anchors."""
    with path.open(encoding="utf-8") as curve_file:
        data: Any = json.load(curve_file)
    if not isinstance(data, dict) or not isinstance(data.get("anchors"), list):
        raise TypeError("La courbe cible doit contenir une liste de points.")

    anchors: list[TargetAnchor] = []
    for item in data["anchors"]:
        if not isinstance(item, dict):
            raise TypeError("Un point de la courbe cible est invalide.")
        day = item.get("day")
        weight_g = item.get("weight_g")
        if not isinstance(day, int) or day <= 0:
            raise ValueError("Le jour de la courbe cible doit être positif.")
        if not isinstance(weight_g, (int, float)) or weight_g <= 0:
            raise ValueError("Le poids de la courbe cible doit être positif.")
        anchors.append(TargetAnchor(day=day, weight_g=float(weight_g)))

    if len(anchors) < 2 or anchors != sorted(anchors, key=lambda anchor: anchor.day):
        raise ValueError("La courbe cible doit contenir au moins deux jours croissants.")
    if len({anchor.day for anchor in anchors}) != len(anchors):
        raise ValueError("Les jours de la courbe cible doivent être uniques.")
    return anchors


def _start_date(batch: Mapping[str, object]) -> date:
    """Read a batch's ISO start date."""
    return date.fromisoformat(str(batch["start_date"]))


def _day_number(batch: Mapping[str, object], record_date: str) -> int:
    """Return the one-based day number for a record date."""
    return (date.fromisoformat(record_date) - _start_date(batch)).days + 1


def _logs_by_date(logs: Sequence[Mapping[str, object]]) -> dict[date, Mapping[str, object]]:
    """Index the one-per-day logs by their date."""
    return {date.fromisoformat(str(log["log_date"])): log for log in logs}


def mortality_rate(batch: Mapping[str, object], daily_logs: Sequence[Mapping[str, object]]) -> float:
    """Return mortality as a percentage of the initial bird count."""
    initial_count = int(batch["initial_count"])
    total_dead = sum(int(log["dead_count"]) for log in daily_logs)
    return round(total_dead / initial_count * 100, 2) if initial_count else 0.0


def daily_mortality_series(
    batch: Mapping[str, object], daily_logs: Sequence[Mapping[str, object]]
) -> list[dict[str, int | str]]:
    """Return daily and cumulative mortality, including unlogged days as zero."""
    if not daily_logs:
        return []
    logs_by_date = _logs_by_date(daily_logs)
    current_date = _start_date(batch)
    last_date = max(logs_by_date)
    cumulative_dead = 0
    series: list[dict[str, int | str]] = []
    while current_date <= last_date:
        log = logs_by_date.get(current_date)
        dead_count = int(log["dead_count"]) if log else 0
        cumulative_dead += dead_count
        series.append(
            {
                "date": current_date.isoformat(),
                "day_number": (current_date - _start_date(batch)).days + 1,
                "dead_count": dead_count,
                "cumulative_dead": cumulative_dead,
            }
        )
        current_date += timedelta(days=1)
    return series


def feed_series(
    batch: Mapping[str, object], daily_logs: Sequence[Mapping[str, object]]
) -> list[dict[str, float | int | str | None]]:
    """Return feed totals and feed per living bird, filling days without a log."""
    if not daily_logs:
        return []
    logs_by_date = _logs_by_date(daily_logs)
    current_date = _start_date(batch)
    last_date = max(logs_by_date)
    initial_count = int(batch["initial_count"])
    cumulative_dead = 0
    cumulative_feed = 0.0
    series: list[dict[str, float | int | str | None]] = []
    while current_date <= last_date:
        log = logs_by_date.get(current_date)
        dead_count = int(log["dead_count"]) if log else 0
        feed_kg = float(log["feed_kg"]) if log else 0.0
        cumulative_dead += dead_count
        cumulative_feed += feed_kg
        birds_alive = initial_count - cumulative_dead
        series.append(
            {
                "date": current_date.isoformat(),
                "day_number": (current_date - _start_date(batch)).days + 1,
                "feed_kg": round(feed_kg, 3),
                "cumulative_feed_kg": round(cumulative_feed, 3),
                "birds_alive": birds_alive,
                "feed_per_bird_kg": round(feed_kg / birds_alive, 3) if birds_alive else None,
                "cumulative_feed_per_initial_bird_kg": round(cumulative_feed / initial_count, 3),
            }
        )
        current_date += timedelta(days=1)
    return series


def target_weight_for_day(
    day_number: int, target_weight_g: float, anchors: Sequence[TargetAnchor]
) -> float:
    """Interpolate a configured curve and scale its final point to the batch target."""
    final_anchor = anchors[-1]
    scale = target_weight_g / final_anchor.weight_g
    if day_number <= anchors[0].day:
        return round(anchors[0].weight_g * scale, 1)
    if day_number >= final_anchor.day:
        return round(target_weight_g, 1)
    for lower, upper in pairwise(anchors):
        if lower.day <= day_number <= upper.day:
            progress = (day_number - lower.day) / (upper.day - lower.day)
            weight = lower.weight_g + (upper.weight_g - lower.weight_g) * progress
            return round(weight * scale, 1)
    raise ValueError("Le jour demandé est absent de la courbe cible.")


def weight_series(
    batch: Mapping[str, object],
    weigh_ins: Sequence[Mapping[str, object]],
    anchors: Sequence[TargetAnchor],
) -> list[dict[str, float | int | str]]:
    """Return weigh-ins ordered by batch day together with their target weights."""
    target_weight_g = float(batch["target_weight_g"])
    series = [
        {
            "date": str(weigh_in["weigh_date"]),
            "day_number": _day_number(batch, str(weigh_in["weigh_date"])),
            "average_weight_g": float(weigh_in["average_weight_g"]),
            "target_weight_g": target_weight_for_day(
                _day_number(batch, str(weigh_in["weigh_date"])), target_weight_g, anchors
            ),
        }
        for weigh_in in weigh_ins
    ]
    return sorted(series, key=lambda point: int(point["day_number"]))


def latest_weight_vs_target(
    batch: Mapping[str, object],
    weigh_ins: Sequence[Mapping[str, object]],
    anchors: Sequence[TargetAnchor],
) -> dict[str, float | int | None]:
    """Return the latest measured weight, target, and percentage gap."""
    series = weight_series(batch, weigh_ins, anchors)
    if not series:
        return {"day_number": None, "average_weight_g": None, "target_weight_g": None, "gap_percent": None}
    latest = series[-1]
    target_weight_g = float(latest["target_weight_g"])
    average_weight_g = float(latest["average_weight_g"])
    return {
        "day_number": int(latest["day_number"]),
        "average_weight_g": average_weight_g,
        "target_weight_g": target_weight_g,
        "gap_percent": round((average_weight_g - target_weight_g) / target_weight_g * 100, 2),
    }
