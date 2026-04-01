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


def _ensure_bucket(bucket: str) -> None:
    try:
        supabase.storage.create_bucket(bucket, options={"public": True})
    except Exception:
        pass


def _upload_mp3(audio_bytes: bytes, filename_prefix: str, bucket: str) -> str | None:
    """Faz upload dos bytes para Supabase Storage e retorna URL pública."""
    file_name = f"{filename_prefix}_{uuid.uuid4().hex[:8]}.mp3"
    supabase.storage.from_(bucket).upload(
        path=file_name,
        file=audio_bytes,
        file_options={"content-type": "audio/mpeg"},
    )
    return supabase.storage.from_(bucket).get_public_url(file_name)


def _elevenlabs_tts(text: str, voice_id: str | None = None) -> bytes | None:
    """Gera áudio via ElevenLabs API. Retorna bytes MP3 ou None se falhar."""
    try:
        import httpx
        api_key = settings.elevenlabs_api_key
        if not api_key:
            return None

        active_voice_id = voice_id or ELEVENLABS_VOICE_ID
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{active_voice_id}"
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


def get_tts_info() -> dict:
    """
    Retorna o estado atual do engine TTS — usada pelo endpoint GET /friday/tts-info.

    Verifica se ElevenLabs está configurado e responsivo.
    Nunca falha silenciosamente: status é sempre explícito.

    Returns:
        dict com engine, voice_id, voice_name, status e fallback info.
    """
    api_key = settings.elevenlabs_api_key
    elevenlabs_configured = bool(api_key)
    elevenlabs_alive = False
    voice_name = "unknown"

    if elevenlabs_configured:
        try:
            import httpx
            # Valida a API key e obtém o nome da voz ativa
            r = httpx.get(
                f"https://api.elevenlabs.io/v1/voices/{ELEVENLABS_VOICE_ID}",
                headers={"xi-api-key": api_key},
                timeout=8,
            )
            if r.status_code == 200:
                elevenlabs_alive = True
                voice_name = r.json().get("name", "unknown")
            else:
                print(f"[tts] ElevenLabs voice check retornou {r.status_code}")
        except Exception as e:
            print(f"[tts] ElevenLabs health check falhou: {e}")

    # Verifica se gTTS está disponível como fallback
    gtts_available = False
    try:
        import gtts  # noqa: F401
        gtts_available = True
    except ImportError:
        pass

    if elevenlabs_alive:
        return {
            "engine": "elevenlabs",
            "voice_id": ELEVENLABS_VOICE_ID,
            "voice_name": voice_name,
            "status": "active",
            "fallback_available": gtts_available,
            "fallback_engine": "gtts" if gtts_available else None,
        }
    elif gtts_available:
        return {
            "engine": "gtts",
            "voice_id": None,
            "voice_name": "gTTS PT-BR",
            "status": "fallback_active",
            "fallback_available": True,
            "fallback_engine": "gtts",
            "elevenlabs_reason": "not_configured" if not elevenlabs_configured else "unreachable",
        }
    else:
        return {
            "engine": None,
            "voice_id": None,
            "voice_name": None,
            "status": "unavailable",
            "fallback_available": False,
            "fallback_engine": None,
            "elevenlabs_reason": "not_configured" if not elevenlabs_configured else "unreachable",
        }


def text_to_audio_url(
    text: str,
    filename_prefix: str = "friday",
    voice_id: str | None = None,
    bucket: str | None = None,
) -> str | None:
    """
    Converte texto em áudio MP3 e faz upload ao Supabase Storage.
    Tenta ElevenLabs primeiro, fallback para gTTS.
    Retorna URL pública ou None se tudo falhar.

    Args:
        text: Texto a converter em áudio.
        filename_prefix: Prefixo do arquivo no Storage (ex: "friday", "character_finch").
        voice_id: Voice ID ElevenLabs a usar. None = usa ELEVENLABS_VOICE_ID (Rachel/Friday).
        bucket: Bucket do Supabase Storage. None = usa "friday-audio".
    """
    active_bucket = bucket or BUCKET
    try:
        _ensure_bucket(active_bucket)

        # Tentar ElevenLabs primeiro
        audio_bytes = _elevenlabs_tts(text, voice_id=voice_id)
        provider = "elevenlabs"

        # Fallback para gTTS
        if not audio_bytes:
            print("[tts] Usando fallback gTTS")
            audio_bytes = _gtts_tts(text)
            provider = "gtts"

        if not audio_bytes:
            return None

        url = _upload_mp3(audio_bytes, filename_prefix, active_bucket)
        print(f"[tts] Áudio gerado via {provider}: {url}")
        return url

    except Exception as e:
        print(f"[tts] Erro geral: {e}")
        return None
