"""Small local HTTP client for Ollama's JSON chat endpoint."""

from collections.abc import Mapping
from typing import Any

import httpx

from app.config import OLLAMA_MODEL, OLLAMA_TIMEOUT_S, OLLAMA_URL


class AssistantUnavailable(RuntimeError):
    """Raised when the configured local Ollama model cannot be used."""


class AssistantBadOutput(ValueError):
    """Raised when Ollama returns a response without usable JSON content."""


def chat_json(
    system: str,
    user: str,
    schema: Mapping[str, Any],
    *,
    transport: httpx.BaseTransport | None = None,
) -> str:
    """Ask the local Ollama model for one JSON response without streaming."""
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "format": schema,
        "stream": False,
        "options": {"temperature": 0},
    }
    try:
        with httpx.Client(timeout=OLLAMA_TIMEOUT_S, transport=transport) as client:
            response = client.post(f"{OLLAMA_URL}/api/chat", json=payload)
            response.raise_for_status()
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.HTTPStatusError) as error:
        raise AssistantUnavailable("Le modèle local Ollama est indisponible.") from error
    except httpx.HTTPError as error:
        raise AssistantUnavailable("Le modèle local Ollama est indisponible.") from error

    try:
        response_body = response.json()
        content = response_body["message"]["content"]
    except (KeyError, TypeError, ValueError) as error:
        raise AssistantBadOutput("La réponse du modèle local est invalide.") from error
    if not isinstance(content, str):
        raise AssistantBadOutput("La réponse du modèle local est invalide.")
    return content
