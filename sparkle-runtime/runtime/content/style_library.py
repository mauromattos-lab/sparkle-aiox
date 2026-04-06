"""
Style Library — Curadoria de imagens Zenya para geração visual.

Endpoints:
  GET  /content/library               — lista com filtros + stats
  POST /content/library/register      — registra imagem já no Storage
  POST /content/library/register-batch — registro em lote
  POST /content/library/{id}/react    — reação (like/discard/neutral)
  GET  /content/library/similar/{id}  — similares por CLIP (fallback: score)
  POST /content/library/confirm       — confirma Style Library (aplica tiers)
  GET  /content/library/tier-a        — retorna Tier A para geração

Embeddings CLIP: calculados via scripts/clip_embeddings.py (roda local)
e inseridos diretamente no Supabase. O VPS apenas consulta pgvector.
"""
from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from runtime.db import supabase

router = APIRouter(prefix="/library")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Pydantic models ──────────────────────────────────────────

class RegisterImageRequest(BaseModel):
    storage_path: str
    public_url: str
    creator_id: str = "zenya"
    style_type: Optional[str] = None   # 'cinematic' | 'influencer_natural'
    tags: list[str] = []


class ReactRequest(BaseModel):
    reaction: str  # 'like' | 'discard' | 'neutral'


# ── GET /content/library ─────────────────────────────────────

@router.get("")
async def list_library(
    tier: Optional[str] = Query(None, description="Filter: A, B, C"),
    style_type: Optional[str] = Query(None),
    creator_id: str = Query("zenya"),
    limit: int = Query(200),
    offset: int = Query(0),
):
    """Lista imagens da Style Library com filtros e stats."""
    query = (
        supabase.table("style_library")
        .select("id, creator_id, tier, storage_path, public_url, tags, style_type, mauro_score, use_count, embedding_status, created_at")
        .eq("creator_id", creator_id)
        .order("mauro_score", desc=True)
        .order("created_at", desc=False)
        .limit(limit)
        .offset(offset)
    )
    if tier:
        query = query.eq("tier", tier.upper())
    if style_type:
        query = query.eq("style_type", style_type)

    try:
        result = query.execute()
        stats_result = (
            supabase.table("style_library")
            .select("tier, mauro_score", count="exact")
            .eq("creator_id", creator_id)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    tier_counts = {"A": 0, "B": 0, "C": 0}
    reaction_counts = {"liked": 0, "discarded": 0, "neutral": 0}
    for row in (stats_result.data or []):
        t = row.get("tier", "C")
        if t in tier_counts:
            tier_counts[t] += 1
        s = row.get("mauro_score", 0)
        if s == 1:
            reaction_counts["liked"] += 1
        elif s == -1:
            reaction_counts["discarded"] += 1
        else:
            reaction_counts["neutral"] += 1

    return {
        "items": result.data,
        "count": len(result.data),
        "stats": {
            "tiers": tier_counts,
            "reactions": reaction_counts,
            "total": stats_result.count or 0,
        },
    }


# ── POST /content/library/register ───────────────────────────

@router.post("/register")
async def register_image(req: RegisterImageRequest):
    """Registra imagem já enviada ao Supabase Storage."""
    try:
        result = supabase.table("style_library").insert({
            "creator_id": req.creator_id,
            "storage_path": req.storage_path,
            "public_url": req.public_url,
            "tier": "C",
            "mauro_score": 0,
            "tags": req.tags,
            "style_type": req.style_type,
            "embedding_status": "pending",
            "created_at": _now(),
            "updated_at": _now(),
        }).execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    item_id = result.data[0]["id"] if result.data else None
    return {"status": "ok", "id": item_id}


# ── POST /content/library/register-batch ─────────────────────

@router.post("/register-batch")
async def register_batch(items: list[RegisterImageRequest]):
    """Registra múltiplas imagens de uma vez."""
    if not items:
        raise HTTPException(status_code=400, detail="No items provided")
    if len(items) > 1000:
        raise HTTPException(status_code=400, detail="Max 1000 items per batch")

    rows = [
        {
            "creator_id": item.creator_id,
            "storage_path": item.storage_path,
            "public_url": item.public_url,
            "tier": "C",
            "mauro_score": 0,
            "tags": item.tags,
            "style_type": item.style_type,
            "embedding_status": "pending",
            "created_at": _now(),
            "updated_at": _now(),
        }
        for item in items
    ]

    try:
        result = supabase.table("style_library").insert(rows).execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {"status": "ok", "registered": len(result.data)}


# ── POST /content/library/{id}/react ─────────────────────────

@router.post("/{item_id}/react")
async def react_to_image(item_id: str, req: ReactRequest):
    """Registra reação: like (❤️ → Tier A), discard (✗ → Tier C), neutral (→ → Tier B)."""
    reaction_map = {"like": 1, "discard": -1, "neutral": 0}
    if req.reaction not in reaction_map:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid reaction '{req.reaction}'. Use: like, discard, neutral",
        )

    score = reaction_map[req.reaction]
    tier = "A" if score == 1 else ("C" if score == -1 else "B")

    try:
        result = (
            supabase.table("style_library")
            .update({"mauro_score": score, "tier": tier, "updated_at": _now()})
            .eq("id", item_id)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if not result.data:
        raise HTTPException(status_code=404, detail="Image not found")

    return {"status": "ok", "id": item_id, "score": score, "tier": tier}


# ── GET /content/library/similar/{id} ────────────────────────

@router.get("/similar/{item_id}")
async def similar_images(item_id: str, limit: int = 10):
    """
    Imagens similares via pgvector cosine distance (se embedding disponível).
    Fallback: ordenação por mauro_score.
    """
    try:
        ref = (
            supabase.table("style_library")
            .select("embedding, embedding_status, creator_id")
            .eq("id", item_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if not ref.data:
        raise HTTPException(status_code=404, detail="Image not found")

    item = ref.data[0]
    creator_id = item.get("creator_id", "zenya")

    # Se embedding disponível, usar pgvector via RPC
    if item.get("embedding_status") == "done" and item.get("embedding"):
        try:
            similar = supabase.rpc("style_library_similar", {
                "ref_id": item_id,
                "creator": creator_id,
                "top_k": limit,
            }).execute()
            if similar.data:
                return {"items": similar.data, "method": "clip_cosine"}
        except Exception:
            pass  # fallback gracioso

    # Fallback: ordenar por mauro_score, excluir o próprio item
    try:
        fallback = (
            supabase.table("style_library")
            .select("id, storage_path, public_url, tier, mauro_score, style_type")
            .eq("creator_id", creator_id)
            .neq("id", item_id)
            .order("mauro_score", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {"items": fallback.data, "method": "score_fallback"}


# ── POST /content/library/confirm ────────────────────────────

@router.post("/confirm")
async def confirm_library(creator_id: str = "zenya"):
    """
    Confirma a Style Library.
    Tier A = mauro_score 1 | Tier B = 0 | Tier C = -1
    Requer mínimo 10 curtidas (Tier A).
    """
    try:
        tier_a = (
            supabase.table("style_library")
            .select("id", count="exact")
            .eq("creator_id", creator_id)
            .eq("mauro_score", 1)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    tier_a_count = tier_a.count or 0
    if tier_a_count < 10:
        raise HTTPException(
            status_code=400,
            detail=f"Mínimo 10 curtidas para confirmar. Atual: {tier_a_count}",
        )

    try:
        supabase.table("style_library").update({"tier": "A", "updated_at": _now()}).eq("creator_id", creator_id).eq("mauro_score", 1).execute()
        supabase.table("style_library").update({"tier": "B", "updated_at": _now()}).eq("creator_id", creator_id).eq("mauro_score", 0).execute()
        supabase.table("style_library").update({"tier": "C", "updated_at": _now()}).eq("creator_id", creator_id).eq("mauro_score", -1).execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # Contagem final
    counts = (
        supabase.table("style_library")
        .select("tier")
        .eq("creator_id", creator_id)
        .execute()
    )
    tier_counts = {"A": 0, "B": 0, "C": 0}
    for row in (counts.data or []):
        t = row.get("tier", "C")
        if t in tier_counts:
            tier_counts[t] += 1

    return {
        "status": "confirmed",
        "tier_a": tier_counts["A"],
        "tier_b": tier_counts["B"],
        "tier_c": tier_counts["C"],
        "message": f"Style Library confirmada — {tier_counts['A']} imagens canônicas (Tier A)",
    }


# ── GET /content/library/tier-a ──────────────────────────────

@router.get("/tier-a")
async def get_tier_a(
    creator_id: str = "zenya",
    style_type: Optional[str] = None,
    limit: int = 5,
):
    """Retorna imagens Tier A para uso como referência na geração de imagens."""
    query = (
        supabase.table("style_library")
        .select("id, storage_path, public_url, style_type, use_count")
        .eq("creator_id", creator_id)
        .eq("tier", "A")
        .order("use_count", desc=False)
        .limit(limit * 3)
    )
    if style_type:
        query = query.eq("style_type", style_type)

    try:
        result = query.execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if not result.data:
        raise HTTPException(
            status_code=400,
            detail="Style Library sem imagens Tier A. Execute a curadoria primeiro.",
        )

    selected = random.sample(result.data, min(limit, len(result.data)))
    return {"items": selected, "count": len(selected)}
