"""Smoke tests for the separate static application pages."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.mark.parametrize(
    ("path", "script"),
    [
        ("/", "/js/welcome.js"),
        ("/lots", "/js/home.js"),
        ("/batch.html?id=1", "/js/dashboard.js"),
        ("/journal.html?id=1", "/js/journal.js"),
    ],
)
def test_static_pages_are_served(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str, script: str
) -> None:
    """Each user-facing screen has its own URL and targeted JavaScript module."""
    monkeypatch.setenv("KUKUTRACK_DB", str(tmp_path / "test.db"))

    with TestClient(app) as client:
        response = client.get(path)

    assert response.status_code == 200
    assert script in response.text
    assert 'href="/style.css"' in response.text
    assert "data-lot-navigation" in response.text
