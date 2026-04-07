"""
Image Generator — integração com Google Gemini Image API.

Gera imagens da Zenya usando prompt técnico + referência Tier A da Style Library.
Salva no Supabase Storage em content-assets/images/{content_piece_id}.png
Atualiza content_pieces.image_url e status.

Modelo: gemini-2.0-flash-exp-image-generation (multimodal: texto + imagem ref → imagem)
Fallback: imagen-3.0-generate-002 (text-to-image, sem referência)
"""
from __future__ import annotations

import asyncio
import base64
import httpx
import json

from runtime.config import settings
from runtime.db import supabase

CONTENT_BUCKET = "content-assets"
IMAGE_MODEL = "gemini-2.0-flash-exp-image-generation"
IMAGEN_MODEL = "imagen-3.0-generate-002"


def _get_gemini_client():
    from google import genai
    return genai.Client(api_key=settings.gemini_api_key)


async def _download_image(url: str) -> bytes:
    """Baixa imagem de uma URL pública."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content


async def generate_image_gemini(
    prompt: str,
    reference_image_url: str | None = None,
) -> bytes:
    """
    Gera imagem via Gemini multimodal (texto + ref → imagem) ou Imagen 3 (só texto).

    Args:
        prompt: Prompt técnico com descrição da Zenya
        reference_image_url: URL da imagem Tier A da Style Library (opcional)

    Returns:
        bytes da imagem PNG gerada
    """
    from google import genai
    from google.genai import types

    client = _get_gemini_client()

    if reference_image_url:
        # Multimodal: referência Tier A + prompt → imagem consistente
        ref_bytes = await _download_image(reference_image_url)
        ref_b64 = base64.b64encode(ref_bytes).decode()

        # Detectar mime type (assume png, fallback jpeg)
        mime_type = "image/png" if reference_image_url.lower().endswith(".png") else "image/jpeg"

        contents = [
            types.Content(parts=[
                types.Part(
                    inline_data=types.Blob(mime_type=mime_type, data=ref_b64)
                ),
                types.Part(text=f"Usando esta imagem como referência de estilo visual, gere uma nova imagem: {prompt}"),
            ])
        ]

        response = await asyncio.to_thread(
            client.models.generate_content,
            model=IMAGE_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
            ),
        )

        # Extrair imagem do response
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                return base64.b64decode(part.inline_data.data)

        raise RuntimeError("Gemini não retornou imagem no response")

    else:
        # Fallback: Imagen 3 text-to-image (sem referência)
        response = await asyncio.to_thread(
            client.models.generate_images,
            model=IMAGEN_MODEL,
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="9:16",
            ),
        )
        image = response.generated_images[0].image
        return image.image_bytes


async def generate_image_for_piece(
    content_piece_id: str,
    prompt: str,
    reference_image_url: str | None = None,
) -> str | None:
    """
    Gera imagem e salva no Supabase Storage.

    Args:
        content_piece_id: UUID do content piece
        prompt: Prompt técnico construído pelo image_engineer
        reference_image_url: URL pública da imagem Tier A (preferencial)

    Returns:
        URL pública da imagem no Supabase Storage, ou None em caso de falha
    """
    try:
        image_bytes = await generate_image_gemini(prompt, reference_image_url)
    except Exception as exc:
        _record_failure(content_piece_id, str(exc))
        print(f"[image_generator] ERRO piece={content_piece_id}: {exc}")
        return None

    # Salvar no Supabase Storage
    path = f"images/{content_piece_id}.png"
    try:
        supabase.storage.from_(CONTENT_BUCKET).upload(
            path=path,
            file=image_bytes,
            file_options={"content-type": "image/png", "upsert": "true"},
        )
        image_url = supabase.storage.from_(CONTENT_BUCKET).get_public_url(path)
    except Exception as exc:
        _record_failure(content_piece_id, f"Storage upload failed: {exc}")
        print(f"[image_generator] Storage ERRO piece={content_piece_id}: {exc}")
        return None

    # Atualizar content_pieces
    supabase.table("content_pieces").update({
        "image_url": image_url,
        "status": "image_done",
    }).eq("id", content_piece_id).execute()

    print(f"[image_generator] piece={content_piece_id} image_url={image_url}")
    return image_url


def _record_failure(content_piece_id: str, error: str) -> None:
    """Registra falha em error_log e avança status para image_failed."""
    try:
        # Buscar error_log atual
        result = supabase.table("content_pieces").select("error_log").eq(
            "id", content_piece_id
        ).execute()
        current_log = (result.data[0].get("error_log") or []) if result.data else []
        if isinstance(current_log, str):
            try:
                current_log = json.loads(current_log)
            except Exception:
                current_log = []

        current_log.append({"stage": "image_generation", "error": error})

        supabase.table("content_pieces").update({
            "status": "image_failed",
            "error_log": current_log,
        }).eq("id", content_piece_id).execute()
    except Exception:
        pass  # falha no log não deve crashar o fluxo
