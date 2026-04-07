"""
Member State Engine — Router (S5-02 + B4-05).

S5-02 Endpoints (phone-based EAV):
  GET  /member/{phone}                — perfil completo (profile + state + últimas 10 interações)
  POST /member                        — upsert membro
  POST /member/{phone}/state          — set único key/value de estado
  POST /member/{phone}/state/batch    — set múltiplas keys em paralelo
  POST /member/{phone}/interaction    — registra interação

B4-05 Community Endpoints (client_id scoped, XP/levels):
  GET  /member/community/{client_id}                    — list members for a client
  GET  /member/community/{client_id}/leaderboard        — leaderboard (top by XP)
  GET  /member/community/{client_id}/{member_id}        — get specific community member
  POST /member/community/{client_id}                    — create community member
  POST /member/community/{client_id}/{member_id}/event  — record event + XP
  PATCH /member/community/{client_id}/{member_id}       — partial update

Todos os endpoints retornam o objeto atualizado ou criado.
"""
from __future__ import annotations

import asyncio
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from runtime.members.handler import (
    add_interaction,
    get_member,
    set_member_state,
    upsert_member,
)
from runtime.members.state import (
    calculate_level,
    create_member as create_community_member,
    get_leaderboard,
    get_member as get_community_member,
    list_members,
    record_event,
    update_member as update_community_member,
)

router = APIRouter()


# ── S5-02 Request / Response models ──────────────────────────────────────────

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


# ── B4-05 Request models ─────────────────────────────────────────────────────

class CreateCommunityMemberRequest(BaseModel):
    member_id: str
    display_name: str | None = None


class UpdateCommunityMemberRequest(BaseModel):
    display_name: str | None = None
    status: str | None = None
    engagement_score: float | None = None
    metadata: dict | None = None
    last_active_at: str | None = None


class RecordEventRequest(BaseModel):
    event_type: str
    event_data: dict | None = None
    xp_earned: int = 0


# ══════════════════════════════════════════════════════════════════════════════
# B4-05 Community Endpoints (must be registered BEFORE S5-02 /{phone} catch-all)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/community/{client_id}/leaderboard")
async def community_leaderboard(
    client_id: str,
    limit: int = Query(default=10, ge=1, le=100),
) -> list[dict[str, Any]]:
    """
    Return top members for a client community ranked by XP.
    Only active members are included.
    """
    return await get_leaderboard(client_id=client_id, limit=limit)


@router.get("/community/{client_id}/{member_id}")
async def get_community_member_endpoint(
    client_id: str,
    member_id: str,
) -> dict[str, Any]:
    """
    Get a specific community member's state.
    """
    member = await get_community_member(client_id=client_id, member_id=member_id)
    if not member:
        raise HTTPException(
            status_code=404,
            detail=f"Community member '{member_id}' not found for client '{client_id}'.",
        )
    return member


@router.get("/community/{client_id}")
async def list_community_members(
    client_id: str,
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """
    List all community members for a client, optionally filtered by status.
    """
    return await list_members(client_id=client_id, status=status, limit=limit)


@router.post("/community/{client_id}")
async def create_community_member_endpoint(
    client_id: str,
    req: CreateCommunityMemberRequest,
) -> dict[str, Any]:
    """
    Create a new community member for a client.
    Upserts if the member already exists.
    """
    return await create_community_member(
        client_id=client_id,
        member_id=req.member_id,
        display_name=req.display_name,
    )


@router.post("/community/{client_id}/{member_id}/event")
async def record_community_event(
    client_id: str,
    member_id: str,
    req: RecordEventRequest,
) -> dict[str, Any]:
    """
    Record an event for a community member, optionally awarding XP.
    The member's level is automatically recalculated.
    """
    # First resolve the member's UUID
    member = await get_community_member(client_id=client_id, member_id=member_id)
    if not member:
        raise HTTPException(
            status_code=404,
            detail=f"Community member '{member_id}' not found for client '{client_id}'.",
        )

    return await record_event(
        member_id=member["id"],
        event_type=req.event_type,
        event_data=req.event_data,
        xp_earned=req.xp_earned,
    )


@router.patch("/community/{client_id}/{member_id}")
async def update_community_member_endpoint(
    client_id: str,
    member_id: str,
    req: UpdateCommunityMemberRequest,
) -> dict[str, Any]:
    """
    Partial update of a community member's state.
    """
    member = await get_community_member(client_id=client_id, member_id=member_id)
    if not member:
        raise HTTPException(
            status_code=404,
            detail=f"Community member '{member_id}' not found for client '{client_id}'.",
        )

    updates = req.model_dump(exclude_none=True)
    if not updates:
        return member

    result = await update_community_member(member_id=member["id"], updates=updates)
    return result or member


# ══════════════════════════════════════════════════════════════════════════════
# S5-02 Endpoints (phone-based EAV — original)
# ══════════════════════════════════════════════════════════════════════════════

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
