"""Local audio transcription with a lazily loaded faster-whisper model."""

import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.config import WHISPER_LANGUAGE, WHISPER_MAX_AUDIO_BYTES, WHISPER_MODEL

SUPPORTED_EXTENSIONS = {".aac", ".m4a", ".mp3", ".ogg", ".wav", ".webm"}
ModelLoader = Callable[..., Any]
_model: Any | None = None


class TranscriptionUnavailable(RuntimeError):
    """Raised when faster-whisper or its local model cannot be loaded."""


class UnsupportedAudioError(ValueError):
    """Raised when an upload is not an accepted audio file."""


class AudioTooLargeError(ValueError):
    """Raised when an audio upload exceeds the local safety limit."""


class TranscriptionError(ValueError):
    """Raised when an accepted audio file cannot be transcribed."""


def _load_model() -> Any:
    """Import faster-whisper only when speech recognition is first requested."""
    try:
        from faster_whisper import WhisperModel
    except ImportError as error:
        raise TranscriptionUnavailable(
            "La transcription locale n'est pas installée sur cet ordinateur."
        ) from error
    try:
        return WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    except Exception as error:
        raise TranscriptionUnavailable(
            "Le modèle de transcription est indisponible. Connectez l'ordinateur une fois "
            "pour le télécharger, puis réessayez."
        ) from error


def get_model(loader: ModelLoader = _load_model) -> Any:
    """Keep the local transcription model in memory after its first successful load."""
    global _model
    if _model is None:
        _model = loader()
    return _model


def _validated_suffix(filename: str, content_type: str) -> str:
    """Accept known audio MIME types or file extensions and return a safe suffix."""
    suffix = Path(filename).suffix.lower()
    if not content_type.startswith("audio/") and suffix not in SUPPORTED_EXTENSIONS:
        raise UnsupportedAudioError("Choisissez un fichier audio.")
    return suffix if suffix in SUPPORTED_EXTENSIONS else ".audio"


def _validate_audio(audio: bytes, filename: str, content_type: str) -> str:
    """Apply cheap request limits before loading the transcription model."""
    suffix = _validated_suffix(filename, content_type)
    if not audio:
        raise UnsupportedAudioError("Le fichier audio est vide.")
    if len(audio) > WHISPER_MAX_AUDIO_BYTES:
        raise AudioTooLargeError("Le fichier audio est trop volumineux.")
    return suffix


def transcribe_audio(audio: bytes, filename: str, content_type: str) -> str:
    """Transcribe one temporary local audio file and delete it after processing."""
    suffix = _validate_audio(audio, filename, content_type)
    descriptor, temporary_name = tempfile.mkstemp(prefix="kukutrack-audio-", suffix=suffix)
    audio_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as audio_file:
            audio_file.write(audio)
        segments, _ = get_model().transcribe(audio_path, language=WHISPER_LANGUAGE, beam_size=5)
        text = " ".join(segment.text.strip() for segment in segments).strip()
    except TranscriptionUnavailable:
        raise
    except Exception as error:
        raise TranscriptionError("La transcription de ce fichier audio est impossible.") from error
    finally:
        audio_path.unlink(missing_ok=True)
    if not text:
        raise TranscriptionError("Aucune parole n'a été reconnue dans cet audio.")
    return text
