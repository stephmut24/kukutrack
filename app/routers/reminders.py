"""Reminder HTTP endpoints."""

from fastapi import APIRouter, HTTPException

from app.routers.batches import DatabaseConnection
from app.schemas import ReminderResponse, ReminderUpdate
from app.services.batches import update_reminder

router = APIRouter(prefix="/api/reminders", tags=["reminders"])


@router.patch("/{reminder_id}", response_model=ReminderResponse)
def edit_reminder(
    reminder_id: int,
    update: ReminderUpdate,
    connection: DatabaseConnection,
) -> dict[str, object]:
    """Mark a reminder done or move it to another date."""
    if update.due_date is None and update.done is None:
        raise HTTPException(
            status_code=422,
            detail="Indiquez une nouvelle date ou l'état du rappel.",
        )
    reminder = update_reminder(connection, reminder_id, update)
    if reminder is None:
        raise HTTPException(status_code=404, detail="Rappel introuvable.")
    return reminder
