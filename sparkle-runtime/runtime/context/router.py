"""
Context router — SYS-2.4: endpoints REST para gerenciar blocos de contexto.

GET    /context/blocks                 — lista blocos ativos
GET    /context/blocks?agent=analyst   — filtro por agente
POST   /context/blocks                 — cria bloco
PUT    /context/blocks/{block_id}      — atualiza bloco
DELETE /context/blocks/{block_id}      — soft delete (active=false)
GET    /context/preview?agent=analyst  — preview do contexto montado
POST   /context/seed                   — seed/upsert all predefined blocks (idempotent)
"""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from runtime.db import supabase
from runtime.context.assembler import assemble_context
from runtime.context.seed_blocks import seed_blocks

router = APIRouter()


# ── Request models ────────────────────────────────────────────

class CreateBlockRequest(BaseModel):
    block_key: str  # ex: "system.identity", "process.onboarding"
    layer: str  # system | process | state | knowledge
    agent_id: Optional[str] = None  # NULL = global
    content: str
    priority: int = 5


class UpdateBlockRequest(BaseModel):
    block_key: Optional[str] = None
    layer: Optional[str] = None
    agent_id: Optional[str] = None
    content: Optional[str] = None
    priority: Optional[int] = None
    active: Optional[bool] = None


# ── GET /context/blocks ───────────────────────────────────────

@router.get("/blocks")
async def list_blocks(
    agent: Optional[str] = None,
    layer: Optional[str] = None,
    active_only: bool = True,
):
    """Lista blocos de contexto. Filtra por agente e/ou camada."""
    try:
        query = supabase.table("agent_context_blocks").select(
            "id,block_key,layer,agent_id,content,priority,active,version,updated_at"
        )
        if active_only:
            query = query.eq("active", True)
        if agent:
            query = query.or_(f"agent_id.is.null,agent_id.eq.{agent}")
        if layer:
            query = query.eq("layer", layer)

        query = query.order("layer").order("priority")
        result = await asyncio.to_thread(lambda: query.execute())

        return {
            "status": "ok",
            "count": len(result.data or []),
            "blocks": result.data or [],
        }
    except Exception as e:
        return {"status": "error", "error": f"Falha ao listar blocos: {str(e)[:200]}"}


# ── POST /context/blocks ──────────────────────────────────────

@router.post("/blocks")
async def create_block(req: CreateBlockRequest):
    """Cria novo bloco de contexto."""
    valid_layers = {"system", "process", "state", "knowledge"}
    if req.layer not in valid_layers:
        raise HTTPException(
            status_code=400,
            detail=f"Layer invalida. Valores aceitos: {', '.join(sorted(valid_layers))}",
        )

    try:
        row = {
            "block_key": req.block_key,
            "layer": req.layer,
            "agent_id": req.agent_id,
            "content": req.content,
            "priority": req.priority,
            "active": True,
            "version": 1,
        }
        result = await asyncio.to_thread(
            lambda: supabase.table("agent_context_blocks").insert(row).execute()
        )
        created = result.data[0] if result.data else {}
        return {"status": "ok", "block": created}
    except Exception as e:
        error_msg = str(e)
        if "duplicate" in error_msg.lower() or "unique" in error_msg.lower():
            raise HTTPException(
                status_code=409,
                detail=f"Bloco com block_key '{req.block_key}' ja existe",
            )
        return {"status": "error", "error": f"Falha ao criar bloco: {error_msg[:200]}"}


# ── PUT /context/blocks/{block_id} ────────────────────────────

@router.put("/blocks/{block_id}")
async def update_block(block_id: str, req: UpdateBlockRequest):
    """Atualiza bloco de contexto existente."""
    update_data: dict = {}
    if req.block_key is not None:
        update_data["block_key"] = req.block_key
    if req.layer is not None:
        valid_layers = {"system", "process", "state", "knowledge"}
        if req.layer not in valid_layers:
            raise HTTPException(
                status_code=400,
                detail=f"Layer invalida. Valores aceitos: {', '.join(sorted(valid_layers))}",
            )
        update_data["layer"] = req.layer
    if req.agent_id is not None:
        update_data["agent_id"] = req.agent_id
    if req.content is not None:
        update_data["content"] = req.content
    if req.priority is not None:
        update_data["priority"] = req.priority
    if req.active is not None:
        update_data["active"] = req.active

    if not update_data:
        raise HTTPException(status_code=400, detail="Nenhum campo para atualizar")

    try:
        # Incrementa version automaticamente
        # Primeiro busca version atual
        current = await asyncio.to_thread(
            lambda: supabase.table("agent_context_blocks")
            .select("version")
            .eq("id", block_id)
            .single()
            .execute()
        )
        if not current.data:
            raise HTTPException(status_code=404, detail="Bloco nao encontrado")

        update_data["version"] = (current.data.get("version", 1) or 1) + 1

        result = await asyncio.to_thread(
            lambda: supabase.table("agent_context_blocks")
            .update(update_data)
            .eq("id", block_id)
            .execute()
        )
        updated = result.data[0] if result.data else {}
        return {"status": "ok", "block": updated}
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "error": f"Falha ao atualizar bloco: {str(e)[:200]}"}


# ── DELETE /context/blocks/{block_id} ─────────────────────────

@router.delete("/blocks/{block_id}")
async def delete_block(block_id: str):
    """Soft delete — marca bloco como inactive."""
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("agent_context_blocks")
            .update({"active": False})
            .eq("id", block_id)
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Bloco nao encontrado")
        return {"status": "ok", "message": f"Bloco {block_id} desativado"}
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "error": f"Falha ao desativar bloco: {str(e)[:200]}"}


# ── GET /context/preview ──────────────────────────────────────

@router.get("/preview")
async def preview_context(agent: str = "analyst", request: str = ""):
    """
    Preview do contexto completo que um agente receberia.
    Permite ver exatamente o que seria injetado como system prompt.
    """
    try:
        context = await assemble_context(agent_id=agent, request=request)
        token_estimate = len(context) // 4  # estimativa grosseira
        return {
            "status": "ok",
            "agent": agent,
            "context": context,
            "estimated_tokens": token_estimate,
            "char_count": len(context),
        }
    except Exception as e:
        return {"status": "error", "error": f"Falha ao montar preview: {str(e)[:200]}"}


# ── POST /context/seed ───────────────────────────────────────

@router.post("/seed")
async def seed_context_blocks():
    """
    Seed/upsert all predefined context blocks.
    Idempotent — safe to call multiple times. Updates existing blocks by block_key.
    """
    try:
        result = await seed_blocks()
        return result
    except Exception as e:
        return {"status": "error", "error": f"Falha ao executar seed: {str(e)[:200]}"}
