"""
brain_ingest_pipeline handler — SYS-1.3: Pipeline unificada de ingestao Mega Brain.

Orquestra as 6 fases do Finch em sequencia:
  1. Raw Storage — obtem conteudo bruto e salva em brain_raw_ingestions
  2. Chunking Semantico — divide em chunks com overlap
  3. Canonicalizacao — substitui aliases por nomes canonicos
  4. Embedding — gera embedding vetorial via OpenAI
  5. DNA Extraction — classifica chunks em camadas de DNA (condicional)
  6. Narrative Synthesis — sintetiza narrativas de entidades (condicional)

Reutiliza funcoes existentes de ingest_url.py e brain_ingest.py.
Nao substitui handlers existentes — os orquestra.
"""
from __future__ import annotations

import asyncio
from typing import Optional

from runtime.brain.isolation import get_brain_owner_for_ingest
from runtime.config import settings
from runtime.db import supabase
from runtime.brain.embedding import get_embedding
from runtime.brain.ingest_url import (
    _chunk_text,
    _get_youtube_transcript,
    _get_url_content,
    _is_youtube,
)
from runtime.brain.dedup import check_duplicate_chunk, confirm_existing_chunk
from runtime.tasks.handlers.brain_ingest import canonicalize_entities


# ── Fase 1: Raw Storage ──────────────────────────────────────

async def _extract_from_source(source_type: str, source_ref: str) -> tuple[str, str]:
    """Extrai conteudo bruto conforme tipo de fonte. Retorna (texto, titulo)."""
    if source_type == "youtube" or _is_youtube(source_ref):
        return await _get_youtube_transcript(source_ref)
    else:
        return await _get_url_content(source_ref)


async def _save_raw(
    raw_text: str,
    title: str,
    payload: dict,
    task_id: Optional[str],
    client_id: Optional[str],
) -> Optional[str]:
    """Salva conteudo bruto completo em brain_raw_ingestions. Retorna o ID."""
    try:
        row = {
            "source_type": payload.get("source_type", "document"),
            "source_ref": payload.get("source_ref"),
            "title": title,
            "raw_content": raw_text,
            "pipeline_type": payload.get("persona", "mauro"),
            "metadata": {
                "source_agent": "brain_pipeline",
                "target_entity": payload.get("target_entity"),
                "run_dna": payload.get("run_dna", True),
                "run_narrative": payload.get("run_narrative", True),
            },
            "task_id": str(task_id) if task_id else None,
            "status": "processing",
        }
        if client_id and client_id != settings.sparkle_internal_client_id:
            row["client_id"] = client_id

        result = await asyncio.to_thread(
            lambda: supabase.table("brain_raw_ingestions").insert(row).execute()
        )
        raw_id = result.data[0]["id"] if result.data else None
        return raw_id
    except Exception as e:
        print(f"[brain_pipeline] falha ao salvar raw: {e}")
        return None


async def _update_raw_status(raw_id: str, status: str, chunks_generated: int = 0) -> None:
    """Atualiza status da ingestao raw."""
    try:
        update = {"status": status}
        if chunks_generated > 0:
            update["chunks_generated"] = chunks_generated
        await asyncio.to_thread(
            lambda: supabase.table("brain_raw_ingestions")
            .update(update)
            .eq("id", raw_id)
            .execute()
        )
    except Exception as e:
        print(f"[brain_pipeline] falha ao atualizar raw status: {e}")


# ── Fase 5: DNA Extraction (condicional) ─────────────────────

async def _run_extract_dna(
    chunk_ids: list[str],
    task_id: Optional[str],
    client_id: Optional[str],
) -> Optional[dict]:
    """Executa extract_dna inline para os chunks inseridos."""
    try:
        from runtime.tasks.handlers.extract_dna import handle_extract_dna
        fake_task = {
            "id": task_id,
            "client_id": client_id,
            "payload": {
                "source_chunk_ids": chunk_ids,
                "target_agent_id": "friday",
                "dry_run": False,
            },
        }
        result = await handle_extract_dna(fake_task)
        return {
            "processed": result.get("processed", 0),
            "inserted": result.get("inserted", 0),
            "layers_distribution": result.get("layers_distribution", {}),
        }
    except Exception as e:
        print(f"[brain_pipeline] DNA extraction falhou: {e}")
        return {"error": str(e)}


# ── Fase 6: Narrative Synthesis (condicional) ─────────────────

async def _run_narrative_synthesis(
    target_entity: Optional[str],
    task_id: Optional[str],
    client_id: Optional[str],
) -> Optional[dict]:
    """Executa narrative_synthesis inline se target_entity especificada."""
    if not target_entity:
        return None
    try:
        from runtime.tasks.handlers.narrative_synthesis import handle_narrative_synthesis
        fake_task = {
            "id": task_id,
            "client_id": client_id or settings.sparkle_internal_client_id,
            "payload": {
                "entity_name": target_entity,
                "min_chunks": 3,
            },
        }
        result = await handle_narrative_synthesis(fake_task)
        return {
            "processed": result.get("processed", 0),
            "updated": result.get("updated", 0),
            "skipped": result.get("skipped", 0),
        }
    except Exception as e:
        print(f"[brain_pipeline] narrative synthesis falhou: {e}")
        return {"error": str(e)}


# ── Fase 5b: Insight Extraction (condicional) ────────────────

async def _run_extract_insights(
    chunk_ids: list[str],
    raw_id: Optional[str],
    task_id: Optional[str],
    client_id: Optional[str],
) -> Optional[dict]:
    """Executa extract_insights inline para os chunks inseridos."""
    try:
        from runtime.tasks.handlers.extract_insights import handle_extract_insights
        fake_task = {
            "id": task_id,
            "client_id": client_id,
            "payload": {
                "source_chunk_ids": chunk_ids,
                "source_raw_ingestion_id": str(raw_id) if raw_id else None,
                "min_confidence": 0.6,
            },
        }
        result = await handle_extract_insights(fake_task)
        return {
            "processed": result.get("processed", 0),
            "inserted": result.get("inserted", 0),
            "domain_distribution": result.get("domain_distribution", {}),
        }
    except Exception as e:
        print(f"[brain_pipeline] Insight extraction falhou: {e}")
        return {"error": str(e)}


# ── Fase 6b: Cross-Source Synthesis (condicional) ────────────

async def _run_cross_source_synthesis(
    task_id: Optional[str],
    client_id: Optional[str],
) -> Optional[dict]:
    """Executa cross_source_synthesis para dominios com massa critica."""
    try:
        from runtime.tasks.handlers.cross_source_synthesis import handle_cross_source_synthesis
        fake_task = {
            "id": task_id,
            "client_id": client_id or settings.sparkle_internal_client_id,
            "payload": {
                "min_insights": 5,
            },
        }
        result = await handle_cross_source_synthesis(fake_task)
        return {
            "processed": result.get("processed", 0),
            "updated": result.get("updated", 0),
            "skipped": result.get("skipped", 0),
        }
    except Exception as e:
        print(f"[brain_pipeline] Cross-source synthesis falhou: {e}")
        return {"error": str(e)}


# ── Handler principal ─────────────────────────────────────────

async def handle_brain_ingest_pipeline(task: dict) -> dict:
    """
    Pipeline unificada de ingestao Mega Brain — 6 fases do Finch.
    """
    payload = task.get("payload", {})
    task_id = task.get("id")
    client_id = task.get("client_id")

    # ── FASE 1: Raw Storage — obter conteudo bruto ──
    try:
        if payload.get("source_ref"):
            raw_text, title = await _extract_from_source(
                source_type=payload.get("source_type", "url"),
                source_ref=payload["source_ref"],
            )
        else:
            raw_text = payload.get("raw_content", "")
            title = payload.get("title", "direct_input")
    except Exception as e:
        return {"error": f"Fase 1 (extracao) falhou: {e}"}

    if not raw_text or len(raw_text) < 50:
        return {"error": "Conteudo muito curto para ingestao (minimo 50 chars)"}

    # Salva raw completo em brain_raw_ingestions
    raw_id = await _save_raw(raw_text, title, payload, task_id, client_id)

    # ── FASE 2: Chunking Semantico ──
    chunks = _chunk_text(raw_text, chunk_size=1500, overlap=200)

    # ── FASE 3 + 4: Canonicalizacao + Embedding por chunk (com dedup) ──
    chunk_ids: list[str] = []
    duplicates_confirmed = 0
    effective_client_id = client_id or settings.sparkle_internal_client_id

    for i, chunk_text in enumerate(chunks):
        try:
            # Fase 3: Canonicalizacao
            canonical, entity_tags = await canonicalize_entities(
                chunk_text, effective_client_id
            )

            # Fase 4: Embedding
            embedding = await get_embedding(canonical or chunk_text)

            # Dedup: verifica se chunk similar ja existe
            if embedding:
                existing = await check_duplicate_chunk(embedding)
                if existing:
                    print(
                        f"[brain/dedup] chunk similar encontrado "
                        f"(similarity={existing['similarity']:.4f}), "
                        f"confirmando existente {existing['id']}"
                    )
                    await confirm_existing_chunk(existing["id"])
                    duplicates_confirmed += 1
                    continue

            # B1-03: resolve brain_owner for this pipeline ingest.
            # When persona="cliente" and client_id is present, the brain_owner must
            # be the client_id so that extract_client_dna can find these chunks via
            # brain_owner filter. Pass "zenya_client" so isolation routes to client_id.
            if client_id and payload.get("persona") == "cliente":
                brain_owner = client_id
            else:
                brain_owner = get_brain_owner_for_ingest(
                    "brain_pipeline", client_id,
                )

            # Insere em brain_chunks
            row: dict = {
                "raw_content": chunk_text,
                "canonical_content": canonical if canonical != chunk_text else None,
                "source_type": payload.get("source_type", "document"),
                "source_title": (
                    f"{title} (chunk {i+1}/{len(chunks)})"
                    if len(chunks) > 1
                    else title
                ),
                "pipeline_type": payload.get("persona", "mauro"),
                "brain_owner": brain_owner,
                "chunk_metadata": {
                    "source_ref": payload.get("source_ref"),
                    "source_agent": "brain_pipeline",
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "entity_tags": entity_tags,
                    "raw_ingestion_id": str(raw_id) if raw_id else None,
                },
            }
            if client_id and client_id != settings.sparkle_internal_client_id:
                row["client_id"] = client_id
            if embedding:
                row["embedding"] = embedding
            if raw_id:
                row["raw_ingestion_id"] = raw_id

            result = await asyncio.to_thread(
                lambda r=row: supabase.table("brain_chunks").insert(r).execute()
            )
            if result.data:
                chunk_ids.append(result.data[0]["id"])
        except Exception as e:
            print(f"[brain_pipeline] falha chunk {i}: {e}")

    # Atualiza status do raw
    if raw_id:
        await _update_raw_status(
            raw_id,
            status="completed" if chunk_ids else "failed",
            chunks_generated=len(chunk_ids),
        )

    if not chunk_ids:
        return {"error": "Nenhum chunk inserido com sucesso"}

    # ── FASE 5a: DNA Extraction (condicional) ──
    dna_stats = None
    if payload.get("run_dna", True) and chunk_ids:
        dna_stats = await _run_extract_dna(chunk_ids, task_id, client_id)

    # ── FASE 5b: Insight Extraction (condicional) ──
    insight_stats = None
    if payload.get("run_insights", True) and chunk_ids:
        insight_stats = await _run_extract_insights(
            chunk_ids, raw_id, task_id, client_id,
        )

    # ── FASE 6a: Narrative Synthesis (condicional) ──
    narrative_stats = None
    if payload.get("run_narrative", True):
        narrative_stats = await _run_narrative_synthesis(
            target_entity=payload.get("target_entity"),
            task_id=task_id,
            client_id=client_id,
        )

    # ── FASE 6b: Cross-Source Synthesis (condicional) ──
    synthesis_stats = None
    if payload.get("run_synthesis", True) and insight_stats and insight_stats.get("inserted", 0) > 0:
        synthesis_stats = await _run_cross_source_synthesis(task_id, client_id)

    result = {
        "message": (
            f"Pipeline Mega Brain completa: {len(chunk_ids)} chunks novos, "
            f"{duplicates_confirmed} duplicatas confirmadas de '{title}'"
        ),
        "raw_ingestion_id": str(raw_id) if raw_id else None,
        "chunks_inserted": len(chunk_ids),
        "duplicates_confirmed": duplicates_confirmed,
        "chunk_ids": [str(cid) for cid in chunk_ids],
        "total_text_length": len(raw_text),
        "dna": dna_stats,
        "insights": insight_stats,
        "narrative": narrative_stats,
        "synthesis": synthesis_stats,
        "brain_worthy": True,
        "brain_content": (
            f"Pipeline de ingestao concluida: '{title}' — "
            f"{len(chunk_ids)} chunks, source={payload.get('source_type', 'document')}"
        ),
    }

    # SYS-4: quando persona=cliente + client_id, run extract_client_dna inline
    client_dna_stats = None
    if client_id and payload.get("persona") == "cliente" and chunk_ids:
        try:
            from runtime.tasks.handlers.extract_client_dna import handle_extract_client_dna
            dna_task = {
                "id": task_id,
                "payload": {
                    "client_id": client_id,
                    "regenerate_prompt": True,
                },
            }
            client_dna_stats = await handle_extract_client_dna(dna_task)
            print(f"[brain_pipeline] SYS-4 client DNA extracted: {client_dna_stats.get('items_extracted', 0)} items")
        except Exception as e:
            print(f"[brain_pipeline] SYS-4 client DNA extraction failed: {e}")
            client_dna_stats = {"error": str(e)[:200]}

    if client_dna_stats:
        result["client_dna"] = client_dna_stats

    return result
