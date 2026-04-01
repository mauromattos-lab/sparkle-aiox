"""
Member State Engine — Router (S5-02).

Endpoints:
  GET  /member/{phone}                — perfil completo (profile + state + últimas 10 interações)
  POST /member                        — upsert membro
  POST /member/{phone}/state          — set único key/value de estado
  POST /member/{phone}/state/batch    — set múltiplas keys em paralelo
  POST /member/{phone}/interaction    — registra interação

Todos os endpoints retornam o objeto atualizado ou criado.
"""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from runtime.members.handler import (
    add_interaction,
    get_member,
    set_member_state,
    upsert_member,
)

router = APIRouter()


# ── Request / Response models ─────────────────────────────────────────────────

class UpsertMemberRequest(BaseModel):
    phone: str
    name: str | None = None
    email: str | None = None
    tags: list[str] | None = None


class SetStateRequest(BaseModel):
    key: str
    value: str
    set_by: str = "system"


class BatchStateEntry(BaseModel):
    key: str
    value: str
    set_by: str = "system"


class BatchStateRequest(BaseModel):
    states: list[BatchStateEntry]


class AddInteractionRequest(BaseModel):
    character_id: str | None = None
    channel: str = "whatsapp"
    summary: str = ""
    sentiment: str | None = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/{phone}")
async def get_member_profile(phone: str) -> dict[str, Any]:
    """
    Retorna perfil completo do membro: dados base + estado EAV + últimas 10 interações.
    404 se o membro não existir.
    """
    member = await get_member(phone)
    if not member:
        raise HTTPException(status_code=404, detail=f"Member '{phone}' not found.")
    return member


@router.post("")
async def upsert_member_endpoint(req: UpsertMemberRequest) -> dict[str, Any]:
    """
    Cria ou atualiza um membro.
    Campos opcionais (name, email, tags) só sobrescrevem se fornecidos (não-null).
    """
    return await upsert_member(
        phone=req.phone,
        name=req.name,
        email=req.email,
        tags=req.tags,
    )


@router.post("/{phone}/state")
async def set_state(phone: str, req: SetStateRequest) -> dict[str, Any]:
    """
    Define (upsert) um único key/value de estado para o membro.
    Cria o membro automaticamente se não existir.
    """
    # Auto-create member shell so foreign key / lookup never fails
    await upsert_member(phone=phone)
    return await set_member_state(
        phone=phone,
        key=req.key,
        value=req.value,
        set_by=req.set_by,
    )


@router.post("/{phone}/state/batch")
async def set_state_batch(phone: str, req: BatchStateRequest) -> list[dict[str, Any]]:
    """
    Define múltiplas keys de estado em paralelo.
    Retorna lista de rows upsertados, na mesma ordem do input.
    """
    if not req.states:
        return []

    # Auto-create member shell first (sequential — must complete before upserts)
    await upsert_member(phone=phone)

    # Upsert all keys in parallel
    tasks = [
        set_member_state(
            phone=phone,
            key=entry.key,
            value=entry.value,
            set_by=entry.set_by,
        )
        for entry in req.states
    ]
    results = await asyncio.gather(*tasks)
    return list(results)


@router.post("/{phone}/interaction")
async def record_interaction(phone: str, req: AddInteractionRequest) -> dict[str, Any]:
    """
    Registra uma interação do membro com um personagem ou canal.
    Auto-cria o membro se não existir.
    """
    await upsert_member(phone=phone)
    return await add_interaction(
        phone=phone,
        character_id=req.character_id,
        channel=req.channel,
        summary=req.summary,
        sentiment=req.sentiment,
    )
