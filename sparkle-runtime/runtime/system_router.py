"""
System router — /system/* endpoints.

GET  /system/capabilities — lista handlers, domains, agents, crons, brain_stats
GET  /system/state        — consulta estado de sprint items (agent_work_items)
POST /system/state        — grava conclusão de sprint item

Permite que agentes construtores entendam o que já existe antes de propor mudanças:
    GET /system/capabilities → entender o que já existe → propor só o que falta
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from runtime.db import supabase
from runtime.config import settings
from runtime.tasks.registry import REGISTRY

router = APIRouter(prefix="/system", tags=["system"])

# ── Constantes descritivas ──────────────────────────────────

_DOMAINS = [
    "trafego_pago",
    "zenya_config",
    "conteudo",
    "estrategia",
    "financeiro",
    "tech",
    "brain_ops",
]

_AGENTS = sorted(["analyst", "architect", "dev", "qa", "pm", "trafego"])

_CRONS = [
    {"name": "health_check",          "schedule": "every 15min"},
    {"name": "daily_briefing",        "schedule": "daily 8h Brasilia"},
    {"name": "weekly_briefing",       "schedule": "sunday 8h Brasilia"},
    {"name": "gap_report",            "schedule": "monday 8h Brasilia"},
    {"name": "daily_decision_moment", "schedule": "daily 9h Brasilia"},
]

_VERSION = "sprint9"


# ── Helpers ─────────────────────────────────────────────────

async def _count_table(table: str) -> int:
    """Retorna count de uma tabela Supabase. Silencia erros."""
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table(table).select("id", count="exact").limit(1).execute()
        )
        return res.count if res.count is not None else len(res.data or [])
    except Exception as e:
        print(f"[system] count {table} failed: {e}")
        return -1


# ── Capabilities ────────────────────────────────────────────

@router.get("/capabilities")
async def get_capabilities():
    """
    Retorna snapshot completo das capacidades do Runtime.

    Usado por agentes construtores para entender o que já existe antes de propor mudanças:
        GET /system/capabilities → entender o que já existe → propor só o que falta
    """
    chunks_total, dna_entries = await asyncio.gather(
        _count_table("brain_chunks"),
        _count_table("agent_dna"),
    )

    return {
        "handlers": sorted(REGISTRY.keys()),
        "domains": _DOMAINS,
        "agents": _AGENTS,
        "crons": _CRONS,
        "brain_stats": {
            "chunks_total": chunks_total,
            "dna_entries": dna_entries,
        },
        "version": _VERSION,
    }


# ── State (sprint item tracking) ────────────────────────────

class StateUpdate(BaseModel):
    sprint_item: str
    status: str
    title: Optional[str] = None
    assigned_to: Optional[str] = None
    notes: Optional[str] = None
    verified: bool = True
    verification_source: Optional[str] = None
    handoff_to: Optional[str] = None
    completed: bool = False


@router.post("/state")
async def update_state(update: StateUpdate):
    """
    Grava conclusão de sprint item em agent_work_items.

    Protocolo obrigatório ao concluir trabalho:
        POST /system/state com sprint_item, status, verified, notes, handoff_to
    """
    supabase_url = settings.supabase_url
    supabase_key = settings.supabase_key
    if not supabase_url or not supabase_key:
        raise HTTPException(status_code=500, detail="Supabase nao configurado")

    payload: dict = {
        "status": update.status,
        "verified": update.verified,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if update.title:               payload["title"] = update.title
    if update.notes:               payload["notes"] = update.notes
    if update.verification_source: payload["verification_source"] = update.verification_source
    if update.handoff_to:          payload["handoff_to"] = update.handoff_to
    if update.assigned_to:         payload["assigned_to"] = update.assigned_to
    if update.completed:           payload["completed_at"] = datetime.now(timezone.utc).isoformat()

    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.patch(
            f"{supabase_url}/rest/v1/agent_work_items",
            params={"sprint_item": f"eq.{update.sprint_item}"},
            json=payload,
            headers=headers,
            timeout=10,
        )
        if resp.status_code in (200, 204):
            data = resp.json()
            if not data:
                # Registro não existe — cria
                payload["sprint_item"] = update.sprint_item
                payload["created_by"] = update.assigned_to or "agent"
                if update.title: payload["title"] = update.title
                await client.post(
                    f"{supabase_url}/rest/v1/agent_work_items",
                    json=payload, headers=headers, timeout=10,
                )
                return {"action": "created", "sprint_item": update.sprint_item, "status": update.status}
            return {"action": "updated", "sprint_item": update.sprint_item, "status": update.status}
        raise HTTPException(status_code=resp.status_code, detail=resp.text)


@router.get("/state")
async def get_state(sprint_item: Optional[str] = None):
    """
    Consulta estado atual de sprint items.

    Query params:
        sprint_item (opcional) — filtra por item específico (ex: SPRINT8-P3)
    """
    supabase_url = settings.supabase_url
    supabase_key = settings.supabase_key
    if not supabase_url or not supabase_key:
        raise HTTPException(status_code=500, detail="Supabase nao configurado")

    headers = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"}
    params: dict = {
        "order": "sprint_item.asc",
        "select": "sprint_item,title,status,verified,assigned_to,handoff_to,notes,updated_at",
    }
    if sprint_item:
        params["sprint_item"] = f"eq.{sprint_item}"
    else:
        params["sprint_item"] = "not.is.null"

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{supabase_url}/rest/v1/agent_work_items",
            params=params, headers=headers, timeout=10,
        )
        return resp.json()
