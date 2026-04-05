"""
generate_content handler — F2-P1: Content Generation Engine.

Gera conteúdo de Instagram (post, carrossel, story) a partir do Brain.

Fluxo:
  1. Busca chunks relevantes do Brain (via brain_query semântica)
  2. Carrega persona do personagem (soul_prompt) se disponível
  3. Gera conteúdo via Claude Sonnet com contexto do Brain
  4. Extrai hashtags automaticamente
  5. Salva em generated_content com status=draft
  6. Retorna preview + content_id para aprovação

Formatos suportados:
  - instagram_post: legenda única (máx 2200 chars)
  - carousel: 5-7 slides com texto por slide
  - story: texto curto impactante (máx 200 chars)
  - thread: sequência de 3-5 posts encadeados

source_type:
  - manual: gerado por request explícito
  - repurpose_audio: gerado a partir de transcrição de áudio do Mauro
  - cron: gerado automaticamente pelo scheduler semanal
  - brain_trigger: gerado quando entidade acumula novos chunks
"""
from __future__ import annotations

import asyncio
import os
import re
from typing import Optional

import httpx

from runtime.config import settings
from runtime.db import supabase
from runtime.utils.llm import call_claude
from runtime.characters.juno_soul import SOUL_PROMPT as _JUNO_SOUL_PROMPT


# ── Personas de geração ───────────────────────────────────────────────────────

_PERSONA_PROMPTS: dict[str, str] = {
    "zenya": (
        "Você é Zenya, assistente de IA que ajuda negócios a crescerem com presença digital inteligente. "
        "Tom: direto, empático, sem jargão técnico. Fala como uma parceira de negócio, não como robô. "
        "Usa linguagem do dono de negócio brasileiro — prático, resultado-orientado."
    ),
    "finch": (
        "Você é Finch, coach de hábitos e desenvolvimento intencional. "
        "Tom: desafiador mas acolhedor. Faz perguntas que fazem pensar. "
        "Foca em comportamento, consistência e identidade — não em motivação passageira."
    ),
    "mauro": (
        "Você é Mauro Mattos, fundador da Sparkle AIOX. "
        "Tom: visionário, direto, sem frescura. Fala de IA, negócios e autonomia como quem vive isso. "
        "Estilo: insights densos em poucas palavras, sem floreio."
    ),
    "juno": _JUNO_SOUL_PROMPT,
}

_FORMAT_INSTRUCTIONS: dict[str, str] = {
    "instagram_post": (
        "Escreva uma legenda para Instagram com:\n"
        "- Abertura impactante (1ª linha = gancho que para o scroll)\n"
        "- Corpo: 3-5 parágrafos curtos, um conceito por parágrafo\n"
        "- CTA claro no final\n"
        "- Máximo 2200 caracteres\n"
        "- Não inclua hashtags no corpo — liste ao final separado por '---HASHTAGS---'"
    ),
    "carousel": (
        "Crie um carrossel de Instagram com 5-7 slides:\n"
        "- Slide 1: título/gancho (máx 10 palavras)\n"
        "- Slides 2-6: um insight por slide (1-2 frases cada)\n"
        "- Último slide: CTA\n"
        "Formato: 'SLIDE 1:\\n[texto]\\n\\nSLIDE 2:\\n[texto]...'\n"
        "Não inclua hashtags — liste ao final separado por '---HASHTAGS---'"
    ),
    "story": (
        "Escreva um texto para Story de Instagram:\n"
        "- Máximo 200 caracteres\n"
        "- Impactante, ação imediata ou pergunta provocativa\n"
        "- Sem hashtags"
    ),
    "thread": (
        "Crie uma thread de 4-6 posts encadeados:\n"
        "- Post 1: gancho/premissa\n"
        "- Posts 2-5: desenvolvimento do argumento\n"
        "- Último post: conclusão + CTA\n"
        "Formato: 'POST 1:\\n[texto]\\n\\nPOST 2:\\n[texto]...'\n"
        "Não inclua hashtags — liste ao final separado por '---HASHTAGS---'"
    ),
}


# ── Busca semântica no Brain ──────────────────────────────────────────────────

async def _query_brain(topic: str, client_id: str, limit: int = 8) -> list[dict]:
    """Busca chunks relevantes do Brain via embedding semântico."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return []
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": "text-embedding-3-small", "input": topic[:1000]},
                timeout=8.0,
            )
            resp.raise_for_status()
            embedding = resp.json()["data"][0]["embedding"]

        result = await asyncio.to_thread(
            lambda: supabase.rpc(
                "match_brain_chunks",
                {"query_embedding": embedding, "pipeline_type_in": "especialista", "client_id_in": None, "match_count": limit},
            ).execute()
        )
        return result.data or []
    except Exception as e:
        print(f"[generate_content] brain query falhou: {e}")
        return []


def _extract_hashtags(text: str) -> tuple[str, list[str]]:
    """Extrai bloco ---HASHTAGS--- do texto. Retorna (conteúdo_limpo, lista_hashtags)."""
    parts = text.split("---HASHTAGS---")
    content = parts[0].strip()
    hashtags: list[str] = []
    if len(parts) > 1:
        raw_tags = parts[1].strip()
        hashtags = [
            tag.strip().lstrip("#")
            for tag in re.split(r"[\s,\n]+", raw_tags)
            if tag.strip()
        ]
    return content, hashtags


# ── Handler principal ─────────────────────────────────────────────────────────

async def handle_generate_content(task: dict) -> dict:
    """
    Gera conteudo multi-plataforma a partir do Brain e salva em generated_content.
    Suporta Instagram, YouTube e TikTok (v2).
    """
    payload = task.get("payload", {})
    task_id = task.get("id")
    client_id = task.get("client_id") or settings.sparkle_internal_client_id

    persona: str = payload.get("persona", "zenya")
    fmt: str = payload.get("format", "instagram_post")
    platform: str = payload.get("platform", "instagram")
    topic: str = payload.get("topic") or payload.get("content") or ""
    source_type: str = payload.get("source_type", "manual")
    source_ref: str = payload.get("source_ref", "")

    if not topic:
        return {"message": "generate_content: topic obrigatório no payload."}

    # 1. Buscar contexto do Brain (3 niveis: sintese → insights → chunks)
    from runtime.brain.knowledge import retrieve_knowledge

    knowledge = await retrieve_knowledge(
        topic=topic,
        insight_types=["framework", "tecnica", "principio"],
        client_id=client_id,
        max_insights=6,
        max_chunks=3,
    )
    brain_context_text = knowledge["context_text"]
    brain_context_ids = [i["id"] for i in knowledge.get("insights", []) if i.get("id")]
    brain_context_ids += [c["id"] for c in knowledge.get("chunks", []) if c.get("id")]

    # 2. Montar prompt (v2: usa templates por plataforma quando disponivel)
    from runtime.content.templates import get_prompt_instructions
    persona_prompt = _PERSONA_PROMPTS.get(persona, _PERSONA_PROMPTS["zenya"])
    format_instruction = get_prompt_instructions(fmt, platform)

    system = (
        f"{persona_prompt}\n\n"
        "Você é um criador de conteúdo especialista. "
        "Crie conteúdo autêntico baseado no contexto fornecido. "
        "NUNCA invente dados ou estatísticas — use apenas o que está no contexto."
    )

    user_prompt = f"Tema: {topic}\n\n"
    if brain_context_text:
        user_prompt += f"Contexto do Brain (use para embasar o conteúdo):\n{brain_context_text}\n\n"
    user_prompt += f"Formato solicitado:\n{format_instruction}"

    # 3. Gerar conteúdo via Sonnet
    raw_content = await call_claude(
        prompt=user_prompt,
        system=system,
        model="claude-sonnet-4-6",
        client_id=client_id,
        task_id=task_id,
        agent_id="content-engine",
        purpose="generate_content",
        max_tokens=1200,
    )

    # 4. Extrair hashtags
    clean_content, hashtags = _extract_hashtags(raw_content)

    # 5. Salvar em generated_content
    try:
        row = {
            "client_id": client_id,
            "persona": persona,
            "format": fmt,
            "platform": platform,
            "topic": topic[:500],
            "raw_prompt": user_prompt[:2000],
            "content": clean_content,
            "hashtags": hashtags or None,
            "brain_context_ids": brain_context_ids or None,
            "status": "draft",
            "source_type": source_type,
            "source_ref": source_ref or str(task_id or ""),
        }
        result = await asyncio.to_thread(
            lambda: supabase.table("generated_content").insert(row).execute()
        )
        content_id = result.data[0]["id"] if result.data else None
    except Exception as e:
        print(f"[generate_content] falha ao salvar: {e}")
        content_id = None

    preview = clean_content[:200] + ("..." if len(clean_content) > 200 else "")
    tags_info = f"\n🏷️ {' '.join('#' + h for h in hashtags[:5])}" if hashtags else ""

    return {
        "message": (
            f"Conteudo gerado ({fmt} • {platform} • {persona})\n\n"
            f"{preview}{tags_info}"
        ),
        "content_id": content_id,
        "format": fmt,
        "platform": platform,
        "persona": persona,
        "brain_insights_used": len(knowledge.get("insights", [])),
        "brain_chunks_used": len(knowledge.get("chunks", [])),
        "brain_synthesis_domain": knowledge.get("synthesis", {}).get("domain") if knowledge.get("synthesis") else None,
        "hashtags": hashtags,
        "content": clean_content,
        "status": "draft",
    }
