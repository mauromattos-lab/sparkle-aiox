"""
SYS-4: extract_client_dna handler — extrai DNA estruturado do cliente
a partir de chunks do Brain e opcionalmente gera soul_prompt.

6 camadas: identidade, tom_voz, regras_negocio, diferenciais, publico_alvo, anti_patterns.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from runtime.config import settings
from runtime.db import supabase
from runtime.utils.llm import call_claude


_CLIENT_DNA_SYSTEM = """Voce extrai o DNA de um negocio a partir de conteudo ingerido (site, Instagram, conversas).

Seu objetivo: gerar um perfil estruturado que permita a uma IA de atendimento (Zenya) conversar
com os clientes desse negocio de forma natural e precisa.

Voce recebera chunks de conteudo do negocio. Extraia:

1. identidade: nome, tipo de negocio, localizacao, canais de atendimento, resumo em 1 frase
2. tom_voz: estilo de comunicacao, formalidade, uso de emojis, tratamento, 2-3 exemplos de frases tipicas
3. regras_negocio: regras operacionais (horarios, prazos, politicas, restricoes) — lista de strings
4. diferenciais: o que diferencia o negocio (max 5 itens) — lista de strings
5. publico_alvo: perfil demografico, dores, desejos — objeto estruturado
6. anti_patterns: o que a IA de atendimento NUNCA deve fazer/dizer — lista de strings

IMPORTANTE:
- Extraia apenas o que o conteudo evidencia. Nao invente.
- Se uma camada nao tem evidencia suficiente, retorne null para ela.
- tom_voz.exemplos devem ser frases que o proprio negocio usaria, nao descricoes.

Responda APENAS com JSON valido seguindo o schema descrito."""


_SOUL_PROMPT_SYSTEM = """Voce gera system prompts para a Zenya, uma assistente de atendimento via WhatsApp.

Dado o DNA estruturado de um negocio, gere um system prompt completo que inclua:

1. IDENTIDADE: quem a Zenya eh neste contexto (nome do negocio, o que faz)
2. TOM DE VOZ: como deve falar (baseado no tom_voz do DNA)
3. REGRAS: o que sabe responder, horarios, politicas (baseado em regras_negocio)
4. DIFERENCIAIS: como apresentar o negocio quando perguntada
5. ESCALAMENTO: quando passar para humano (duvidas fora do escopo, reclamacoes, pedidos complexos)
6. ANTI-PATTERNS: o que nunca fazer

O prompt deve ser direto, em segunda pessoa ("voce eh..."), sem markdown, max 1500 caracteres.
Nao inclua instrucoes sobre como usar — apenas o prompt em si."""


_DNA_LAYERS = ("identidade", "tom_voz", "regras_negocio", "diferenciais", "publico_alvo", "anti_patterns")


def _parse_json_response(raw: str) -> dict | None:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


def _count_layers(dna: dict) -> int:
    return sum(1 for k in _DNA_LAYERS if dna.get(k) is not None)


async def _get_client_chunks(client_id: str, limit: int = 50) -> list[dict]:
    result = await asyncio.to_thread(
        lambda: supabase.table("brain_chunks")
        .select("id,raw_content,source_type,source_title,chunk_metadata")
        .eq("client_id", client_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


async def _get_next_version(client_id: str) -> int:
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("zenya_clients")
            .select("client_dna")
            .eq("client_id", client_id)
            .single()
            .execute()
        )
        dna = result.data.get("client_dna") or {} if result.data else {}
        meta = dna.get("extraction_meta", {})
        return meta.get("version", 0) + 1
    except Exception:
        return 1


async def _update_zenya_client(client_id: str, update_data: dict) -> None:
    await asyncio.to_thread(
        lambda: supabase.table("zenya_clients")
        .update(update_data)
        .eq("client_id", client_id)
        .execute()
    )


async def _generate_soul_prompt_from_dna(
    dna: dict, client_id: str, task_id: str | None
) -> str | None:
    prompt = f"DNA do negocio:\n\n{json.dumps(dna, ensure_ascii=False, indent=2)}"
    try:
        soul = await call_claude(
            prompt=prompt,
            system=_SOUL_PROMPT_SYSTEM,
            model="claude-sonnet-4-6",
            client_id=client_id,
            task_id=task_id,
            agent_id="system",
            purpose="generate_soul_prompt",
            max_tokens=1024,
        )
        return soul.strip() if soul else None
    except Exception as e:
        print(f"[extract_client_dna] falha ao gerar soul_prompt: {e}")
        return None


async def _persist_dna_layers(client_id: str, dna: dict, chunks: list[dict]) -> int:
    """Persist each DNA layer as a row in client_dna table."""
    confidence_map = {"high": 0.9, "medium": 0.6, "low": 0.3}
    meta = dna.get("extraction_meta", {})
    confidence_val = confidence_map.get(meta.get("confidence", "low"), 0.3)
    chunk_ids = [c.get("id") for c in chunks if c.get("id")]
    now = datetime.now(timezone.utc).isoformat()

    # Delete old DNA rows for this client before inserting fresh ones
    try:
        await asyncio.to_thread(
            lambda: supabase.table("client_dna")
            .delete()
            .eq("client_id", client_id)
            .execute()
        )
    except Exception as e:
        print(f"[extract_client_dna] falha ao limpar DNA anterior: {e}")

    rows = []
    for layer in _DNA_LAYERS:
        value = dna.get(layer)
        if value is None:
            continue

        # Serialize complex values to JSON string for content
        if isinstance(value, (dict, list)):
            content = json.dumps(value, ensure_ascii=False)
        else:
            content = str(value)

        # Build a readable title
        title_map = {
            "identidade": "Identidade do Negocio",
            "tom_voz": "Tom de Voz",
            "regras_negocio": "Regras de Negocio",
            "diferenciais": "Diferenciais",
            "publico_alvo": "Publico-Alvo",
            "anti_patterns": "Anti-Patterns",
        }

        rows.append({
            "client_id": client_id,
            "dna_type": layer,
            "title": title_map.get(layer, layer),
            "content": content,
            "confidence": confidence_val,
            "source_chunk_ids": chunk_ids[:50],  # limit array size
            "tags": meta.get("sources_used", []),
            "created_at": now,
            "updated_at": now,
        })

    if not rows:
        return 0

    try:
        await asyncio.to_thread(
            lambda: supabase.table("client_dna").insert(rows).execute()
        )
        return len(rows)
    except Exception as e:
        print(f"[extract_client_dna] falha ao persistir DNA layers: {e}")
        return 0


async def _mark_chunks_processed(client_id: str, chunks: list[dict]) -> None:
    """Mark chunks as having gone through dna_extraction stage."""
    for chunk in chunks:
        chunk_id = chunk.get("id")
        if not chunk_id:
            continue
        try:
            # Fetch current processed_stages, append dna_extraction
            result = await asyncio.to_thread(
                lambda cid=chunk_id: supabase.table("brain_chunks")
                .select("processed_stages")
                .eq("id", cid)
                .single()
                .execute()
            )
            current = result.data.get("processed_stages") or [] if result.data else []
            if "dna_extraction" not in current:
                current.append("dna_extraction")
                await asyncio.to_thread(
                    lambda cid=chunk_id, stages=current: supabase.table("brain_chunks")
                    .update({"processed_stages": stages})
                    .eq("id", cid)
                    .execute()
                )
        except Exception:
            # Non-critical — column may not exist yet
            pass


async def handle_extract_client_dna(task: dict) -> dict:
    """
    Extrai DNA do cliente a partir de chunks do Brain.
    Atualiza zenya_clients.client_dna e opcionalmente gera soul_prompt.
    """
    payload = task.get("payload", {})
    client_id = payload.get("client_id")

    if not client_id:
        return {"error": "client_id obrigatorio"}

    chunks = await _get_client_chunks(client_id, limit=50)
    if not chunks:
        return {"error": f"Nenhum chunk encontrado no Brain para client_id={client_id}"}

    chunks_text = "\n\n---\n\n".join(
        f"[{c.get('source_type', '?')}] {c.get('raw_content', '')[:1000]}"
        for c in chunks
    )
    additional = payload.get("additional_context", "")
    prompt = f"Conteudo do negocio ({len(chunks)} chunks):\n\n{chunks_text}"
    if additional:
        prompt += f"\n\n=== CONTEXTO ADICIONAL DO ONBOARDING ===\n{additional}"

    raw = await call_claude(
        prompt=prompt,
        system=_CLIENT_DNA_SYSTEM,
        model="claude-sonnet-4-6",
        client_id=client_id,
        task_id=task.get("id"),
        agent_id="system",
        purpose="extract_client_dna",
        max_tokens=2048,
    )

    dna = _parse_json_response(raw)
    if not dna:
        return {"error": "Falha ao parsear DNA extraido", "raw": raw[:500]}

    dna["extraction_meta"] = {
        "sources_used": list(set(c.get("source_type", "?") for c in chunks)),
        "chunks_analyzed": len(chunks),
        "confidence": "high" if len(chunks) >= 10 else "medium" if len(chunks) >= 3 else "low",
        "version": await _get_next_version(client_id),
    }

    update_data = {
        "client_dna": dna,
        "dna_updated_at": datetime.now(timezone.utc).isoformat(),
    }

    soul_prompt = None
    if payload.get("regenerate_prompt", True):
        soul_prompt = await _generate_soul_prompt_from_dna(dna, client_id, task.get("id"))
        if soul_prompt:
            update_data["soul_prompt_generated"] = soul_prompt

    await _update_zenya_client(client_id, update_data)

    # Persist individual DNA layers to client_dna table
    rows_inserted = await _persist_dna_layers(client_id, dna, chunks)

    # Mark processed chunks with dna_extraction stage
    await _mark_chunks_processed(client_id, chunks)

    return {
        "message": f"DNA extraido: {len(chunks)} chunks analisados, {_count_layers(dna)} camadas preenchidas",
        "client_id": client_id,
        "layers_filled": _count_layers(dna),
        "rows_inserted": rows_inserted,
        "confidence": dna["extraction_meta"]["confidence"],
        "soul_prompt_generated": soul_prompt is not None,
    }
