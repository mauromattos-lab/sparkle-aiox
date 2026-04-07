"""
Brain DNA router — B2-04: endpoints para consulta e extracao de DNA de cliente.

GET  /brain/client-dna/{client_id}       — retorna DNA completo de um cliente
POST /brain/extract-dna/{client_id}      — dispara extracao de DNA a partir dos chunks
"""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from runtime.db import supabase
from runtime.tasks.handlers.extract_client_dna import (
    handle_extract_client_dna,
    DNA_CATEGORIES,
)

router = APIRouter()


# ── Models ────────────────────────────────────────────────────

class ExtractDNARequest(BaseModel):
    additional_context: Optional[str] = None
    regenerate_prompt: bool = True
    categories: Optional[list[str]] = None


# ── GET: query existing DNA ───────────────────────────────────

@router.get("/client-dna/{client_id}")
async def get_client_dna(client_id: str, dna_type: Optional[str] = None):
    """
    Retorna o DNA completo de um cliente, agrupado por dna_type.

    Query params:
        dna_type: filtrar por tipo especifico (tom, persona, regras, etc.)
    """
    try:
        query = (
            supabase.table("client_dna")
            .select("id,client_id,dna_type,key,title,content,confidence,source_chunk_ids,tags,extracted_at,created_at,updated_at")
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
            "categories_count": len(by_type),
            "total_items": len(rows),
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


# ── POST: trigger extraction ─────────────────────────────────

@router.post("/extract-dna/{client_id}")
async def extract_client_dna(client_id: str, body: Optional[ExtractDNARequest] = None):
    """
    Dispara extracao de DNA do cliente a partir dos chunks do Brain.

    Usa Claude Haiku para extrair itens granulares em 8 categorias:
    tom, persona, regras, diferenciais, publico_alvo, produtos, objecoes, faq.

    Body (optional):
        additional_context: contexto extra do onboarding
        regenerate_prompt: gerar soul_prompt (default true)
        categories: filtrar categorias especificas
    """
    payload: dict = {"client_id": client_id}

    if body:
        if body.additional_context:
            payload["additional_context"] = body.additional_context
        payload["regenerate_prompt"] = body.regenerate_prompt
        if body.categories:
            # Validate categories
            invalid = [c for c in body.categories if c not in DNA_CATEGORIES]
            if invalid:
                raise HTTPException(
                    status_code=400,
                    detail=f"Categorias invalidas: {invalid}. Validas: {list(DNA_CATEGORIES)}",
                )
            payload["categories"] = body.categories

    task = {
        "id": f"api-extract-dna-{client_id}",
        "task_type": "extract_client_dna",
        "payload": payload,
    }

    result = await handle_extract_client_dna(task)

    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])

    return {
        "status": "ok",
        **result,
    }


# ── GET: list available categories ────────────────────────────

@router.get("/dna-categories")
async def list_dna_categories():
    """Lista as categorias de DNA disponiveis para extracao."""
    from runtime.tasks.handlers.extract_client_dna import _CATEGORY_DESCRIPTIONS
    return {
        "status": "ok",
        "categories": {cat: _CATEGORY_DESCRIPTIONS[cat] for cat in DNA_CATEGORIES},
    }
