"""
Brain DNA router — SYS-4: endpoints para consulta de DNA de cliente.

GET /brain/client-dna/{client_id}  — retorna DNA completo de um cliente
"""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException

from runtime.db import supabase

router = APIRouter()


@router.get("/client-dna/{client_id}")
async def get_client_dna(client_id: str, dna_type: Optional[str] = None):
    """
    Retorna o DNA completo de um cliente, agrupado por dna_type.

    Query params:
        dna_type: filtrar por tipo especifico (identidade, tom_voz, etc.)
    """
    try:
        query = (
            supabase.table("client_dna")
            .select("id,client_id,dna_type,title,content,confidence,source_chunk_ids,tags,created_at,updated_at")
            .eq("client_id", client_id)
            .order("created_at", desc=True)
        )
        if dna_type:
            query = query.eq("dna_type", dna_type)

        result = await asyncio.to_thread(lambda: query.execute())
        rows = result.data or []

        if not rows:
            raise HTTPException(
                status_code=404,
                detail=f"Nenhum DNA encontrado para client_id={client_id}",
            )

        # Group by dna_type for structured response
        by_type: dict[str, list[dict]] = {}
        for row in rows:
            dt = row.get("dna_type", "unknown")
            by_type.setdefault(dt, []).append(row)

        # Compute overall confidence (average)
        confidences = [r.get("confidence", 0) for r in rows if r.get("confidence")]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0

        return {
            "status": "ok",
            "client_id": client_id,
            "layers_count": len(by_type),
            "total_entries": len(rows),
            "avg_confidence": round(avg_confidence, 2),
            "dna": by_type,
        }

    except HTTPException:
        raise
    except Exception as e:
        return {
            "status": "error",
            "error": f"Falha ao buscar client DNA: {str(e)[:300]}",
        }
