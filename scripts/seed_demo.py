"""Create deterministic, clearly fake data for a KukuTrack demonstration."""

import argparse
import random
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from app.config import get_db_path
from app.db import get_connection, initialize_database
from app.schemas import BatchCreate, DailyLogCreate, ReminderUpdate, WeighInCreate
from app.services.batches import create_batch, update_reminder
from app.services.logs import add_daily_log, add_weigh_in, current_utc_date
from app.services.stats import load_target_curve, target_weight_for_day

DEMO_BATCH_NAME = "DEMO (fake data)"
DEMO_INITIAL_COUNT = 100
DEMO_TARGET_WEIGHT_G = 3000
DEMO_DAYS = 45
DEMO_RANDOM_SEED = 20261004


class DemoBatchExistsError(ValueError):
    """Raised when a demo batch is already present."""


def _demo_death_counts(randomizer: random.Random) -> list[int]:
    """Create 17 deaths, with a greater concentration during the first week."""
    death_counts = [0] * DEMO_DAYS
    for day_offset in range(7):
        death_counts[day_offset] = 1
    death_counts[randomizer.randrange(7)] += 1
    for day_offset in randomizer.sample(range(7, DEMO_DAYS), 9):
        death_counts[day_offset] += 1
    return death_counts


def _add_demo_logs(
    connection: sqlite3.Connection, batch_id: int, start_date: date, randomizer: random.Random
) -> None:
    """Add one validated fake log for every completed day."""
    for day_offset, dead_count in enumerate(_demo_death_counts(randomizer)):
        log_date = start_date + timedelta(days=day_offset)
        feed_kg = round(0.7 + day_offset * 0.17 + randomizer.uniform(-0.08, 0.08), 2)
        note = "Observation demo data" if day_offset % 9 == 0 else None
        add_daily_log(
            connection,
            batch_id,
            DailyLogCreate(
                log_date=log_date,
                dead_count=dead_count,
                feed_kg=feed_kg,
                note=note,
            ),
        )


def _add_demo_weigh_ins(
    connection: sqlite3.Connection, batch_id: int, start_date: date, randomizer: random.Random
) -> None:
    """Add weekly validated fake weigh-ins with visible variation from the target."""
    anchors = load_target_curve()
    factors = (0.98, 0.95, 0.91, 0.94, 0.9, 0.93, 0.92)
    for day_offset, factor in zip((6, 13, 20, 27, 34, 41, 44), factors, strict=True):
        target_weight = target_weight_for_day(day_offset + 1, DEMO_TARGET_WEIGHT_G, anchors)
        average_weight = round(target_weight * (factor + randomizer.uniform(-0.01, 0.01)))
        add_weigh_in(
            connection,
            batch_id,
            WeighInCreate(
                weigh_date=start_date + timedelta(days=day_offset),
                sample_size=randomizer.randint(8, 12),
                average_weight_g=average_weight,
            ),
        )


def _mark_demo_reminders(connection: sqlite3.Connection, batch_id: int, today: date) -> None:
    """Complete past demo reminders except for exactly two overdue reminders."""
    reminders = connection.execute(
        """
        SELECT id FROM reminders
        WHERE batch_id = ? AND due_date < ?
        ORDER BY due_date, id
        """,
        (batch_id, today.isoformat()),
    ).fetchall()
    for reminder in reminders[:-2]:
        update_reminder(connection, int(reminder["id"]), ReminderUpdate(done=True))


def seed_demo(database_path: Path, reset: bool = False) -> int:
    """Create the demo batch, or replace only it when reset is requested."""
    initialize_database(database_path)
    today = current_utc_date()
    start_date = today - timedelta(days=DEMO_DAYS)
    randomizer = random.Random(DEMO_RANDOM_SEED)

    with get_connection(database_path) as connection:
        existing = connection.execute(
            "SELECT id FROM batches WHERE name = ?", (DEMO_BATCH_NAME,)
        ).fetchall()
        if existing and not reset:
            raise DemoBatchExistsError("Le lot DEMO existe déjà. Utilisez --reset pour le recréer.")
        if reset:
            with connection:
                connection.execute("DELETE FROM batches WHERE name = ?", (DEMO_BATCH_NAME,))

        batch = create_batch(
            connection,
            BatchCreate(
                name=DEMO_BATCH_NAME,
                start_date=start_date,
                initial_count=DEMO_INITIAL_COUNT,
                target_weight_g=DEMO_TARGET_WEIGHT_G,
            ),
        )
        batch_id = int(batch["id"])
        _add_demo_logs(connection, batch_id, start_date, randomizer)
        _add_demo_weigh_ins(connection, batch_id, start_date, randomizer)
        _mark_demo_reminders(connection, batch_id, today)
    return batch_id


def parse_arguments() -> argparse.Namespace:
    """Parse command-line options for the demonstration seed."""
    parser = argparse.ArgumentParser(description="Crée des données DEMO fictives pour KukuTrack.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="supprime uniquement le lot DEMO existant avant de le recréer",
    )
    parser.add_argument("--db", type=Path, help="chemin vers le fichier SQLite à utiliser")
    return parser.parse_args()


def main() -> None:
    """Run the command-line seed operation."""
    arguments = parse_arguments()
    database_path = arguments.db or get_db_path()
    try:
        batch_id = seed_demo(database_path, reset=arguments.reset)
    except DemoBatchExistsError as error:
        raise SystemExit(str(error)) from error
    print(f"Lot DEMO fictif créé (id {batch_id}) dans {database_path}.")


if __name__ == "__main__":
    main()
