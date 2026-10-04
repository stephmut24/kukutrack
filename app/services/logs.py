"""Daily log and weigh-in business rules."""

import sqlite3
from datetime import date, datetime, timezone

from app.schemas import DailyLogCreate, DailyLogUpdate, WeighInCreate


class BatchNotFoundError(ValueError):
    """Raised when a batch does not exist."""


class LogNotFoundError(ValueError):
    """Raised when a daily log does not exist."""


class WeighInNotFoundError(ValueError):
    """Raised when a weigh-in does not exist."""


class LogValidationError(ValueError):
    """Raised when a log or weigh-in violates a business rule."""


def current_utc_date() -> date:
    """Return today's UTC date for date-only farm records."""
    return datetime.now(timezone.utc).date()


def _row_to_dict(row: sqlite3.Row) -> dict[str, object]:
    """Convert a SQLite row into a response-compatible dictionary."""
    return dict(row)


def _get_batch(connection: sqlite3.Connection, batch_id: int) -> sqlite3.Row:
    batch = connection.execute("SELECT * FROM batches WHERE id = ?", (batch_id,)).fetchone()
    if batch is None:
        raise BatchNotFoundError("Lot introuvable.")
    return batch


def _require_active_batch(batch: sqlite3.Row) -> None:
    """Reject new records for a closed batch."""
    if batch["status"] != "active":
        raise LogValidationError("Ce lot est fermé.")


def _validate_record_date(record_date: date, batch: sqlite3.Row) -> None:
    """Ensure a record date is within the batch's valid daily period."""
    start_date = date.fromisoformat(batch["start_date"])
    if record_date < start_date:
        raise LogValidationError("La date ne peut pas être avant le début du lot.")
    if record_date > current_utc_date():
        raise LogValidationError("La date ne peut pas être dans le futur.")


def _total_dead(connection: sqlite3.Connection, batch_id: int, before_or_on: date | None) -> int:
    """Return mortality for a batch, optionally through a specific date."""
    if before_or_on is None:
        row = connection.execute(
            "SELECT COALESCE(SUM(dead_count), 0) AS total FROM daily_logs WHERE batch_id = ?",
            (batch_id,),
        ).fetchone()
    else:
        row = connection.execute(
            """
            SELECT COALESCE(SUM(dead_count), 0) AS total
            FROM daily_logs
            WHERE batch_id = ? AND log_date <= ?
            """,
            (batch_id, before_or_on.isoformat()),
        ).fetchone()
    return int(row["total"])


def birds_alive(
    connection: sqlite3.Connection, batch_id: int, as_of_date: date | None = None
) -> int:
    """Return initial birds minus mortality recorded through the selected date."""
    batch = _get_batch(connection, batch_id)
    cutoff_date = as_of_date or current_utc_date()
    return int(batch["initial_count"]) - _total_dead(connection, batch_id, cutoff_date)


def _validate_dead_count(
    connection: sqlite3.Connection,
    batch: sqlite3.Row,
    log_date: date,
    dead_count: int,
    excluded_log_id: int | None = None,
) -> None:
    """Check that mortality fits the birds alive and preserves later records."""
    if dead_count < 0:
        raise LogValidationError("Le nombre de morts ne peut pas être négatif.")

    values: list[object] = [batch["id"], log_date.isoformat()]
    query = "SELECT COALESCE(SUM(dead_count), 0) AS total FROM daily_logs WHERE batch_id = ? AND log_date < ?"
    if excluded_log_id is not None:
        query += " AND id != ?"
        values.append(excluded_log_id)
    before_row = connection.execute(query, values).fetchone()
    alive_before_date = int(batch["initial_count"]) - int(before_row["total"])
    if dead_count > alive_before_date:
        raise LogValidationError("Le nombre de morts dépasse les oiseaux vivants.")

    all_values: list[object] = [batch["id"]]
    total_query = "SELECT COALESCE(SUM(dead_count), 0) AS total FROM daily_logs WHERE batch_id = ?"
    if excluded_log_id is not None:
        total_query += " AND id != ?"
        all_values.append(excluded_log_id)
    total_row = connection.execute(total_query, all_values).fetchone()
    if int(total_row["total"]) + dead_count > int(batch["initial_count"]):
        raise LogValidationError("Le nombre de morts dépasse les oiseaux vivants.")


def _validate_feed_kg(feed_kg: float) -> None:
    """Reject negative feed quantities even when called outside the API."""
    if feed_kg < 0:
        raise LogValidationError("La quantité d'aliment ne peut pas être négative.")


def add_daily_log(
    connection: sqlite3.Connection, batch_id: int, daily_log: DailyLogCreate
) -> dict[str, object]:
    """Add the only permitted daily log for a date in a batch."""
    batch = _get_batch(connection, batch_id)
    _require_active_batch(batch)
    _validate_record_date(daily_log.log_date, batch)
    _validate_feed_kg(daily_log.feed_kg)
    duplicate = connection.execute(
        "SELECT id FROM daily_logs WHERE batch_id = ? AND log_date = ?",
        (batch_id, daily_log.log_date.isoformat()),
    ).fetchone()
    if duplicate is not None:
        raise LogValidationError("Un journal existe déjà pour cette date. Modifiez-le.")
    _validate_dead_count(connection, batch, daily_log.log_date, daily_log.dead_count)

    with connection:
        cursor = connection.execute(
            """
            INSERT INTO daily_logs (batch_id, log_date, dead_count, feed_kg, water_note, note)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                batch_id,
                daily_log.log_date.isoformat(),
                daily_log.dead_count,
                daily_log.feed_kg,
                daily_log.water_note,
                daily_log.note,
            ),
        )
    row = connection.execute("SELECT * FROM daily_logs WHERE id = ?", (cursor.lastrowid,)).fetchone()
    if row is None:
        raise RuntimeError("Le journal créé est introuvable.")
    return _row_to_dict(row)


def list_daily_logs(connection: sqlite3.Connection, batch_id: int) -> list[dict[str, object]]:
    """Return daily logs newest first for an existing batch."""
    _get_batch(connection, batch_id)
    rows = connection.execute(
        "SELECT * FROM daily_logs WHERE batch_id = ? ORDER BY log_date DESC, id DESC", (batch_id,)
    ).fetchall()
    return [_row_to_dict(row) for row in rows]


def update_daily_log(
    connection: sqlite3.Connection, log_id: int, update: DailyLogUpdate
) -> dict[str, object]:
    """Edit a daily log while applying the same rules as creation."""
    current = connection.execute("SELECT * FROM daily_logs WHERE id = ?", (log_id,)).fetchone()
    if current is None:
        raise LogNotFoundError("Journal introuvable.")
    batch = _get_batch(connection, int(current["batch_id"]))
    _require_active_batch(batch)
    if not update.model_fields_set:
        raise LogValidationError("Indiquez au moins une modification.")

    log_date = update.log_date or date.fromisoformat(current["log_date"])
    dead_count = update.dead_count if update.dead_count is not None else int(current["dead_count"])
    feed_kg = update.feed_kg if update.feed_kg is not None else float(current["feed_kg"])
    _validate_record_date(log_date, batch)
    _validate_feed_kg(feed_kg)

    duplicate = connection.execute(
        "SELECT id FROM daily_logs WHERE batch_id = ? AND log_date = ? AND id != ?",
        (batch["id"], log_date.isoformat(), log_id),
    ).fetchone()
    if duplicate is not None:
        raise LogValidationError("Un journal existe déjà pour cette date. Modifiez-le.")
    _validate_dead_count(connection, batch, log_date, dead_count, excluded_log_id=log_id)

    fields = {
        "log_date": log_date.isoformat(),
        "dead_count": dead_count,
        "feed_kg": feed_kg,
        "water_note": current["water_note"],
        "note": current["note"],
    }
    for field_name in ("water_note", "note"):
        if field_name in update.model_fields_set:
            fields[field_name] = getattr(update, field_name)
    with connection:
        connection.execute(
            """
            UPDATE daily_logs
            SET log_date = ?, dead_count = ?, feed_kg = ?, water_note = ?, note = ?
            WHERE id = ?
            """,
            (*fields.values(), log_id),
        )
    row = connection.execute("SELECT * FROM daily_logs WHERE id = ?", (log_id,)).fetchone()
    if row is None:
        raise LogNotFoundError("Journal introuvable.")
    return _row_to_dict(row)


def delete_daily_log(connection: sqlite3.Connection, log_id: int) -> None:
    """Delete an existing daily log."""
    with connection:
        cursor = connection.execute("DELETE FROM daily_logs WHERE id = ?", (log_id,))
    if cursor.rowcount == 0:
        raise LogNotFoundError("Journal introuvable.")


def add_weigh_in(
    connection: sqlite3.Connection, batch_id: int, weigh_in: WeighInCreate
) -> dict[str, object]:
    """Add a weigh-in to an active batch."""
    batch = _get_batch(connection, batch_id)
    _require_active_batch(batch)
    _validate_record_date(weigh_in.weigh_date, batch)
    if weigh_in.sample_size <= 0:
        raise LogValidationError("La taille de l'échantillon doit être supérieure à zéro.")
    if weigh_in.average_weight_g <= 0:
        raise LogValidationError("Le poids moyen doit être supérieur à zéro.")
    with connection:
        cursor = connection.execute(
            """
            INSERT INTO weigh_ins (batch_id, weigh_date, sample_size, average_weight_g)
            VALUES (?, ?, ?, ?)
            """,
            (
                batch_id,
                weigh_in.weigh_date.isoformat(),
                weigh_in.sample_size,
                weigh_in.average_weight_g,
            ),
        )
    row = connection.execute("SELECT * FROM weigh_ins WHERE id = ?", (cursor.lastrowid,)).fetchone()
    if row is None:
        raise RuntimeError("La pesée créée est introuvable.")
    return _row_to_dict(row)


def list_weigh_ins(connection: sqlite3.Connection, batch_id: int) -> list[dict[str, object]]:
    """Return weigh-ins newest first for an existing batch."""
    _get_batch(connection, batch_id)
    rows = connection.execute(
        "SELECT * FROM weigh_ins WHERE batch_id = ? ORDER BY weigh_date DESC, id DESC", (batch_id,)
    ).fetchall()
    return [_row_to_dict(row) for row in rows]


def delete_weigh_in(connection: sqlite3.Connection, weigh_in_id: int) -> None:
    """Delete an existing weigh-in."""
    with connection:
        cursor = connection.execute("DELETE FROM weigh_ins WHERE id = ?", (weigh_in_id,))
    if cursor.rowcount == 0:
        raise WeighInNotFoundError("Pesée introuvable.")


def summary_counts(connection: sqlite3.Connection, batch_id: int) -> dict[str, int]:
    """Return current birds alive, total mortality, and batch day number."""
    batch = _get_batch(connection, batch_id)
    start_date = date.fromisoformat(batch["start_date"])
    today = current_utc_date()
    day_number = max(0, (today - start_date).days + 1)
    total_dead = _total_dead(connection, batch_id, today)
    return {
        "birds_alive": birds_alive(connection, batch_id, today),
        "total_dead": total_dead,
        "day_number": day_number,
    }
