"""
Voice Generator — converte voice_script em áudio MP3 usando ElevenLabs (voz da Zenya).

Salva o áudio em Supabase Storage no bucket 'content-assets' com path determinístico:
  audio/{content_piece_id}.mp3

Atualiza content_pieces.audio_url após upload bem-sucedido.

Se voice_script for None → audio_url = None (sem chamada ao ElevenLabs).
Reusa a integração ElevenLabs de runtime/utils/tts.py.
"""
from __future__ import annotations

from runtime.config import settings
from runtime.db import supabase
from runtime.utils.tts import _elevenlabs_tts, _ensure_bucket, _upload_mp3

CONTENT_BUCKET = "content-assets"


def _get_zenya_voice_id() -> str:
    """Retorna o Voice ID da Zenya configurado em variável de ambiente."""
    voice_id = settings.elevenlabs_zenya_voice_id
    if not voice_id:
        raise ValueError(
            "ELEVENLABS_ZENYA_VOICE_ID não configurado. "
            "Configure a variável de ambiente com o Voice ID da Zenya no ElevenLabs."
        )
    return voice_id


async def generate_voice_for_piece(
    content_piece_id: str,
    voice_script: str | None,
) -> str | None:
    """
    Gera áudio MP3 do voice_script e salva no Supabase Storage.

    Args:
        content_piece_id: UUID do content piece (usado como nome do arquivo)
        voice_script: Texto para TTS. Se None → retorna None sem chamar ElevenLabs.

    Returns:
        URL pública do áudio ou None se voice_script for None ou geração falhar.
    """
    if voice_script is None:
        print(f"[voice_generator] piece={content_piece_id} voice_script=None → sem áudio")
        _update_audio_url(content_piece_id, None)
        return None

    voice_id = _get_zenya_voice_id()
    _ensure_bucket(CONTENT_BUCKET)

    audio_bytes = _elevenlabs_tts(voice_script, voice_id=voice_id)

    if not audio_bytes:
        print(f"[voice_generator] ElevenLabs falhou para piece={content_piece_id}")
        return None

    # Path determinístico: audio/{content_piece_id}.mp3
    path = f"audio/{content_piece_id}.mp3"
    supabase.storage.from_(CONTENT_BUCKET).upload(
        path=path,
        file=audio_bytes,
        file_options={"content-type": "audio/mpeg", "upsert": "true"},
    )
    audio_url = supabase.storage.from_(CONTENT_BUCKET).get_public_url(path)

    _update_audio_url(content_piece_id, audio_url)

    print(f"[voice_generator] piece={content_piece_id} audio_url={audio_url}")
    return audio_url


def _update_audio_url(content_piece_id: str, audio_url: str | None) -> None:
    """Atualiza content_pieces.audio_url no Supabase."""
    supabase.table("content_pieces").update(
        {"audio_url": audio_url}
    ).eq("id", content_piece_id).execute()
