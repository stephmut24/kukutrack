"""Generate editable reminder calendars from the schedule configuration."""

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from app.config import DEFAULT_SCHEDULE_PATH


@dataclass(frozen=True)
class ReminderDraft:
    due_date: date
    category: str
    title: str
    details: str | None


def load_schedule(path: Path = DEFAULT_SCHEDULE_PATH) -> list[dict[str, Any]]:
    """Load the reminder definitions from the editable JSON schedule."""
    with path.open(encoding="utf-8") as schedule_file:
        schedule = json.load(schedule_file)

    if not isinstance(schedule, dict):
        raise TypeError("Le calendrier par défaut doit être un objet JSON.")
    reminders = schedule.get("reminders")
    if not isinstance(reminders, list):
        raise TypeError("Le calendrier par défaut doit contenir une liste de rappels.")
    return reminders


def generate_reminder_drafts(
    start_date: date, path: Path = DEFAULT_SCHEDULE_PATH
) -> list[ReminderDraft]:
    """Turn configured day offsets into reminder drafts for one batch."""
    drafts: list[ReminderDraft] = []
    for item in load_schedule(path):
        try:
            day_offset = item["day_offset"]
            category = item["category"]
            title = item["title"]
        except KeyError as error:
            raise ValueError("Un rappel du calendrier est incomplet.") from error

        if not isinstance(day_offset, int) or day_offset < 0:
            raise ValueError("Le décalage de jour d'un rappel doit être positif.")
        if not all(isinstance(value, str) and value for value in (category, title)):
            raise ValueError("La catégorie et le titre d'un rappel sont obligatoires.")

        details = item.get("details")
        if details is not None and not isinstance(details, str):
            raise ValueError("Les détails d'un rappel doivent être du texte.")
        drafts.append(
            ReminderDraft(
                due_date=start_date + timedelta(days=day_offset),
                category=category,
                title=title,
                details=details,
            )
        )
    return drafts
