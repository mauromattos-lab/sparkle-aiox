"""
Text-to-Speech — converte texto em áudio MP3 e faz upload para Supabase Storage.
Retorna URL pública para uso no Z-API send_audio().

Provider: ElevenLabs (voz natural) com fallback para gTTS se falhar.
Bucket: 'friday-audio' (público)
"""
from __future__ import annotations

import os
import tempfile
import uuid

from runtime.config import settings
from runtime.db import supabase

BUCKET = "friday-audio"
ELEVENLABS_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel — voz feminina natural em PT
ELEVENLABS_MODEL = "eleven_multilingual_v2"


def _ensure_bucket() -> None:
    try:
        supabase.storage.create_bucket(BUCKET, options={"public": True})
    except Exception:
        pass


def _upload_mp3(audio_bytes: bytes, filename_prefix: str) -> str | None:
    """Faz upload dos bytes para Supabase Storage e retorna URL pública."""
    file_name = f"{filename_prefix}_{uuid.uuid4().hex[:8]}.mp3"
    supabase.storage.from_(BUCKET).upload(
        path=file_name,
        file=audio_bytes,
        file_options={"content-type": "audio/mpeg"},
    )
    return supabase.storage.from_(BUCKET).get_public_url(file_name)


def _elevenlabs_tts(text: str) -> bytes | None:
    """Gera áudio via ElevenLabs API. Retorna bytes MP3 ou None se falhar."""
    try:
        import httpx
        api_key = settings.elevenlabs_api_key
        if not api_key:
            return None

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
        headers = {
            "xi-api-key": api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "model_id": ELEVENLABS_MODEL,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }
        r = httpx.post(url, json=payload, headers=headers, timeout=30)
        r.raise_for_status()
        return r.content
    except Exception as e:
        print(f"[tts] ElevenLabs falhou: {e}")
        return None


def _gtts_tts(text: str) -> bytes | None:
    """Fallback: gera áudio via gTTS (Google). Retorna bytes MP3 ou None se falhar."""
    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang="pt", slow=False)
        tmp_path = None
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name
        tts.save(tmp_path)
        with open(tmp_path, "rb") as f:
            return f.read()
    except Exception as e:
        print(f"[tts] gTTS falhou: {e}")
        return None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


def text_to_audio_url(text: str, filename_prefix: str = "friday") -> str | None:
    """
    Converte texto em áudio MP3 e faz upload ao Supabase Storage.
    Tenta ElevenLabs primeiro, fallback para gTTS.
    Retorna URL pública ou None se tudo falhar.
    """
    try:
        _ensure_bucket()

        # Tentar ElevenLabs primeiro
        audio_bytes = _elevenlabs_tts(text)
        provider = "elevenlabs"

        # Fallback para gTTS
        if not audio_bytes:
            print("[tts] Usando fallback gTTS")
            audio_bytes = _gtts_tts(text)
            provider = "gtts"

        if not audio_bytes:
            return None

        url = _upload_mp3(audio_bytes, filename_prefix)
        print(f"[tts] Áudio gerado via {provider}: {url}")
        return url

    except Exception as e:
        print(f"[tts] Erro geral: {e}")
        return None
