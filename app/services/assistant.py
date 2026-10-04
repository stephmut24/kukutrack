"""Parse local-Ollama proposals without ever writing to the database."""

import json
import re
from collections.abc import Callable, Mapping
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.config import (
    OLLAMA_MAX_AVERAGE_WEIGHT_G,
    OLLAMA_MAX_DEAD_COUNT,
    OLLAMA_MAX_FEED_KG,
    OLLAMA_MAX_SAMPLE_SIZE,
    PROJECT_DIR,
)
from app.schemas import ParsedEntry
from app.services.ollama_client import (
    AssistantBadOutput,
    AssistantUnavailable,
    chat_json,
)

PROMPT_PATH = PROJECT_DIR / "app" / "prompts" / "parse_entry.md"
ChatRequester = Callable[[str, str, Mapping[str, Any]], str]


def load_system_prompt(path: Path = PROMPT_PATH) -> str:
    """Read the short local-model system prompt."""
    return path.read_text(encoding="utf-8")


def _relative_date(text: str, today: date) -> date | None:
    """Resolve common French relative date words in deterministic application code."""
    normalized = text.lower()
    if re.search(r"\bavant[- ]hier\b", normalized):
        return today - timedelta(days=2)
    if re.search(r"\bhier\b", normalized):
        return today - timedelta(days=1)
    if re.search(r"\b(aujourd['’]hui|ce matin|ce soir)\b", normalized):
        return today
    return None


def _system_message(today: date) -> str:
    """Append the current date so the model can format explicit dates consistently."""
    return f"{load_system_prompt()}\n\nCurrent application date: {today.isoformat()}."


def _sanitize_entry(entry: ParsedEntry, today: date, text: str) -> ParsedEntry:
    """Move unsafe numbers to unclear while preserving valid parsed fields."""
    values = entry.model_dump()
    unclear = list(entry.unclear)
    values["log_date"] = _relative_date(text, today) or entry.log_date or today
    limits = {
        "dead_count": OLLAMA_MAX_DEAD_COUNT,
        "feed_kg": OLLAMA_MAX_FEED_KG,
        "sample_size": OLLAMA_MAX_SAMPLE_SIZE,
        "average_weight_g": OLLAMA_MAX_AVERAGE_WEIGHT_G,
    }
    labels = {
        "dead_count": "nombre de morts",
        "feed_kg": "quantité d'aliment",
        "sample_size": "taille de l'échantillon",
        "average_weight_g": "poids moyen",
    }
    for field_name, limit in limits.items():
        value = values[field_name]
        if value is not None and (value < 0 or value > limit):
            values[field_name] = None
            unclear.append(f"{labels[field_name]} à vérifier")
    values["unclear"] = unclear
    return ParsedEntry.model_validate(values)


def parse_entry(
    text: str, today: date, request_chat: ChatRequester = chat_json
) -> ParsedEntry:
    """Return a validated local-AI proposal, retrying once after bad model output."""
    if not text.strip():
        raise AssistantBadOutput("La phrase à analyser est vide.")

    for attempt in range(2):
        try:
            content = request_chat(_system_message(today), text, ParsedEntry.model_json_schema())
            raw_entry = json.loads(content)
            if not isinstance(raw_entry, dict):
                raise AssistantBadOutput("La réponse du modèle local est invalide.")
            entry = ParsedEntry.model_validate(raw_entry)
            return _sanitize_entry(entry, today, text)
        except AssistantUnavailable:
            raise
        except (AssistantBadOutput, ValidationError, json.JSONDecodeError, TypeError) as error:
            if attempt == 1:
                raise AssistantBadOutput("Le modèle n'a pas produit une saisie utilisable.") from error
    raise AssistantBadOutput("Le modèle n'a pas produit une saisie utilisable.")
