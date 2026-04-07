"""
Video Generator — integração com Google Veo 3.1 (image-to-video).

Implementa VideoGeneratorProtocol com VeoVideoGenerator.
Salva vídeo no Supabase Storage em content-assets/videos/{content_piece_id}.mp4
Atualiza content_pieces.video_url e status.

Modelo: veo-2.0-generate-001 (estável)
Abstração: VideoGeneratorProtocol → swap futuro sem alterar o pipeline
"""
from __future__ import annotations

import asyncio
import json
import httpx
from typing import Protocol, runtime_checkable

from runtime.config import settings
from runtime.db import supabase

CONTENT_BUCKET = "content-assets"
VEO_MODEL = "veo-2.0-generate-001"
VEO_TIMEOUT_ITERATIONS = 30   # 30 × 10s = 5 min
VEO_POLL_INTERVAL = 10        # segundos


@runtime_checkable
class VideoGeneratorProtocol(Protocol):
    async def generate(self, image_url: str, prompt: str, style: str) -> str:
        """
        Gera vídeo a partir de imagem + prompt de movimento.

        Args:
            image_url: URL pública da imagem gerada (Supabase Storage)
            prompt: Prompt de movimento/câmera do video_engineer
            style: 'cinematic' | 'influencer_natural'

        Returns:
            URL temporária do vídeo gerado (antes de salvar no Storage)
        """
        ...


class VeoVideoGenerator:
    """Implementação de VideoGeneratorProtocol usando Google Veo."""

    def __init__(self):
        from google import genai
        self.client = genai.Client(api_key=settings.gemini_api_key)

    async def generate(self, image_url: str, prompt: str, style: str) -> str:
        from google.genai import types

        duration = 10 if style == "cinematic" else 5

        # Criar operation de geração de vídeo
        operation = await asyncio.to_thread(
            self.client.models.generate_videos,
            model=VEO_MODEL,
            prompt=prompt,
            image=types.Image(image_url=image_url),
            config=types.GenerateVideosConfig(
                aspect_ratio="9:16",
                duration_seconds=duration,
                number_of_videos=1,
            ),
        )

        # Polling até completar
        for _ in range(VEO_TIMEOUT_ITERATIONS):
            await asyncio.sleep(VEO_POLL_INTERVAL)
            operation = await asyncio.to_thread(
                self.client.operations.get,
                operation,
            )
            if operation.done:
                break
        else:
            raise TimeoutError(
                f"Veo job timeout após {VEO_TIMEOUT_ITERATIONS * VEO_POLL_INTERVAL}s"
            )

        video_uri = operation.result.generated_videos[0].video.uri
        return video_uri


async def generate_video_for_piece(
    content_piece_id: str,
    image_url: str,
    prompt: str,
    style: str,
    generator: VideoGeneratorProtocol | None = None,
) -> str | None:
    """
    Gera vídeo, faz download e salva no Supabase Storage.

    Args:
        content_piece_id: UUID do content piece
        image_url: URL da imagem (Supabase Storage)
        prompt: Prompt de movimento do video_engineer
        style: Estilo visual
        generator: Implementação do protocolo (default: VeoVideoGenerator)

    Returns:
        URL pública do vídeo no Storage, ou None em falha
    """
    if generator is None:
        generator = VeoVideoGenerator()

    # Atualizar status
    supabase.table("content_pieces").update({
        "status": "video_generating",
        "video_prompt": prompt,
    }).eq("id", content_piece_id).execute()

    try:
        video_uri = await generator.generate(image_url, prompt, style)
    except TimeoutError as exc:
        _record_failure(content_piece_id, str(exc))
        print(f"[video_generator] TIMEOUT piece={content_piece_id}: {exc}")
        return None
    except Exception as exc:
        _record_failure(content_piece_id, str(exc))
        print(f"[video_generator] ERRO piece={content_piece_id}: {exc}")
        return None

    # Download do vídeo temporário
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(video_uri)
            resp.raise_for_status()
            video_bytes = resp.content
    except Exception as exc:
        _record_failure(content_piece_id, f"Video download failed: {exc}")
        return None

    # Upload para Supabase Storage
    path = f"videos/{content_piece_id}.mp4"
    try:
        supabase.storage.from_(CONTENT_BUCKET).upload(
            path=path,
            file=video_bytes,
            file_options={"content-type": "video/mp4", "upsert": "true"},
        )
        video_url = supabase.storage.from_(CONTENT_BUCKET).get_public_url(path)
    except Exception as exc:
        _record_failure(content_piece_id, f"Storage upload failed: {exc}")
        return None

    # Atualizar content_pieces
    supabase.table("content_pieces").update({
        "video_url": video_url,
        "status": "video_done",
    }).eq("id", content_piece_id).execute()

    print(f"[video_generator] piece={content_piece_id} video_url={video_url}")
    return video_url


def _record_failure(content_piece_id: str, error: str) -> None:
    """Registra falha em error_log e avança status para video_failed."""
    try:
        result = supabase.table("content_pieces").select("error_log").eq(
            "id", content_piece_id
        ).execute()
        current_log = (result.data[0].get("error_log") or []) if result.data else []
        if isinstance(current_log, str):
            try:
                current_log = json.loads(current_log)
            except Exception:
                current_log = []

        current_log.append({"stage": "video_generation", "error": error})

        supabase.table("content_pieces").update({
            "status": "video_failed",
            "error_log": current_log,
        }).eq("id", content_piece_id).execute()
    except Exception:
        pass
