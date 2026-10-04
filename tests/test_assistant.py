import json
from collections.abc import Callable
from datetime import date
from pathlib import Path

import httpx
import pytest

from app.schemas import ParsedEntry
from app.services.assistant import AssistantBadOutput, AssistantUnavailable, parse_entry
from app.services.ollama_client import chat_json


def mock_requester(handler: Callable[[httpx.Request], httpx.Response]) -> Callable[..., str]:
    """Create an injected Ollama requester backed by an in-memory transport."""
    transport = httpx.MockTransport(handler)

    def requester(system: str, user: str, schema: dict[str, object]) -> str:
        return chat_json(system, user, schema, transport=transport)

    return requester


def test_parse_entry_returns_valid_proposal_and_sends_ollama_json_format() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.url.path == "/api/chat"
        assert payload["stream"] is False
        assert payload["options"]["temperature"] == 0
        assert "properties" in payload["format"]
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": json.dumps({"dead_count": 2, "feed_kg": 4, "unclear": []})
                }
            },
        )

    entry = parse_entry(
        "ce matin 2 morts et 4 kg d'aliment", date(2026, 6, 10), mock_requester(handler)
    )

    assert entry == ParsedEntry(log_date=date(2026, 6, 10), dead_count=2, feed_kg=4)


def test_invalid_model_json_retries_once_then_fails() -> None:
    attempts = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(200, json={"message": {"content": "pas du JSON"}})

    with pytest.raises(AssistantBadOutput):
        parse_entry("1 mort", date(2026, 6, 10), mock_requester(handler))

    assert attempts == 2


def test_invalid_model_schema_retries_once_then_fails() -> None:
    attempts = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(
            200, json={"message": {"content": json.dumps({"unknown_field": 1})}}
        )

    with pytest.raises(AssistantBadOutput):
        parse_entry("1 mort", date(2026, 6, 10), mock_requester(handler))

    assert attempts == 2


@pytest.mark.parametrize("exception", [httpx.ConnectError("offline"), httpx.ReadTimeout("slow")])
def test_ollama_connection_errors_are_friendly(exception: httpx.HTTPError) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise exception

    with pytest.raises(AssistantUnavailable):
        parse_entry("1 mort", date(2026, 6, 10), mock_requester(handler))


def test_unsafe_numbers_are_moved_to_unclear() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        content = {
            "dead_count": -1,
            "feed_kg": 101,
            "sample_size": -2,
            "average_weight_g": 100001,
            "unclear": [],
        }
        return httpx.Response(200, json={"message": {"content": json.dumps(content)}})

    entry = parse_entry("saisie étrange", date(2026, 6, 10), mock_requester(handler))

    assert entry.log_date == date(2026, 6, 10)
    assert entry.dead_count is None
    assert entry.feed_kg is None
    assert entry.sample_size is None
    assert entry.average_weight_g is None
    assert entry.unclear == [
        "nombre de morts à vérifier",
        "quantité d'aliment à vérifier",
        "taille de l'échantillon à vérifier",
        "poids moyen à vérifier",
    ]


def test_documented_examples_match_the_entry_schema() -> None:
    examples_path = Path("docs/parsing_examples.json")
    examples = json.loads(examples_path.read_text(encoding="utf-8"))

    assert len(examples) >= 12
    for example in examples:
        entry = ParsedEntry.model_validate(example["expected"])
        assert entry.log_date is not None
