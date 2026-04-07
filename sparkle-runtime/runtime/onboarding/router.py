"""
Onboarding router — B3-03: SOP Onboarding Automatizado.

POST /onboarding/start              — inicia pipeline de onboarding
GET  /onboarding/status/{client_id} — consulta progresso
POST /onboarding/approve/{client_id} — aprovacao humana, ativa Zenya
"""
from __future__ import annotations

import asyncio
import json
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from runtime.db import supabase
from runtime.onboarding.handler import handle_onboarding

router = APIRouter()


# ── Request / Response models ─────────────────────────────────

class OnboardingStartRequest(BaseModel):
    client_id: Optional[str] = None
    business_name: str
    website_url: Optional[str] = None
    instagram_handle: Optional[str] = None
    contact_phone: str


class OnboardingApproveRequest(BaseModel):
    soul_prompt_override: Optional[str] = None


# ── POST /onboarding/start ────────────────────────────────────

@router.post("/start")
async def start_onboarding(body: OnboardingStartRequest):
    """
    Inicia o pipeline de onboarding automatizado.

    Cria cliente, ingere website, extrai DNA, gera soul_prompt,
    cria character e character_state — tudo em status DRAFT.
    Aprovacao humana necessaria via POST /onboarding/approve/{client_id}.
    """
    task = {
        "id": f"onboarding-{body.business_name[:20]}",
        "task_type": "onboarding_start",
        "payload": {
            "client_id": body.client_id,
            "business_name": body.business_name,
            "website_url": body.website_url or "",
            "instagram_handle": body.instagram_handle or "",
            "contact_phone": body.contact_phone,
        },
    }

    result = await handle_onboarding(task)

    if result.get("status") == "error":
        raise HTTPException(status_code=422, detail=result)

    return result


# ── GET /onboarding/status/{client_id} ────────────────────────

@router.get("/status/{client_id}")
async def get_onboarding_status(client_id: str):
    """
    Consulta o status do onboarding de um cliente.

    Retorna: status (draft/active/error), steps executados,
    soul_prompt gerado e character_slug.
    """
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("onboarding_sessions")
            .select("*")
            .eq("client_id", client_id)
            .maybe_single()
            .execute()
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Falha ao consultar onboarding: {e}",
        ) from e

    data = result.data if result else None

    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"Nenhum onboarding encontrado para client_id={client_id}",
        )

    # Parse steps JSON if stored as string
    steps = data.get("steps", "[]")
    if isinstance(steps, str):
        try:
            steps = json.loads(steps)
        except json.JSONDecodeError:
            steps = []

    return {
        "status": data.get("status", "unknown"),
        "client_id": client_id,
        "character_slug": data.get("character_slug", ""),
        "soul_prompt": data.get("soul_prompt", ""),
        "steps": steps,
        "updated_at": data.get("updated_at", ""),
    }


# ── POST /onboarding/approve/{client_id} ─────────────────────

@router.post("/approve/{client_id}")
async def approve_onboarding(client_id: str, body: Optional[OnboardingApproveRequest] = None):
    """
    Aprovacao humana do onboarding — ativa o character e o cliente.

    Passos:
    1. Verifica que o onboarding existe e esta em status draft
    2. Se soul_prompt_override fornecido, atualiza o character
    3. Ativa character (active=true)
    4. Atualiza client status para 'active'
    5. Atualiza onboarding_sessions status para 'active'
    """
    # 1. Busca sessao de onboarding
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("onboarding_sessions")
            .select("*")
            .eq("client_id", client_id)
            .maybe_single()
            .execute()
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Falha ao consultar onboarding: {e}",
        ) from e

    session = result.data if result else None
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Nenhum onboarding encontrado para client_id={client_id}",
        )

    current_status = session.get("status", "")
    if current_status == "active":
        return {
            "status": "already_active",
            "message": f"Onboarding de {client_id} ja foi aprovado anteriormente.",
        }

    character_slug = session.get("character_slug", "")
    if not character_slug:
        raise HTTPException(
            status_code=422,
            detail="Onboarding incompleto — character_slug nao encontrado. Execute /onboarding/start primeiro.",
        )

    # 2. Override soul_prompt if provided
    soul_prompt = session.get("soul_prompt", "")
    if body and body.soul_prompt_override:
        soul_prompt = body.soul_prompt_override

    # 3. Activate character
    try:
        await asyncio.to_thread(
            lambda: supabase.table("characters")
            .update({
                "active": True,
                "soul_prompt": soul_prompt,
                "lore_status": "active",
            })
            .eq("slug", character_slug)
            .execute()
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Falha ao ativar character '{character_slug}': {e}",
        ) from e

    # 4. Update client status
    try:
        await asyncio.to_thread(
            lambda: supabase.table("clients")
            .update({"status": "active"})
            .eq("id", client_id)
            .execute()
        )
    except Exception as e:
        print(f"[onboarding] update client status failed (non-fatal): {e}")

    # 5. Update onboarding session
    try:
        from datetime import datetime, timezone
        await asyncio.to_thread(
            lambda: supabase.table("onboarding_sessions")
            .update({
                "status": "active",
                "soul_prompt": soul_prompt,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            .eq("client_id", client_id)
            .execute()
        )
    except Exception as e:
        print(f"[onboarding] update onboarding session failed (non-fatal): {e}")

    return {
        "status": "active",
        "client_id": client_id,
        "character_slug": character_slug,
        "message": (
            f"Onboarding aprovado! Zenya ({character_slug}) ativada para {client_id}. "
            f"Character active=true, client status=active."
        ),
    }
