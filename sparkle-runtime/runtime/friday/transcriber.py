"""
Friday — Audio transcription via Groq Whisper.
Handles OGG (WhatsApp format) and other common audio formats.
"""
from __future__ import annotations

import httpx
from groq import Groq

from runtime.config import settings

_groq = Groq(api_key=settings.groq_api_key)

WHISPER_MODEL = "whisper-large-v3-turbo"


def transcribe_url(audio_url: str) -> str:
    """
    Download audio from URL and transcribe with Groq Whisper.
    Used when Z-API provides a URL for the audio file.
    """
    audio_bytes = _download_audio(audio_url)
    return _transcribe_bytes(audio_bytes, filename="audio.ogg")


def transcribe_bytes(audio_bytes: bytes, filename: str = "audio.ogg") -> str:
    """Transcribe raw audio bytes — used when audio is sent as multipart upload."""
    return _transcribe_bytes(audio_bytes, filename=filename)


def _download_audio(url: str) -> bytes:
    with httpx.Client(timeout=30) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.content


def _transcribe_bytes(audio_bytes: bytes, filename: str) -> str:
    transcription = _groq.audio.transcriptions.create(
        model=WHISPER_MODEL,
        file=(filename, audio_bytes, _mime_for(filename)),
        language="pt",
        response_format="text",
    )
    # Groq returns str directly when response_format="text"
    return transcription.strip() if isinstance(transcription, str) else transcription.text.strip()


def _mime_for(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower()
    return {
        "ogg": "audio/ogg",
        "mp3": "audio/mpeg",
        "mp4": "audio/mp4",
        "wav": "audio/wav",
        "m4a": "audio/mp4",
    }.get(ext, "audio/ogg")
