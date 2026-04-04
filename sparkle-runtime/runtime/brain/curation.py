"""
Brain Curation router -- B3-01: Quality > Volume.

Endpoints para Mauro revisar, aprovar ou rejeitar brain chunks via portal.
Chunks rejeitados sao excluidos de consultas Brain.

GET  /brain/curation/queue    -- fila de chunks pendentes de revisao
POST /brain/curation/{id}/approve  -- aprovar chunk
POST /brain/curation/{id}/reject   -- rejeitar chunk com motivo
GET  /brain/curation/stats    -- contadores e taxa de aprovacao
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from runtime.db import supabase

router = APIRouter()


# -- Request models --------------------------------------------------------

class RejectRequest(BaseModel):
    reason: Optional[str] = None


class ApproveRequest(BaseModel):
    note: Optional[str] = None


# -- GET /brain/curation/queue ---------------------------------------------

@router.get("/curation/queue")
async def curation_queue(
    status: str = "pending",
    limit: int = 20,
    offset: int = 0,
):
    """Lista chunks aguardando revisao (mais recentes primeiro)."""
    if status not in ("pending", "approved", "rejected"):
        raise HTTPException(status_code=400, detail="status deve ser pending, approved ou rejected")

    limit = min(limit, 50)

    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("brain_chunks")
            .select(
                "id,source_title,source_type,source_url,pipeline_type,"
                "raw_content,canonical_content,insight_narrative,"
                "chunk_metadata,created_at,brain_owner,"
                "curation_status,curation_note,curated_at,confidence_score"
            )
            .eq("curation_status", status)
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )

        chunks = result.data or []

        # Build preview for each chunk (first 200 chars of best content)
        for chunk in chunks:
            text = (
                chunk.get("canonical_content")
                or chunk.get("raw_content")
                or chunk.get("insight_narrative")
                or ""
            )
            chunk["content_preview"] = text[:200].strip()
            # Extract domain from metadata if available
            meta = chunk.get("chunk_metadata") or {}
            chunk["domain"] = meta.get("domain") or meta.get("canonical_domain") or "geral"

        return {
            "status": "ok",
            "count": len(chunks),
            "offset": offset,
            "chunks": chunks,
        }
    except Exception as e:
        return {"status": "error", "error": f"Falha ao buscar fila: {str(e)[:200]}"}


# -- POST /brain/curation/{chunk_id}/approve --------------------------------

@router.post("/curation/{chunk_id}/approve")
async def approve_chunk(chunk_id: str, body: ApproveRequest = ApproveRequest()):
    """Marca chunk como aprovado (qualidade validada)."""
    try:
        now = datetime.now(timezone.utc).isoformat()
        update_data: dict = {
            "curation_status": "approved",
            "curated_at": now,
        }
        if body.note:
            update_data["curation_note"] = body.note

        result = await asyncio.to_thread(
            lambda: supabase.table("brain_chunks")
            .update(update_data)
            .eq("id", chunk_id)
            .execute()
        )

        if not result.data:
            raise HTTPException(status_code=404, detail="Chunk nao encontrado")

        return {"status": "ok", "chunk_id": chunk_id, "curation_status": "approved"}

    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "error": f"Falha ao aprovar: {str(e)[:200]}"}


# -- POST /brain/curation/{chunk_id}/reject ---------------------------------

@router.post("/curation/{chunk_id}/reject")
async def reject_chunk(chunk_id: str, body: RejectRequest = RejectRequest()):
    """Marca chunk como rejeitado. Chunks rejeitados sao excluidos de consultas."""
    try:
        now = datetime.now(timezone.utc).isoformat()
        update_data: dict = {
            "curation_status": "rejected",
            "curated_at": now,
        }
        if body.reason:
            update_data["curation_note"] = body.reason

        result = await asyncio.to_thread(
            lambda: supabase.table("brain_chunks")
            .update(update_data)
            .eq("id", chunk_id)
            .execute()
        )

        if not result.data:
            raise HTTPException(status_code=404, detail="Chunk nao encontrado")

        return {"status": "ok", "chunk_id": chunk_id, "curation_status": "rejected"}

    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "error": f"Falha ao rejeitar: {str(e)[:200]}"}


# -- GET /brain/curation/stats ---------------------------------------------

@router.get("/curation/stats")
async def curation_stats():
    """Retorna contadores de curadoria e taxa de aprovacao."""
    try:
        pending_q, approved_q, rejected_q = await asyncio.gather(
            asyncio.to_thread(
                lambda: supabase.table("brain_chunks")
                .select("id", count="exact")
                .eq("curation_status", "pending")
                .limit(1)
                .execute()
            ),
            asyncio.to_thread(
                lambda: supabase.table("brain_chunks")
                .select("id", count="exact")
                .eq("curation_status", "approved")
                .limit(1)
                .execute()
            ),
            asyncio.to_thread(
                lambda: supabase.table("brain_chunks")
                .select("id", count="exact")
                .eq("curation_status", "rejected")
                .limit(1)
                .execute()
            ),
        )

        pending = pending_q.count if pending_q.count is not None else 0
        approved = approved_q.count if approved_q.count is not None else 0
        rejected = rejected_q.count if rejected_q.count is not None else 0
        total_reviewed = approved + rejected
        approval_rate = round((approved / total_reviewed * 100), 1) if total_reviewed > 0 else 0.0

        return {
            "status": "ok",
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "total": pending + total_reviewed,
            "approval_rate": approval_rate,
        }
    except Exception as e:
        return {"status": "error", "error": f"Falha ao buscar stats: {str(e)[:200]}"}
