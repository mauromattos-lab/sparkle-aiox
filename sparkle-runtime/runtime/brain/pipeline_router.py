"""
Brain Pipeline router — SYS-1.4 + SYS-1.5: endpoints de ingestao pipeline e consulta.

POST /brain/ingest-pipeline   — dispara pipeline completa de 6 fases
GET  /brain/ingestions        — lista ingestoes recentes com stats
GET  /brain/ingestions/{id}   — detalhe de uma ingestao com chunks gerados
GET  /brain/activity          — dashboard consolidado Brain Activity (Mission Control)
"""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from runtime.config import settings
from runtime.db import supabase

router = APIRouter()


# ── Request models ────────────────────────────────────────────

class IngestPipelineRequest(BaseModel):
    source_type: str = "document"  # youtube | pdf_text | url | transcript | conversation | document
    source_ref: Optional[str] = None  # URL ou referencia externa
    raw_content: Optional[str] = None  # conteudo direto (quando source_ref nao aplicavel)
    title: Optional[str] = "direct_input"
    persona: Optional[str] = "mauro"  # namespace: mauro | especialista | cliente
    client_id: Optional[str] = None  # null = sparkle-internal
    target_entity: Optional[str] = None  # entidade principal (para narrative synthesis)
    run_dna: bool = True  # se deve rodar extract_dna ao final
    run_narrative: bool = True  # se deve rodar narrative_synthesis


# ── POST /brain/ingest-pipeline ───────────────────────────────

@router.post("/ingest-pipeline")
async def ingest_pipeline(req: IngestPipelineRequest):
    """
    Dispara pipeline completa de ingestao Mega Brain (6 fases do Finch).
    Executa inline — retorna resultado completo ao finalizar.
    """
    if not req.source_ref and not req.raw_content:
        raise HTTPException(
            status_code=400,
            detail="Informe source_ref (URL) ou raw_content (texto direto)",
        )

    # Cria task no Supabase e executa inline
    try:
        from runtime.tasks.worker import execute_task

        task_result = await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks").insert({
                "agent_id": "brain",
                "client_id": req.client_id or settings.sparkle_internal_client_id,
                "task_type": "brain_ingest_pipeline",
                "payload": {
                    "source_type": req.source_type,
                    "source_ref": req.source_ref,
                    "raw_content": req.raw_content,
                    "title": req.title,
                    "persona": req.persona,
                    "target_entity": req.target_entity,
                    "run_dna": req.run_dna,
                    "run_narrative": req.run_narrative,
                },
                "status": "pending",
                "priority": 7,
            }).execute()
        )

        task_record = task_result.data[0] if task_result.data else {}
        await execute_task(task_record)

        # Busca resultado da task executada
        if task_record.get("id"):
            result = await asyncio.to_thread(
                lambda: supabase.table("runtime_tasks")
                .select("result,status,error")
                .eq("id", task_record["id"])
                .single()
                .execute()
            )
            task_data = result.data or {}
            if task_data.get("status") == "done":
                return {
                    "status": "ok",
                    "task_id": task_record["id"],
                    **(task_data.get("result") or {}),
                }
            else:
                return {
                    "status": "error",
                    "task_id": task_record["id"],
                    "error": task_data.get("error", "Pipeline falhou"),
                }

        return {"status": "error", "error": "Task nao criada"}

    except Exception as e:
        return {"status": "error", "error": f"Erro inesperado: {str(e)[:300]}"}


# ── GET /brain/ingestions ─────────────────────────────────────

@router.get("/ingestions")
async def list_ingestions(
    limit: int = 20,
    source_type: Optional[str] = None,
):
    """Lista ingestoes recentes com stats."""
    try:
        query = (
            supabase.table("brain_raw_ingestions")
            .select("id,source_type,source_ref,title,pipeline_type,status,chunks_generated,created_at")
            .order("created_at", desc=True)
            .limit(min(limit, 50))
        )
        if source_type:
            query = query.eq("source_type", source_type)

        result = await asyncio.to_thread(lambda: query.execute())
        return {
            "status": "ok",
            "count": len(result.data or []),
            "ingestions": result.data or [],
        }
    except Exception as e:
        return {"status": "error", "error": f"Falha ao listar ingestoes: {str(e)[:200]}"}


# ── GET /brain/ingestions/{ingestion_id} ──────────────────────

@router.get("/ingestions/{ingestion_id}")
async def get_ingestion(ingestion_id: str):
    """Detalhe de uma ingestao com chunks gerados."""
    try:
        # Busca a ingestao
        raw_result = await asyncio.to_thread(
            lambda: supabase.table("brain_raw_ingestions")
            .select("*")
            .eq("id", ingestion_id)
            .single()
            .execute()
        )
        ingestion = raw_result.data
        if not ingestion:
            raise HTTPException(status_code=404, detail="Ingestao nao encontrada")

        # Busca chunks associados (via raw_ingestion_id ou chunk_metadata)
        chunks_data = []
        try:
            chunks_result = await asyncio.to_thread(
                lambda: supabase.table("brain_chunks")
                .select("id,source_title,source_type,pipeline_type,chunk_metadata,created_at")
                .eq("raw_ingestion_id", ingestion_id)
                .order("created_at")
                .limit(100)
                .execute()
            )
            chunks_data = chunks_result.data or []
        except Exception:
            # raw_ingestion_id column might not exist yet — fallback silencioso
            pass

        # Remove raw_content do response para nao poluir (pode ser enorme)
        ingestion_summary = {
            k: v for k, v in ingestion.items()
            if k != "raw_content"
        }
        ingestion_summary["raw_content_length"] = len(ingestion.get("raw_content", ""))

        return {
            "status": "ok",
            "ingestion": ingestion_summary,
            "chunks": chunks_data,
            "chunks_count": len(chunks_data),
        }
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "error": f"Falha ao buscar ingestao: {str(e)[:200]}"}


# ── GET /brain/activity ──────────────────────────────────────

@router.get("/activity")
async def brain_activity():
    """
    Dashboard consolidado de atividade do Brain para o Mission Control.

    Retorna processing queue, ingestoes recentes, insights, sinteses e stats.
    """
    try:
        # Run all queries in parallel
        (
            processing_result,
            recent_result,
            insights_recent_result,
            insights_count_result,
            syntheses_result,
            chunks_count_result,
        ) = await asyncio.gather(
            # Tasks brain_ingest_pipeline pending/running
            asyncio.to_thread(
                lambda: supabase.table("runtime_tasks")
                .select("id,task_type,status,payload,created_at,updated_at")
                .eq("task_type", "brain_ingest_pipeline")
                .in_("status", ["pending", "running"])
                .order("created_at", desc=True)
                .limit(20)
                .execute()
            ),
            # Recent completed brain tasks
            asyncio.to_thread(
                lambda: supabase.table("runtime_tasks")
                .select("id,task_type,status,payload,result,created_at,completed_at")
                .eq("task_type", "brain_ingest_pipeline")
                .eq("status", "done")
                .order("completed_at", desc=True)
                .limit(10)
                .execute()
            ),
            # Recent insights
            asyncio.to_thread(
                lambda: supabase.table("brain_insights")
                .select("id,domain,insight_type,content,source_chunk_ids,created_at")
                .order("created_at", desc=True)
                .limit(10)
                .execute()
            ),
            # Total insights count
            asyncio.to_thread(
                lambda: supabase.table("brain_insights")
                .select("id,domain", count="exact")
                .limit(1)
                .execute()
            ),
            # Active domain syntheses
            asyncio.to_thread(
                lambda: supabase.table("brain_domain_syntheses")
                .select("id,domain,version,source_count,synthesis,created_at,updated_at")
                .eq("active", True)
                .order("updated_at", desc=True)
                .limit(20)
                .execute()
            ),
            # Total chunks count
            asyncio.to_thread(
                lambda: supabase.table("brain_chunks")
                .select("id", count="exact")
                .limit(1)
                .execute()
            ),
        )

        # Build insights by_domain from recent insights
        insights_by_domain: dict[str, int] = {}
        for insight in (insights_recent_result.data or []):
            domain = insight.get("domain", "unknown")
            insights_by_domain[domain] = insights_by_domain.get(domain, 0) + 1

        # Also try a dedicated domain count query (best effort)
        try:
            all_insights_for_domain = await asyncio.to_thread(
                lambda: supabase.table("brain_insights")
                .select("domain")
                .limit(500)
                .execute()
            )
            domain_counts: dict[str, int] = {}
            for row in (all_insights_for_domain.data or []):
                d = row.get("domain", "unknown")
                domain_counts[d] = domain_counts.get(d, 0) + 1
            insights_by_domain = domain_counts
        except Exception:
            pass  # fallback to the limited count above

        insights_total = insights_count_result.count if insights_count_result.count is not None else len(insights_count_result.data or [])
        chunks_total = chunks_count_result.count if chunks_count_result.count is not None else len(chunks_count_result.data or [])

        # Extract title/URL from payload for processing tasks
        processing_items = []
        for task in (processing_result.data or []):
            payload = task.get("payload") or {}
            processing_items.append({
                "id": task.get("id"),
                "title": payload.get("title", ""),
                "source_ref": payload.get("source_ref", ""),
                "source_type": payload.get("source_type", ""),
                "status": task.get("status"),
                "created_at": task.get("created_at"),
                "updated_at": task.get("updated_at"),
            })

        # Extract info from recent completed tasks
        recent_items = []
        for task in (recent_result.data or []):
            payload = task.get("payload") or {}
            result = task.get("result") or {}
            recent_items.append({
                "id": task.get("id"),
                "title": payload.get("title", ""),
                "source_ref": payload.get("source_ref", ""),
                "source_type": payload.get("source_type", ""),
                "chunks_inserted": result.get("chunks_inserted", 0),
                "insights_extracted": result.get("insights_extracted", 0),
                "completed_at": task.get("completed_at"),
                "created_at": task.get("created_at"),
            })

        # Syntheses — trim the full synthesis text for the dashboard
        syntheses_items = []
        for syn in (syntheses_result.data or []):
            synthesis_text = syn.get("synthesis", "")
            syntheses_items.append({
                "id": syn.get("id"),
                "domain": syn.get("domain"),
                "version": syn.get("version"),
                "source_count": syn.get("source_count"),
                "synthesis_preview": synthesis_text[:200] if synthesis_text else "",
                "created_at": syn.get("created_at"),
                "updated_at": syn.get("updated_at"),
            })

        return {
            "processing": processing_items,
            "recent": recent_items,
            "insights": {
                "total": insights_total,
                "recent": insights_recent_result.data or [],
                "by_domain": insights_by_domain,
            },
            "syntheses": syntheses_items,
            "stats": {
                "chunks_total": chunks_total,
                "insights_total": insights_total,
                "domains_with_synthesis": len(syntheses_result.data or []),
            },
        }

    except Exception as e:
        return {"status": "error", "error": f"Falha ao buscar brain activity: {str(e)[:300]}"}
