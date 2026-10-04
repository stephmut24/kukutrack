"""Tests for the optional local audio transcription feature."""

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import assistant as assistant_router
from app.services import transcribe


def test_transcribe_audio_uses_a_temporary_file_and_deletes_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The service streams a local file to the model and removes it afterwards."""
    temporary_path: Path | None = None

    class FakeModel:
        def transcribe(
            self, path: Path, *, language: str, beam_size: int
        ) -> tuple[list[SimpleNamespace], object]:
            nonlocal temporary_path
            temporary_path = path
            assert path.exists()
            assert language == "fr"
            assert beam_size == 5
            return [SimpleNamespace(text=" 2 morts "), SimpleNamespace(text=" et 4 kg ")], object()

    monkeypatch.setattr(transcribe, "get_model", lambda: FakeModel())

    result = transcribe.transcribe_audio(b"audio", "message.webm", "audio/webm")

    assert result == "2 morts et 4 kg"
    assert temporary_path is not None
    assert not temporary_path.exists()


def test_transcribe_audio_rejects_invalid_and_oversized_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cheap validation happens before a model is loaded."""
    with pytest.raises(transcribe.UnsupportedAudioError):
        transcribe.transcribe_audio(b"text", "notes.txt", "text/plain")

    monkeypatch.setattr(transcribe, "WHISPER_MAX_AUDIO_BYTES", 2)
    with pytest.raises(transcribe.AudioTooLargeError):
        transcribe.transcribe_audio(b"too large", "message.wav", "audio/wav")


def test_transcription_endpoint_returns_text_without_writing_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Audio transcription only fills a proposal and never touches farm records."""
    database_path = tmp_path / "test.db"
    monkeypatch.setenv("KUKUTRACK_DB", str(database_path))
    monkeypatch.setattr(
        assistant_router,
        "transcribe_audio",
        lambda _audio, _filename, _content_type: "2 morts et 4 kg d'aliment",
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/assistant/transcribe",
            content=b"fake audio",
            headers={"content-type": "audio/webm", "x-audio-filename": "message.webm"},
        )

    with sqlite3.connect(database_path) as connection:
        batch_count = connection.execute("SELECT COUNT(*) FROM batches").fetchone()[0]
        log_count = connection.execute("SELECT COUNT(*) FROM daily_logs").fetchone()[0]

    assert response.status_code == 200
    assert response.json() == {"text": "2 morts et 4 kg d'aliment"}
    assert batch_count == 0
    assert log_count == 0


def test_transcription_endpoint_rejects_non_audio_and_oversized_uploads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The endpoint exposes short, friendly validation errors."""
    monkeypatch.setenv("KUKUTRACK_DB", str(tmp_path / "test.db"))
    with TestClient(app) as client:
        non_audio = client.post(
            "/api/assistant/transcribe",
            content=b"not audio",
            headers={"content-type": "text/plain", "x-audio-filename": "notes.txt"},
        )
        monkeypatch.setattr(transcribe, "WHISPER_MAX_AUDIO_BYTES", 2)
        oversized = client.post(
            "/api/assistant/transcribe",
            content=b"too large",
            headers={"content-type": "audio/wav", "x-audio-filename": "message.wav"},
        )

    assert non_audio.status_code == 422
    assert "fichier audio" in non_audio.json()["detail"]
    assert oversized.status_code == 422
    assert "volumineux" in oversized.json()["detail"]


def test_transcription_endpoint_reports_an_unavailable_local_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing local model never breaks the manual assistant flow."""
    monkeypatch.setenv("KUKUTRACK_DB", str(tmp_path / "test.db"))

    def unavailable(_audio: bytes, _filename: str, _content_type: str) -> str:
        raise transcribe.TranscriptionUnavailable("Modèle indisponible.")

    monkeypatch.setattr(assistant_router, "transcribe_audio", unavailable)
    with TestClient(app) as client:
        response = client.post(
            "/api/assistant/transcribe",
            content=b"audio",
            headers={"content-type": "audio/wav", "x-audio-filename": "message.wav"},
        )

    assert response.status_code == 503
    assert response.json()["detail"] == "Modèle indisponible."
