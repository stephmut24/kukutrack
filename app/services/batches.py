"""Batch and reminder persistence operations."""

import sqlite3
from datetime import datetime, timezone

from app.schemas import BatchCreate, ReminderUpdate
from app.services.calendar import generate_reminder_drafts


def _row_to_dict(row: sqlite3.Row) -> dict[str, object]:
    result = dict(row)
    if "done" in result:
        result["done"] = bool(result["done"])
    return result


def create_batch(connection: sqlite3.Connection, batch: BatchCreate) -> dict[str, object]:
    """Save a batch and all reminders generated from the configured calendar."""
    created_at = datetime.now(timezone.utc).isoformat()
    with connection:
        cursor = connection.execute(
            """
            INSERT INTO batches (name, start_date, initial_count, target_weight_g, status, created_at)
            VALUES (?, ?, ?, ?, 'active', ?)
            """,
            (
                batch.name,
                batch.start_date.isoformat(),
                batch.initial_count,
                batch.target_weight_g,
                created_at,
            ),
        )
        batch_id = cursor.lastrowid
        if batch_id is None:
            raise RuntimeError("Impossible de créer le lot.")

        reminder_rows = [
            (
                batch_id,
                draft.due_date.isoformat(),
                draft.category,
                draft.title,
                draft.details,
            )
            for draft in generate_reminder_drafts(batch.start_date)
        ]
        connection.executemany(
            """
            INSERT INTO reminders (batch_id, due_date, category, title, details)
            VALUES (?, ?, ?, ?, ?)
            """,
            reminder_rows,
        )
        row = connection.execute("SELECT * FROM batches WHERE id = ?", (batch_id,)).fetchone()

    if row is None:
        raise RuntimeError("Le lot créé est introuvable.")
    return _row_to_dict(row)


def list_batches(connection: sqlite3.Connection) -> list[dict[str, object]]:
    """Return all batches, newest first."""
    rows = connection.execute("SELECT * FROM batches ORDER BY start_date DESC, id DESC").fetchall()
    return [_row_to_dict(row) for row in rows]


def get_batch_detail(connection: sqlite3.Connection, batch_id: int) -> dict[str, object] | None:
    """Return one batch together with all of its reminders."""
    batch_row = connection.execute("SELECT * FROM batches WHERE id = ?", (batch_id,)).fetchone()
    if batch_row is None:
        return None
    reminder_rows = connection.execute(
        "SELECT * FROM reminders WHERE batch_id = ? ORDER BY due_date, id", (batch_id,)
    ).fetchall()
    batch = _row_to_dict(batch_row)
    batch["reminders"] = [_row_to_dict(row) for row in reminder_rows]
    return batch


def update_reminder(
    connection: sqlite3.Connection, reminder_id: int, update: ReminderUpdate
) -> dict[str, object] | None:
    """Update the editable due date and/or completion state of a reminder."""
    changes: list[str] = []
    values: list[object] = []
    if update.due_date is not None:
        changes.append("due_date = ?")
        values.append(update.due_date.isoformat())
    if update.done is not None:
        changes.extend(["done = ?", "done_at = ?"])
        values.extend(
            [int(update.done), datetime.now(timezone.utc).isoformat() if update.done else None]
        )
    if not changes:
        return None

    values.append(reminder_id)
    with connection:
        cursor = connection.execute(
            f"UPDATE reminders SET {', '.join(changes)} WHERE id = ?", values
        )
    if cursor.rowcount == 0:
        return None
    row = connection.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,)).fetchone()
    return _row_to_dict(row) if row is not None else None
