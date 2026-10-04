"""Weekly facts and safe local-AI wording with a deterministic fallback."""

import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.config import PROJECT_DIR
from app.services.ollama_client import (
    AssistantBadOutput,
    AssistantUnavailable,
    chat_text,
)
from app.services.stats import TargetAnchor, latest_weight_vs_target

PROMPT_PATH = PROJECT_DIR / "app" / "prompts" / "weekly_summary.md"
ChatRequester = Callable[[str, str], str]
NUMBER_PATTERN = re.compile(r"(?<![\w])[-+]?\d+(?:[.,]\d+)?")
FORBIDDEN_TERMS = (
    "diagnostic",
    "diagnostiquer",
    "maladie",
    "infection",
    "cause",
    "causé",
    "dû",
    "recommand",
    "antibiotique",
    "médicament",
    "dose",
    "traitement",
    "vaccin",
    "amoxicilline",
    "doxycycline",
    "enrofloxacine",
    "oxytétracycline",
    "tylosine",
)


@dataclass(frozen=True)
class SummaryResult:
    """A summary and the reliable source that produced it."""

    text: str
    source: str


def _round(value: float) -> float:
    """Keep summary facts compact while retaining meaningful precision."""
    return round(value, 2)


def build_summary_facts(
    batch: Mapping[str, object],
    daily_logs: Sequence[Mapping[str, object]],
    weigh_ins: Sequence[Mapping[str, object]],
    reminders: Sequence[Mapping[str, object]],
    alerts: Sequence[Mapping[str, object]],
    *,
    today: date,
    anchors: Sequence[TargetAnchor],
) -> dict[str, object]:
    """Gather the stored numbers relevant to the latest seven calendar days."""
    week_start = today - timedelta(days=6)
    week_logs = [
        log
        for log in daily_logs
        if week_start <= date.fromisoformat(str(log["log_date"])) <= today
    ]
    dead_this_week = sum(int(log["dead_count"]) for log in week_logs)
    feed_this_week_kg = sum(float(log["feed_kg"]) for log in week_logs)
    birds_alive = int(batch["initial_count"]) - sum(
        int(log["dead_count"])
        for log in daily_logs
        if date.fromisoformat(str(log["log_date"])) <= today
    )
    latest_weight = latest_weight_vs_target(batch, weigh_ins, anchors)
    overdue_reminders = sum(
        not bool(reminder["done"])
        and date.fromisoformat(str(reminder["due_date"])) < today
        for reminder in reminders
    )
    return {
        "dead_this_week": dead_this_week,
        "mortality_this_week_percent": _round(dead_this_week / int(batch["initial_count"]) * 100),
        "feed_this_week_kg": _round(feed_this_week_kg),
        "feed_per_bird_kg": _round(feed_this_week_kg / birds_alive) if birds_alive else None,
        "birds_alive": birds_alive,
        "latest_weight": latest_weight,
        "overdue_reminders": overdue_reminders,
        "alerts": list(alerts),
    }


def _number(value: object) -> str:
    """Format a numeric fact compactly in French-facing template text."""
    return f"{float(value):g}".replace(".", ",")


def render_template_summary(facts: Mapping[str, object]) -> str:
    """Return a useful French summary without contacting the local model."""
    sentences = [
        (
            "Cette semaine : "
            f"{_number(facts['dead_this_week'])} morts "
            f"({_number(facts['mortality_this_week_percent'])} % du lot initial) et "
            f"{_number(facts['feed_this_week_kg'])} kg d'aliment."
        )
    ]
    feed_per_bird = facts["feed_per_bird_kg"]
    if feed_per_bird is not None:
        sentences.append(f"Cela représente {_number(feed_per_bird)} kg par oiseau vivant.")
    latest_weight = facts["latest_weight"]
    if isinstance(latest_weight, Mapping) and latest_weight["average_weight_g"] is not None:
        sentences.append(
            "Dernière pesée : "
            f"{_number(latest_weight['average_weight_g'])} g pour une cible de "
            f"{_number(latest_weight['target_weight_g'])} g "
            f"(écart {_number(latest_weight['gap_percent'])} %)."
        )
    else:
        sentences.append("Aucune pesée pour le moment.")
    overdue_reminders = int(facts["overdue_reminders"])
    if overdue_reminders:
        sentences.append(f"{overdue_reminders} rappel(s) sont en retard.")
    return " ".join(sentences)


def _allowed_numbers(facts: object) -> set[Decimal]:
    """Collect numeric values recursively so generated prose cannot invent one."""
    if isinstance(facts, Mapping):
        values = facts.values()
    elif isinstance(facts, Sequence) and not isinstance(facts, (str, bytes)):
        values = facts
    else:
        values = ()
    allowed: set[Decimal] = set()
    for value in values:
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            allowed.add(Decimal(str(value)).normalize())
        else:
            allowed.update(_allowed_numbers(value))
    return allowed


def _output_is_safe(text: str, facts: Mapping[str, object]) -> bool:
    """Reject output with new numbers or prohibited health-treatment language."""
    normalized = text.lower()
    if not text.strip() or any(term in normalized for term in FORBIDDEN_TERMS):
        return False
    allowed_numbers = _allowed_numbers(facts)
    try:
        output_numbers = {
            Decimal(match.group().replace(",", ".")).normalize()
            for match in NUMBER_PATTERN.finditer(text)
        }
    except InvalidOperation:
        return False
    return output_numbers <= allowed_numbers


def _system_prompt(path: Path = PROMPT_PATH) -> str:
    """Load the dedicated short prompt for weekly summary wording."""
    return path.read_text(encoding="utf-8")


def render_ai_summary(
    facts: Mapping[str, object], request_chat: ChatRequester = chat_text
) -> SummaryResult:
    """Use Ollama only for wording, reverting safely to the template on any issue."""
    fallback = SummaryResult(text=render_template_summary(facts), source="template")
    try:
        text = request_chat(_system_prompt(), json.dumps(facts, ensure_ascii=False))
    except (AssistantUnavailable, AssistantBadOutput):
        return fallback
    if not _output_is_safe(text, facts):
        return fallback
    return SummaryResult(text=text.strip(), source="ai")
