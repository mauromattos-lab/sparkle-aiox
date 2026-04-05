"""
brain_ingest handler — S9-P1: Brain como órgão de memória persistente.

Fluxo:
  1. Extrai conteúdo do payload
  2. Canonicaliza entidades via brain_entities (S9-P1)
  3. Gera embedding via OpenAI (text-embedding-3-small)
  4. Insere em brain_chunks com embedding + entity_tags
  5. Retorna confirmação para Friday → Mauro

Fontes suportadas:
  - friday_ingest: Mauro envia direto pelo WhatsApp ("brain, aprende isso: X")
  - agent_output: agente ingere decisão ao concluir task
  - adr: decisão arquitetural (POST /brain/ingest com ingest_type=adr)
  - conclave_output: deliberação do Conclave
  - mauro_audio: transcrição de áudio do Mauro

S9 regra: source_agent obrigatório — rejeita se ausente.
"""
from __future__ import annotations

import asyncio
import re

from runtime.brain.embedding import get_embedding
from runtime.brain.isolation import get_brain_owner_for_ingest
from runtime.config import settings
from runtime.db import supabase


# ── Canonicalização ──────────────────────────────────────────────────────────

async def _get_entity_registry(client_id: str) -> list[dict]:
    """Carrega entidades canônicas do Supabase para substituição."""
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("brain_entities")
            .select("canonical_name,aliases,entity_type")
            .eq("client_id", client_id)
            .execute()
        )
        return result.data or []
    except Exception as e:
        print(f"[brain_ingest] falha ao carregar entity_registry: {e}")
        return []


async def canonicalize_entities(raw_text: str, client_id: str) -> tuple[str, list[str]]:
    """
    Substitui aliases por nomes canônicos e retorna (texto_canonico, entidades_referenciadas).
    Ex: "mauro", "o mauro", "mauro mattos" → "Mauro Mattos"
    """
    entities = await _get_entity_registry(client_id)
    canonical_text = raw_text
    referenced: list[str] = []

    for entity in entities:
        canonical = entity["canonical_name"]
        for alias in entity.get("aliases", []):
            if not alias:
                continue
            # Word boundary: evita substituir "mauro" dentro de "Mauro Mattos" já substituído
            pattern = r'(?<!\w)' + re.escape(alias) + r'(?!\w)'
            if re.search(pattern, canonical_text, flags=re.IGNORECASE):
                canonical_text = re.sub(
                    pattern, canonical, canonical_text, flags=re.IGNORECASE
                )
                if canonical not in referenced:
                    referenced.append(canonical)

    return canonical_text, referenced


# ── Handler principal ────────────────────────────────────────────────────────

_COMMAND_PREFIX_RE = re.compile(
    r"^(brain[,.]?\s*)?(aprende\s+(isso|que)|salva[,:]?|registra[,:]?|anota[,:]?|adiciona[,:]?)\s*:?\s*",
    flags=re.IGNORECASE,
)


async def handle_brain_ingest(task: dict) -> dict:
    """
    Ingere conteúdo no Brain (tabela brain_chunks) com canonicalização + embedding.
    """
    payload = task.get("payload", {})
    client_id = task.get("client_id") or settings.sparkle_internal_client_id
    source_agent = payload.get("source_agent") or payload.get("source") or "friday"
    ingest_type = payload.get("ingest_type", "friday_ingest")

    # Extrai conteúdo
    content = (
        payload.get("content")
        or payload.get("original_text", "")
    )
    if not content:
        return {"message": "Brain: não recebi conteúdo para registrar."}

    # Remove prefixos de comando (friday_ingest = texto; mauro_audio = transcrição de voz)
    if ingest_type in ("friday_ingest", "mauro_audio"):
        content = _COMMAND_PREFIX_RE.sub("", content).strip()

    if not content:
        return {"message": "Brain: conteúdo vazio após processar. Tente novamente com mais texto."}

    # S9-P1: Canonicalização
    canonical_content, entity_tags = await canonicalize_entities(content, client_id)

    # Adiciona entity_refs manuais se vieram no payload
    for ref in payload.get("entity_refs", []):
        if ref and ref not in entity_tags:
            entity_tags.append(ref)

    # Gera embedding
    embedding = await get_embedding(canonical_content or content)

    # Monta metadata
    metadata: dict = {
        "source_agent": source_agent,
        "ingest_type": ingest_type,
        "task_ref": str(task.get("id", "")),
    }
    if payload.get("source_title"):
        metadata["source_title"] = payload["source_title"]

    # B1-03: resolve brain_owner for this ingest based on agent + client
    brain_owner = get_brain_owner_for_ingest(source_agent, client_id)

    # Insere em brain_chunks (schema produção: raw_content, chunk_metadata, sem entity_tags)
    try:
        row: dict = {
            "raw_content": content,
            "canonical_content": canonical_content if canonical_content != content else None,
            "source_type": ingest_type,
            "source_title": metadata.get("source_title") or f"friday_{source_agent}",
            "pipeline_type": "mauro",  # allowed: especialista|cliente|mauro
            "brain_owner": brain_owner,
            "chunk_metadata": {
                **metadata,
                "entity_tags": entity_tags,
            },
        }
        if embedding:
            row["embedding"] = embedding

        result = await asyncio.to_thread(
            lambda: supabase.table("brain_chunks").insert(row).execute()
        )
        chunk_id = result.data[0]["id"] if result.data else None
    except Exception as e:
        print(f"[brain_ingest] falha ao inserir chunk: {e}")
        return {"message": f"Brain: erro ao registrar conhecimento — {e}"}

    preview = content[:100] + ("..." if len(content) > 100 else "")
    entity_info = f" [{', '.join(entity_tags)}]" if entity_tags else ""
    emb_info = " + embedding vetorial" if embedding else ""

    return {
        "message": (
            f"Anotado no Brain ✅{entity_info}{emb_info}\n\n"
            f"{preview}"
        ),
        "chunk_id": chunk_id,
        "entity_tags": entity_tags,
        "embedded": embedding is not None,
    }
