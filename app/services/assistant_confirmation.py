"""Confirmation-only persistence for local assistant proposals."""

import sqlite3
from datetime import date

from pydantic import ValidationError

from app.schemas import DailyLogCreate, DailyLogUpdate, ParsedEntry, WeighInCreate
from app.services.logs import (
    BatchNotFoundError,
    add_daily_log,
    add_weigh_in,
    current_utc_date,
    update_daily_log,
)


class AssistantConfirmationError(ValueError):
    """Raised when a proposal cannot create a complete manual record."""


def get_log_for_date(
    connection: sqlite3.Connection, batch_id: int, log_date: date
) -> dict[str, object] | None:
    """Return the existing log for one batch date, when present."""
    row = connection.execute(
        "SELECT * FROM daily_logs WHERE batch_id = ? AND log_date = ?",
        (batch_id, log_date.isoformat()),
    ).fetchone()
    return dict(row) if row is not None else None


def _require_batch(connection: sqlite3.Connection, batch_id: int) -> None:
    """Ensure the selected batch exists before confirmation work begins."""
    row = connection.execute("SELECT id FROM batches WHERE id = ?", (batch_id,)).fetchone()
    if row is None:
        raise BatchNotFoundError("Lot introuvable.")


def _has_log_values(proposal: ParsedEntry) -> bool:
    """Return whether a proposal includes a daily-log value beyond its date."""
    return any(value is not None for value in (proposal.dead_count, proposal.feed_kg, proposal.note))


def _has_weigh_in_values(proposal: ParsedEntry) -> bool:
    """Return whether a proposal includes either half of a weigh-in."""
    return proposal.sample_size is not None or proposal.average_weight_g is not None


def _replace_daily_log(
    connection: sqlite3.Connection, existing_log: dict[str, object], proposal: ParsedEntry
) -> dict[str, object] | None:
    """Update only proposal fields that are present, preserving the rest of a log."""
    fields: dict[str, object] = {}
    for field_name in ("dead_count", "feed_kg", "note"):
        value = getattr(proposal, field_name)
        if value is not None:
            fields[field_name] = value
    if not fields:
        return None
    try:
        update = DailyLogUpdate.model_validate(fields)
    except ValidationError as error:
        raise AssistantConfirmationError("Vérifiez les valeurs du journal.") from error
    return update_daily_log(connection, int(existing_log["id"]), update)


def confirm_entry(
    connection: sqlite3.Connection,
    batch_id: int,
    proposal: ParsedEntry,
    mode: str,
) -> dict[str, object | None]:
    """Save user-confirmed proposal fields through the regular log services."""
    _require_batch(connection, batch_id)
    log_date = proposal.log_date or current_utc_date()
    has_log_values = _has_log_values(proposal)
    has_weigh_in_values = _has_weigh_in_values(proposal)
    if not has_log_values and not has_weigh_in_values:
        raise AssistantConfirmationError("Ajoutez au moins un journal ou une pesée.")

    weigh_in_input: WeighInCreate | None = None
    if has_weigh_in_values:
        if proposal.sample_size is None or proposal.average_weight_g is None:
            raise AssistantConfirmationError(
                "Pour une pesée, indiquez la taille de l'échantillon et le poids moyen."
            )
        try:
            weigh_in_input = WeighInCreate(
                weigh_date=log_date,
                sample_size=proposal.sample_size,
                average_weight_g=proposal.average_weight_g,
            )
        except ValidationError as error:
            raise AssistantConfirmationError("Vérifiez les valeurs de la pesée.") from error

    daily_log: dict[str, object] | None = None
    if has_log_values:
        existing_log = get_log_for_date(connection, batch_id, log_date)
        if mode == "replace":
            if existing_log is None:
                raise AssistantConfirmationError("Aucun journal à remplacer pour cette date.")
            daily_log = _replace_daily_log(connection, existing_log, proposal)
        else:
            try:
                daily_log_input = DailyLogCreate(
                    log_date=log_date,
                    dead_count=proposal.dead_count or 0,
                    feed_kg=proposal.feed_kg or 0,
                    note=proposal.note,
                )
            except ValidationError as error:
                raise AssistantConfirmationError("Vérifiez les valeurs du journal.") from error
            daily_log = add_daily_log(connection, batch_id, daily_log_input)

    weigh_in: dict[str, object] | None = None
    if weigh_in_input is not None:
        weigh_in = add_weigh_in(connection, batch_id, weigh_in_input)
    return {"daily_log": daily_log, "weigh_in": weigh_in}
