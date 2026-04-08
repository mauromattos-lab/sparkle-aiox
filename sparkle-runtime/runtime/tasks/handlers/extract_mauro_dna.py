"""
Handler: extract_mauro_dna — W2-FRIDAY-1.

Extrai DNA do Mauro em 7 categorias a partir das conversas com a Friday
(conversation_history WHERE role = 'user' AND client_id IS NULL).

Usa Claude Haiku para analisar as conversas e extrair insights estruturados.
Persiste em mauro_dna com upsert por (dna_type, key).

As 7 categorias (dna_type values):
  valores         — crenças fundacionais, o que Mauro defende
  preferencias    — como gosta de receber informação, cadência, formato
  cultura_pop     — referências (filmes, jogos, livros, analogias)
  tom_comunicacao — como fala, vocabulário, humor, estilo
  pilares_pessoais — saúde, mente/alma, financeiro, relacionamentos
  visao_negocio   — o que a Sparkle é/não é, para onde vai
  gatilhos_atencao — o que merece atenção imediata vs pode esperar

Payload:
  days_back (int)  — quantos dias de histórico processar (default 7)

Retorna:
  { entries_extracted, categories, entries: [{dna_type, key, content}...] }
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from runtime.db import supabase
from runtime.config import settings

logger = logging.getLogger(__name__)

_CATEGORIES = [
    "valores",
    "preferencias",
    "cultura_pop",
    "tom_comunicacao",
    "pilares_pessoais",
    "visao_negocio",
    "gatilhos_atencao",
]

_EXTRACTION_PROMPT = """Você é um sistema de extração de DNA comportamental e de personalidade.
Analise as conversas abaixo entre Mauro e sua assistente Friday e extraia insights estruturados sobre Mauro.

Extraia APENAS o que Mauro expressou com convicção — não infira preferências não declaradas.

Para cada categoria, retorne um JSON array de entries. Cada entry tem:
- key: identificador curto (snake_case, ex: "prosperidade_como_valor")
- content: o insight extraído (1-3 frases diretas)
- confidence: float 0.0-1.0 (quão certeza você tem que isso representa Mauro)

CATEGORIAS:
1. valores — crenças fundacionais (prosperidade, dignidade humana, AI-native, etc.)
2. preferencias — como gosta de receber informação (direto, exemplos, listas, etc.)
3. cultura_pop — referências culturais explicitamente mencionadas (filmes, jogos, etc.)
4. tom_comunicacao — como ele fala (palavras favoritas, humor, estilo de argumentação)
5. pilares_pessoais — o que ele menciona sobre saúde, família, finanças pessoais, espiritualidade
6. visao_negocio — o que ele acredita sobre a Sparkle, mercado, produto, estratégia
7. gatilhos_atencao — o que ele diz que precisa de atenção imediata vs pode esperar

Retorne um JSON VÁLIDO com esta estrutura exata (sem markdown, sem ```):
{
  "valores": [{"key": "...", "content": "...", "confidence": 0.8}],
  "preferencias": [...],
  "cultura_pop": [...],
  "tom_comunicacao": [...],
  "pilares_pessoais": [...],
  "visao_negocio": [...],
  "gatilhos_atencao": [...]
}

Se não houver informação suficiente para uma categoria, retorne um array vazio [].
Não inclua entries com confidence < 0.6.

CONVERSAS PARA ANALISAR:
{conversations}"""


async def extract_mauro_dna(days_back: int = 7) -> dict:
    """
    Processa conversas dos últimos `days_back` dias e extrai DNA do Mauro.
    Retorna dict com entries_extracted, categories, entries.
    """
    import anthropic

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()

    # Buscar conversas Friday-Mauro (client_id IS NULL = conversa com Mauro)
    res = await asyncio.to_thread(
        lambda: supabase.table("conversation_history")
        .select("role,content,created_at")
        .is_("client_id", "null")
        .gte("created_at", cutoff)
        .order("created_at")
        .limit(300)
        .execute()
    )
    conversations = res.data or []

    if not conversations:
        logger.info("[extract_mauro_dna] nenhuma conversa nos últimos %d dias", days_back)
        return {"entries_extracted": 0, "categories": {}, "entries": [], "message": "sem conversas no período"}

    # Formatar conversas para o prompt
    formatted = []
    for msg in conversations:
        role = msg.get("role", "unknown")
        content = (msg.get("content") or "").strip()
        if not content or len(content) < 5:
            continue
        ts = (msg.get("created_at") or "")[:10]
        formatted.append(f"[{ts}] {role.upper()}: {content[:500]}")

    if not formatted:
        return {"entries_extracted": 0, "categories": {}, "entries": [], "message": "conversas sem conteúdo relevante"}

    conversations_text = "\n".join(formatted)
    prompt = _EXTRACTION_PROMPT.replace("{conversations}", conversations_text[:12000])

    # Chamar Claude Haiku
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    try:
        response = await asyncio.to_thread(
            lambda: client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
        )
        raw = response.content[0].text.strip() if response.content else ""
    except Exception as e:
        logger.error("[extract_mauro_dna] Haiku call failed: %s", e)
        return {"entries_extracted": 0, "categories": {}, "entries": [], "error": str(e)}

    # Parse JSON com fallback
    try:
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        extracted = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("[extract_mauro_dna] JSON parse failed: %s | raw=%s", e, raw[:200])
        return {"entries_extracted": 0, "categories": {}, "entries": [], "error": f"JSON parse: {e}"}

    # Persistir entries em mauro_dna (upsert por dna_type + key)
    now = datetime.now(timezone.utc).isoformat()
    all_entries = []
    categories_count: dict[str, int] = {}

    for category in _CATEGORIES:
        category_entries = extracted.get(category) or []
        if not isinstance(category_entries, list):
            continue

        count = 0
        for entry in category_entries:
            if not isinstance(entry, dict):
                continue
            key = entry.get("key", "").strip()
            content = entry.get("content", "").strip()
            confidence = float(entry.get("confidence", 0))

            if not key or not content or confidence < 0.6:
                continue

            # Upsert: se existir (dna_type, key) → atualiza; se não → insere
            try:
                existing = await asyncio.to_thread(
                    lambda k=key, c=category: supabase.table("mauro_dna")
                    .select("id")
                    .eq("dna_type", c)
                    .eq("key", k)
                    .limit(1)
                    .execute()
                )

                if existing.data:
                    await asyncio.to_thread(
                        lambda eid=existing.data[0]["id"], ct=content, cf=confidence: (
                            supabase.table("mauro_dna")
                            .update({"content": ct, "confidence": cf, "extracted_at": now})
                            .eq("id", eid)
                            .execute()
                        )
                    )
                else:
                    await asyncio.to_thread(
                        lambda k=key, c=category, ct=content, cf=confidence: (
                            supabase.table("mauro_dna")
                            .insert({
                                "dna_type": c,
                                "key": k,
                                "content": ct,
                                "confidence": cf,
                                "source": f"friday_conversation_last_{days_back}d",
                                "extracted_at": now,
                            })
                            .execute()
                        )
                    )

                all_entries.append({"dna_type": category, "key": key, "content": content, "confidence": confidence})
                count += 1

            except Exception as e:
                logger.warning("[extract_mauro_dna] upsert failed for %s/%s: %s", category, key, e)

        if count > 0:
            categories_count[category] = count

    total = len(all_entries)
    logger.info(
        "[extract_mauro_dna] %d entries extraídas em %d categorias (days_back=%d)",
        total, len(categories_count), days_back
    )

    return {
        "entries_extracted": total,
        "categories": categories_count,
        "entries": all_entries,
        "conversations_processed": len(formatted),
        "days_back": days_back,
    }


async def handle_extract_mauro_dna(task: dict) -> dict:
    """Entry point para o task worker."""
    payload = task.get("payload") or {}
    days_back = int(payload.get("days_back", 7))
    return await extract_mauro_dna(days_back=days_back)
