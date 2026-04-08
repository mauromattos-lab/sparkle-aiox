"""
Copy Specialist — gera caption Instagram + voice script da Zenya.

Recebe brief (theme, mood, style, platform) e retorna:
  - caption: texto para legenda do Instagram (hook + corpo + hashtags, máx 2200 chars)
  - voice_script: narração PT-BR puro, máx ~75 palavras (30s de fala). None se não necessário.

Atualiza content_pieces.caption e content_pieces.voice_script no Supabase.
"""
from __future__ import annotations

import json
import re
from typing import Optional

from runtime.db import supabase
from runtime.utils.llm import call_claude

COPY_SYSTEM_PROMPT = """
Você é o Copy Specialist da Zenya, uma personagem de IA brasileira criativa e confiante.
Gere conteúdo para Instagram Reels da Zenya em PT-BR.

Tom: caloroso, direto, um pouco irreverente. Nunca corporativo.
Zenya é: inteligente, curiosa, próxima das pessoas, apaixonada por IA.

REGRAS OBRIGATÓRIAS:
- caption: máximo 2200 caracteres. Deve ter: hook na primeira linha (impacto imediato), corpo do conteúdo, emojis contextuais, mínimo 5 e máximo 15 hashtags relevantes no final.
- voice_script: narração em PT-BR coloquial, máximo 75 palavras (equivale a ~30s de fala). Texto puro — sem emojis, sem markdown, sem formatação. Pode ser null se o conteúdo não precisar de narração.

Retorne APENAS JSON válido com dois campos:
{
  "caption": "...",
  "voice_script": "..." ou null
}
"""


def _extract_json(text: str) -> dict:
    """Extrai JSON do texto, tolerando markdown code blocks."""
    # Remover blocos ```json ... ```
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Tentar extrair primeiro objeto JSON encontrado
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError(f"Resposta do Claude não é JSON válido: {text[:200]}")


async def generate_copy(
    theme: str,
    mood: str,
    style: str,
    platform: str = "instagram",
    include_narration: bool = True,
    client_id: str = "sparkle-internal",
    lore_context: str = "",
) -> dict:
    """
    Gera caption + voice_script para um content piece da Zenya.

    Args:
        theme: Tema do conteúdo (ex: "IA no dia a dia", "produtividade")
        mood: Mood visual/emocional (ex: "inspirador", "divertido")
        style: Estilo visual (ex: "minimalista", "colorido")
        platform: Plataforma alvo (default: instagram)
        include_narration: Se False, voice_script será sempre None
        client_id: Para logging de custo
        lore_context: Bloco de lore canônico da Zenya para injeção no prompt (W1-CONTENT-1).
                      Quando fornecido, é inserido no system prompt antes das instruções de geração.
                      String vazia = comportamento original sem lore.

    Returns:
        dict com keys: caption (str), voice_script (str | None)

    Raises:
        ValueError: Se resposta não for JSON válido
    """
    narration_note = (
        "Gere um voice_script para narração." if include_narration
        else "voice_script deve ser null — este conteúdo não precisa de narração."
    )

    prompt = (
        f"Tema: {theme}\n"
        f"Mood: {mood}\n"
        f"Estilo visual: {style}\n"
        f"Plataforma: {platform}\n"
        f"{narration_note}\n\n"
        "Gere caption + voice script seguindo as regras do sistema."
    )

    # W1-CONTENT-1: Inject lore context into system prompt if available
    if lore_context:
        effective_system = (
            COPY_SYSTEM_PROMPT
            + "\n\n=== LORE CANÔNICO DA ZENYA (use como guia de consistência) ===\n"
            + lore_context
            + "\n=== FIM DO LORE ===\n"
        )
    else:
        effective_system = COPY_SYSTEM_PROMPT

    raw = await call_claude(
        prompt,
        system=effective_system,
        model="claude-haiku-4-5-20251001",
        client_id=client_id,
        purpose="content_copy_generation",
        max_tokens=1024,
    )

    result = _extract_json(raw)

    # Validações básicas
    caption = result.get("caption", "")
    voice_script = result.get("voice_script")

    if not caption:
        raise ValueError("Caption vazia na resposta do Copy Specialist")

    if len(caption) > 2200:
        caption = caption[:2200]

    if voice_script is not None and not include_narration:
        voice_script = None

    return {
        "caption": caption,
        "voice_script": voice_script,
    }


async def apply_copy_to_piece(
    content_piece_id: str,
    theme: str,
    mood: str,
    style: str,
    platform: str = "instagram",
    include_narration: bool = True,
    client_id: str = "sparkle-internal",
    lore_context: str = "",
) -> dict:
    """
    Gera copy e atualiza content_pieces no Supabase.

    Args:
        content_piece_id: UUID do content_piece a atualizar
        theme, mood, style, platform, include_narration, client_id: passados para generate_copy
        lore_context: Bloco de lore canônico da Zenya (W1-CONTENT-1). Passado para generate_copy.

    Returns:
        dict com caption e voice_script aplicados
    """
    copy_data = await generate_copy(
        theme=theme,
        mood=mood,
        style=style,
        platform=platform,
        include_narration=include_narration,
        client_id=client_id,
        lore_context=lore_context,
    )

    supabase.table("content_pieces").update({
        "caption": copy_data["caption"],
        "voice_script": copy_data["voice_script"],
    }).eq("id", content_piece_id).execute()

    print(
        f"[copy_specialist] piece={content_piece_id} "
        f"caption={len(copy_data['caption'])}chars "
        f"voice_script={'yes' if copy_data['voice_script'] else 'none'}"
    )

    return copy_data
