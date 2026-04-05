"""
B2-04: extract_client_dna handler — extrai DNA estruturado do cliente
a partir de chunks do Brain usando Claude Haiku (cost-efficient).

8 categorias:
  tom, persona, regras, diferenciais, publico_alvo, produtos, objecoes, faq

Cada item extraido vira uma row em client_dna com:
  - dna_type (categoria)
  - key (identificador curto do item)
  - title (titulo legivel)
  - content (conteudo completo)
  - confidence (0-1 do LLM)
  - source_chunk_ids (quais chunks geraram o item)

Tambem atualiza zenya_clients.client_dna (JSON blob) e opcionalmente
gera soul_prompt.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from runtime.config import settings
from runtime.db import supabase
from runtime.utils.llm import call_claude


# ── DNA categories ────────────────────────────────────────────
DNA_CATEGORIES = (
    "tom", "persona", "regras", "diferenciais",
    "publico_alvo", "produtos", "objecoes", "faq",
)

_CATEGORY_DESCRIPTIONS = {
    "tom": "Tom de comunicacao: formalidade, emojis, estilo, tratamento, exemplos de frases tipicas",
    "persona": "Personalidade da marca: identidade, valores, posicionamento, como se apresenta",
    "regras": "Regras de negocio: horarios, prazos, politicas, restricoes operacionais",
    "diferenciais": "Diferenciais competitivos: o que diferencia o negocio (max 5 itens)",
    "publico_alvo": "Publico-alvo: perfil demografico, dores, desejos, comportamentos",
    "produtos": "Produtos e servicos: catalogo, precos, categorias, destaques",
    "objecoes": "Objecoes comuns: duvidas frequentes dos clientes, resistencias de compra",
    "faq": "FAQ: perguntas e respostas frequentes sobre o negocio",
}

# ── System prompts ────────────────────────────────────────────
_EXTRACT_SYSTEM = """Voce extrai o DNA de um negocio a partir de conteudo ingerido (site, Instagram, conversas, documentos).

Seu objetivo: gerar um perfil granular e estruturado que permita a uma IA de atendimento
conversar com os clientes desse negocio de forma natural e precisa.

Voce recebera chunks de conteudo do negocio. Para CADA uma das 8 categorias abaixo,
extraia MULTIPLOS itens quando o conteudo permitir:

CATEGORIAS:
- tom: {tom}
- persona: {persona}
- regras: {regras}
- diferenciais: {diferenciais}
- publico_alvo: {publico_alvo}
- produtos: {produtos}
- objecoes: {objecoes}
- faq: {faq}

Responda APENAS com JSON valido no formato:
{{
  "items": [
    {{
      "category": "tom",
      "key": "estilo_informal",
      "title": "Estilo informal e acolhedor",
      "content": "Descricao detalhada...",
      "confidence": 0.85
    }},
    ...mais itens...
  ],
  "summary": "Resumo em 1-2 frases do perfil geral do negocio"
}}

REGRAS:
- Extraia apenas o que o conteudo EVIDENCIA. Nao invente.
- O campo 'key' deve ser um identificador curto em snake_case (ex: horario_atendimento, produto_principal)
- O campo 'confidence' eh um float de 0.0 a 1.0 indicando quao forte eh a evidencia
- Se uma categoria nao tem evidencia, simplesmente nao inclua itens dela
- Prefira mais itens granulares a poucos itens genericos
- Cada item deve ser autocontido — outro sistema vai usar isoladamente
""".format(**_CATEGORY_DESCRIPTIONS)


_SOUL_PROMPT_SYSTEM = """Voce gera system prompts para a Zenya, uma assistente de atendimento via WhatsApp.

Dado o DNA estruturado de um negocio (lista de itens por categoria), gere um system prompt
completo que inclua:

1. IDENTIDADE: quem a Zenya eh neste contexto (nome do negocio, o que faz)
2. TOM DE VOZ: como deve falar (baseado nos itens de 'tom' e 'persona')
3. REGRAS: o que sabe responder, horarios, politicas (baseado em 'regras')
4. PRODUTOS: como apresentar os produtos/servicos
5. DIFERENCIAIS: como apresentar o negocio quando perguntada
6. FAQ: respostas para perguntas frequentes
7. OBJECOES: como lidar com objecoes comuns
8. ESCALAMENTO: quando passar para humano (duvidas fora do escopo, reclamacoes, pedidos complexos)

O prompt deve ser direto, em segunda pessoa ("voce eh..."), sem markdown, max 2000 caracteres.
Nao inclua instrucoes sobre como usar — apenas o prompt em si."""


# ── Helpers ───────────────────────────────────────────────────

def _parse_json_response(raw: str) -> dict | None:
    """Parse JSON from LLM response, stripping markdown fences if present."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


async def _get_client_chunks(client_id: str, limit: int = 60) -> list[dict]:
    """Fetch content for DNA extraction from brain_chunks AND zenya_knowledge_base.

    Search order:
    1. brain_chunks by brain_owner
    2. brain_chunks by client_id (UUID)
    3. zenya_knowledge_base (product catalog / KB entries)
    """
    # 1. brain_chunks by brain_owner
    result = await asyncio.to_thread(
        lambda: supabase.table("brain_chunks")
        .select("id,raw_content,source_type,source_title,chunk_metadata")
        .eq("brain_owner", client_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    chunks = result.data or []

    # 2. brain_chunks by client_id UUID
    if not chunks:
        try:
            result = await asyncio.to_thread(
                lambda: supabase.table("brain_chunks")
                .select("id,raw_content,source_type,source_title,chunk_metadata")
                .eq("client_id", client_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            chunks = result.data or []
        except Exception:
            pass

    # 3. zenya_knowledge_base — convert KB entries to chunk-like dicts
    if not chunks:
        try:
            kb_result = await asyncio.to_thread(
                lambda: supabase.table("zenya_knowledge_base")
                .select("id,category,item_name,description,price,price_unit,additional_info")
                .eq("client_id", client_id)
                .eq("active", True)
                .limit(limit)
                .execute()
            )
            kb_rows = kb_result.data or []
            for row in kb_rows:
                parts = [f"[{row.get('category', '')}] {row.get('item_name', '')}"]
                if row.get("description"):
                    parts.append(row["description"])
                if row.get("price"):
                    unit = row.get("price_unit", "R$")
                    parts.append(f"Preco: {unit} {row['price']}")
                if row.get("additional_info"):
                    parts.append(row["additional_info"])
                chunks.append({
                    "id": str(row["id"]),
                    "raw_content": " | ".join(parts),
                    "source_type": "knowledge_base",
                    "source_title": row.get("item_name", ""),
                    "chunk_metadata": {"category": row.get("category", "")},
                })
        except Exception:
            pass

    return chunks


async def _get_next_version(client_id: str) -> int:
    """Get next DNA version number from zenya_clients."""
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
    """Update zenya_clients record with new DNA data."""
    await asyncio.to_thread(
        lambda: supabase.table("zenya_clients")
        .update(update_data)
        .eq("client_id", client_id)
        .execute()
    )


async def _extract_dna_from_chunks(
    chunks: list[dict],
    client_id: str,
    task_id: str | None,
    additional_context: str = "",
) -> dict | None:
    """Call Haiku to extract DNA items from chunks."""
    chunks_text = "\n\n---\n\n".join(
        f"[{c.get('source_type', '?')}] {c.get('source_title', 'sem titulo')}\n{c.get('raw_content', '')[:1200]}"
        for c in chunks
    )

    prompt = f"Conteudo do negocio ({len(chunks)} chunks):\n\n{chunks_text}"
    if additional_context:
        prompt += f"\n\n=== CONTEXTO ADICIONAL DO ONBOARDING ===\n{additional_context}"

    raw = await call_claude(
        prompt=prompt,
        system=_EXTRACT_SYSTEM,
        model="claude-haiku-4-5-20251001",
        client_id=client_id,
        task_id=task_id,
        agent_id="system",
        purpose="extract_client_dna",
        max_tokens=4096,
    )

    return _parse_json_response(raw)


async def _persist_dna_items(
    client_id: str,
    items: list[dict],
    chunk_ids: list[str],
) -> int:
    """Persist extracted DNA items to client_dna table.

    Deletes previous DNA rows for the client, then inserts new ones.
    Returns number of rows inserted.
    """
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

    # Build title map for human-readable titles
    title_map = {
        "tom": "Tom de Comunicacao",
        "persona": "Personalidade da Marca",
        "regras": "Regras de Negocio",
        "diferenciais": "Diferenciais",
        "publico_alvo": "Publico-Alvo",
        "produtos": "Produtos e Servicos",
        "objecoes": "Objecoes Comuns",
        "faq": "FAQ",
    }

    rows = []
    for item in items:
        category = item.get("category", "")
        if category not in DNA_CATEGORIES:
            continue

        content = item.get("content", "")
        if isinstance(content, (dict, list)):
            content = json.dumps(content, ensure_ascii=False)

        confidence = item.get("confidence", 0.5)
        if not isinstance(confidence, (int, float)):
            confidence = 0.5
        confidence = max(0.0, min(1.0, float(confidence)))

        rows.append({
            "client_id": client_id,
            "dna_type": category,
            "key": item.get("key", category),
            "title": item.get("title", title_map.get(category, category)),
            "content": content,
            "confidence": confidence,
            "source_chunk_ids": chunk_ids[:50],
            "tags": [category],
            "extracted_at": now,
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
        print(f"[extract_client_dna] falha ao persistir DNA items: {e}")
        return 0


async def _generate_soul_prompt_from_items(
    items: list[dict],
    client_id: str,
    task_id: str | None,
) -> str | None:
    """Generate a soul_prompt from the extracted DNA items."""
    # Group items by category for the prompt
    by_category: dict[str, list[dict]] = {}
    for item in items:
        cat = item.get("category", "unknown")
        by_category.setdefault(cat, []).append(item)

    prompt = f"DNA do negocio (client_id={client_id}):\n\n"
    for cat in DNA_CATEGORIES:
        cat_items = by_category.get(cat, [])
        if cat_items:
            prompt += f"\n## {cat.upper()}\n"
            for it in cat_items:
                prompt += f"- [{it.get('key', '?')}] {it.get('content', '')}\n"

    try:
        soul = await call_claude(
            prompt=prompt,
            system=_SOUL_PROMPT_SYSTEM,
            model="claude-haiku-4-5-20251001",
            client_id=client_id,
            task_id=task_id,
            agent_id="system",
            purpose="generate_soul_prompt",
            max_tokens=2048,
        )
        return soul.strip() if soul else None
    except Exception as e:
        print(f"[extract_client_dna] falha ao gerar soul_prompt: {e}")
        return None


async def _mark_chunks_processed(chunks: list[dict]) -> None:
    """Mark chunks as having gone through dna_extraction stage."""
    for chunk in chunks:
        chunk_id = chunk.get("id")
        if not chunk_id:
            continue
        try:
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
            pass


def _count_categories(items: list[dict]) -> dict[str, int]:
    """Count items per category."""
    counts: dict[str, int] = {}
    for item in items:
        cat = item.get("category", "unknown")
        counts[cat] = counts.get(cat, 0) + 1
    return counts


# ── Main handler ──────────────────────────────────────────────

async def handle_extract_all_client_dna(task: dict) -> dict:
    """
    Batch extraction: extract DNA for ALL active zenya_clients that have brain chunks.

    Payload (optional):
        regenerate_prompt (bool): generate soul_prompt per client (default True)

    Iterates zenya_clients where active=true, checks for brain_chunks,
    and runs handle_extract_client_dna for each.
    """
    payload = task.get("payload", {})
    regenerate = payload.get("regenerate_prompt", True)

    # Fetch all active zenya_clients
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("zenya_clients")
            .select("client_id,business_name")
            .eq("active", True)
            .execute()
        )
        clients = result.data or []
    except Exception as e:
        return {"error": f"Falha ao buscar clientes: {e}"}

    if not clients:
        return {"message": "Nenhum cliente ativo encontrado em zenya_clients"}

    results = []
    success = 0
    skipped = 0
    errors = 0

    for client in clients:
        cid = client.get("client_id")
        name = client.get("business_name", cid)

        # Check if client has brain chunks before calling extraction
        chunks = await _get_client_chunks(cid, limit=1)
        if not chunks:
            skipped += 1
            results.append({"client_id": cid, "business_name": name, "status": "skipped", "reason": "no_chunks"})
            continue

        sub_task = {
            "id": task.get("id"),
            "payload": {
                "client_id": cid,
                "regenerate_prompt": regenerate,
            },
        }

        try:
            r = await handle_extract_client_dna(sub_task)
            if "error" in r:
                errors += 1
                results.append({"client_id": cid, "business_name": name, "status": "error", "error": r["error"]})
            else:
                success += 1
                results.append({
                    "client_id": cid,
                    "business_name": name,
                    "status": "ok",
                    "items_extracted": r.get("items_extracted", 0),
                })
        except Exception as e:
            errors += 1
            results.append({"client_id": cid, "business_name": name, "status": "error", "error": str(e)[:200]})

    return {
        "message": f"Batch DNA extraction: {success} ok, {skipped} skipped, {errors} errors de {len(clients)} clientes",
        "total_clients": len(clients),
        "success": success,
        "skipped": skipped,
        "errors": errors,
        "details": results,
    }


async def handle_extract_client_dna(task: dict) -> dict:
    """
    Extrai DNA do cliente a partir de chunks do Brain usando Haiku.

    Payload:
        client_id (str): required
        additional_context (str): optional extra context from onboarding
        regenerate_prompt (bool): generate soul_prompt (default True)
        categories (list[str]): optional filter — only extract these categories

    Flow:
        1. Fetch brain_chunks for client
        2. Send to Haiku for granular extraction (8 categories)
        3. Persist each item as a row in client_dna
        4. Update zenya_clients.client_dna JSON blob
        5. Optionally generate soul_prompt
        6. Mark chunks as processed
    """
    payload = task.get("payload", {})
    client_id = payload.get("client_id")

    if not client_id:
        return {"error": "client_id obrigatorio"}

    # 1. Fetch chunks
    chunks = await _get_client_chunks(client_id, limit=60)
    if not chunks:
        return {"error": f"Nenhum chunk encontrado no Brain para client_id={client_id}"}

    # 2. Extract DNA via Haiku
    additional = payload.get("additional_context", "")
    result = await _extract_dna_from_chunks(chunks, client_id, task.get("id"), additional)

    if not result or not result.get("items"):
        return {
            "error": "Falha ao extrair DNA — LLM nao retornou items validos",
            "raw_keys": list(result.keys()) if result else None,
        }

    items = result["items"]
    summary = result.get("summary", "")

    # Filter by requested categories if specified
    requested_cats = payload.get("categories")
    if requested_cats:
        items = [i for i in items if i.get("category") in requested_cats]

    # 3. Persist to client_dna table
    chunk_ids = [c.get("id") for c in chunks if c.get("id")]
    rows_inserted = await _persist_dna_items(client_id, items, chunk_ids)

    # 4. Update zenya_clients JSON blob
    category_counts = _count_categories(items)
    version = await _get_next_version(client_id)

    dna_blob = {
        "summary": summary,
        "categories": category_counts,
        "extraction_meta": {
            "sources_used": list(set(c.get("source_type", "?") for c in chunks)),
            "chunks_analyzed": len(chunks),
            "items_extracted": len(items),
            "confidence": "high" if len(chunks) >= 10 else "medium" if len(chunks) >= 3 else "low",
            "version": version,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        },
    }

    update_data = {
        "client_dna": dna_blob,
        "dna_updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # 5. Generate soul_prompt
    soul_prompt = None
    if payload.get("regenerate_prompt", True):
        soul_prompt = await _generate_soul_prompt_from_items(items, client_id, task.get("id"))
        if soul_prompt:
            update_data["soul_prompt_generated"] = soul_prompt

    try:
        await _update_zenya_client(client_id, update_data)
    except Exception as e:
        print(f"[extract_client_dna] falha ao atualizar zenya_clients: {e}")

    # 6. Mark chunks processed
    await _mark_chunks_processed(chunks)

    return {
        "message": (
            f"DNA extraido: {len(chunks)} chunks analisados, "
            f"{len(items)} items extraidos em {len(category_counts)} categorias"
        ),
        "client_id": client_id,
        "items_extracted": len(items),
        "rows_inserted": rows_inserted,
        "categories": category_counts,
        "confidence": dna_blob["extraction_meta"]["confidence"],
        "version": version,
        "summary": summary,
        "soul_prompt_generated": soul_prompt is not None,
    }
