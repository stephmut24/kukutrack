"""Small, read-only checks for the local app dependencies."""

import sqlite3
from collections.abc import Callable

import httpx

from app.config import OLLAMA_MODEL, OLLAMA_TIMEOUT_S, OLLAMA_URL
from app.db import get_connection

OllamaRequester = Callable[[], bool]


def ollama_is_available(
    *, model: str = OLLAMA_MODEL, transport: httpx.BaseTransport | None = None
) -> bool:
    """Return whether the configured local model can be found by Ollama."""
    if model == "SET_MODEL_NAME_FROM_OLLAMA_LIST":
        return False
    try:
        with httpx.Client(timeout=OLLAMA_TIMEOUT_S, transport=transport) as client:
            response = client.get(f"{OLLAMA_URL}/api/tags")
            response.raise_for_status()
        models = response.json().get("models", [])
    except (httpx.HTTPError, TypeError, ValueError):
        return False
    return any(isinstance(item, dict) and item.get("name") == model for item in models)


def database_is_available() -> bool:
    """Return whether the local SQLite database accepts a harmless query."""
    try:
        with get_connection() as connection:
            connection.execute("SELECT 1").fetchone()
    except sqlite3.Error:
        return False
    return True


def get_system_status(request_ollama: OllamaRequester = ollama_is_available) -> dict[str, str]:
    """Return simple health flags without making the app depend on Ollama."""
    return {
        "server": "ok",
        "database": "ok" if database_is_available() else "unavailable",
        "assistant": "available" if request_ollama() else "unavailable",
    }
