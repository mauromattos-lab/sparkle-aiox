"""
Image Prompt Engineer — gera prompts técnicos para geração de imagem da Zenya.

Seleciona referência Tier A da Style Library e constrói prompt multimodal
para envio ao Google Gemini Image API.

Estilos suportados:
  - cinematic: iluminação dramática, editorial, profundidade de campo
  - influencer_natural: luz natural, lifestyle, próxima à câmera
"""
from __future__ import annotations

import random
from typing import Any

from runtime.db import supabase

ZENYA_BASE_DESCRIPTION = (
    "Zenya, uma personagem de IA brasileira. "
    "Mulher brasileira, traços marcantes, expressão confiante e acolhedora, "
    "cabelos escuros, aparência moderna e sofisticada. "
    "Mantenha exatamente o estilo visual da imagem de referência fornecida."
)

SUPPORTED_STYLES = ("cinematic", "influencer_natural")


def build_cinematic_prompt(theme: str, mood: str) -> str:
    return (
        f"{ZENYA_BASE_DESCRIPTION} "
        f"Tema: {theme}. Mood: {mood}. "
        "Iluminação cinematográfica dramática, sombras profundas, "
        "profundidade de campo rasa, lente 85mm, hora dourada, "
        "editorial de moda high-end, resolução 8k. "
        "Proporção 9:16 vertical, retrato."
    )


def build_influencer_prompt(theme: str, mood: str) -> str:
    return (
        f"{ZENYA_BASE_DESCRIPTION} "
        f"Tema: {theme}. Mood: {mood}. "
        "Luz natural, lifestyle autêntico, próxima à câmera, "
        "tons quentes, retrato para redes sociais, espontâneo, vibrante. "
        "Proporção 9:16 vertical, retrato."
    )


def build_prompt(theme: str, mood: str, style: str) -> str:
    """Seleciona e constrói o prompt técnico conforme o estilo."""
    if style == "cinematic":
        return build_cinematic_prompt(theme, mood)
    elif style == "influencer_natural":
        return build_influencer_prompt(theme, mood)
    else:
        # fallback para influencer_natural em estilo desconhecido
        return build_influencer_prompt(theme, mood)


async def get_tier_a_reference(style: str) -> dict[str, Any]:
    """
    Busca uma imagem Tier A da Style Library para usar como referência.

    Prioriza imagens com style_type correspondente ao brief e menos usadas.
    Fallback: qualquer Tier A se style_type não bater.

    Raises:
        ValueError: Se não houver imagens Tier A disponíveis.
    """
    # Prioridade 1: Tier A com style_type correspondente, menos usadas
    result = (
        supabase.table("style_library")
        .select("*")
        .eq("tier", "A")
        .eq("style_type", style)
        .order("use_count", desc=False)
        .limit(5)
        .execute()
    )

    if not result.data:
        # Fallback: qualquer Tier A
        result = (
            supabase.table("style_library")
            .select("*")
            .eq("tier", "A")
            .order("use_count", desc=False)
            .limit(5)
            .execute()
        )

    if not result.data:
        raise ValueError(
            "Style Library sem imagens Tier A — execute curadoria primeiro "
            "(Portal → /content/library)"
        )

    ref = random.choice(result.data)

    # Incrementar use_count
    supabase.table("style_library").update(
        {"use_count": (ref.get("use_count") or 0) + 1}
    ).eq("id", ref["id"]).execute()

    return ref


async def prepare_generation(
    content_piece_id: str,
    theme: str,
    mood: str,
    style: str,
) -> dict[str, Any]:
    """
    Prepara todos os dados para geração de imagem:
      - Seleciona referência Tier A
      - Constrói o prompt técnico
      - Atualiza status do content_piece para image_generating
      - Salva referências usadas

    Returns:
        dict com: prompt, reference (dict da style_library)
    """
    ref = await get_tier_a_reference(style)
    prompt = build_prompt(theme, mood, style)

    # Atualizar status e registrar referência
    supabase.table("content_pieces").update({
        "status": "image_generating",
        "image_prompt": prompt,
        "style_ref_ids": [ref["id"]],
    }).eq("id", content_piece_id).execute()

    return {
        "prompt": prompt,
        "reference": ref,
    }
