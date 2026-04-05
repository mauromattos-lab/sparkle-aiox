"""
Onboarding router — ONB-1: Pipeline Orquestrador de Onboarding.

POST /onboarding/start              — inicia pipeline de onboarding (AC-2.x)
GET  /onboarding/status/{client_id} — consulta progresso
POST /onboarding/approve/{client_id} — aprovacao humana, ativa Zenya
POST /onboarding/gate/{client_id}/{phase} — gate check manual para uma fase
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
    """AC-2.1: payload para POST /onboarding/start"""
    client_name: str
    business_type: str
    site_url: Optional[str] = None
    phone: Optional[str] = None
    plan: Optional[str] = None
    mrr_value: Optional[float] = None
    # Legacy fields (backward compat)
    client_id: Optional[str] = None
    business_name: Optional[str] = None
    website_url: Optional[str] = None
    instagram_handle: Optional[str] = None
    contact_phone: Optional[str] = None


class OnboardingApproveRequest(BaseModel):
    soul_prompt_override: Optional[str] = None


class GateCheckRequest(BaseModel):
    conditions: Optional[list[str]] = None


# ── POST /onboarding/start ────────────────────────────────────

@router.post("/start")
async def start_onboarding(body: OnboardingStartRequest):
    """
    AC-2.1: Inicia pipeline de onboarding orquestrado.

    - Aceita: client_name, business_type, site_url, phone, plan, mrr_value
    - AC-2.4: Idempotente — mesmos client_name + phone retornam onboarding existente
    - AC-2.3: Retorna HTTP 422 se client_name ou business_type ausentes
    - Retorna: { onboarding_id, client_id, status: "contract_pending" }
    """
    from runtime.onboarding.service import (
        find_existing_onboarding,
        create_onboarding_pipeline,
        PHASE_CONDITIONS,
    )

    # AC-2.3: Validate required fields
    client_name = body.client_name or body.business_name or ""
    business_type = body.business_type or ""

    if not client_name.strip():
        raise HTTPException(
            status_code=422,
            detail="client_name e obrigatorio",
        )
    if not business_type.strip():
        raise HTTPException(
            status_code=422,
            detail="business_type e obrigatorio",
        )

    # Normalize optional fields
    phone = body.phone or body.contact_phone or None
    site_url = body.site_url or body.website_url or None

    # AC-2.4: Idempotency check — return existing onboarding if found
    existing = await find_existing_onboarding(client_name, phone)
    if existing:
        return {
            "onboarding_id": existing.get("onboarding_id"),
            "client_id": existing["client_id"],
            "status": "contract_pending",
            "phase": existing.get("current_phase", "contract"),
            "message": f"Onboarding ja existe para '{client_name}'. Retornando pipeline existente.",
            "idempotent": True,
        }

    # Create new onboarding pipeline
    result = await create_onboarding_pipeline(
        client_name=client_name.strip(),
        business_type=business_type.strip(),
        site_url=site_url,
        phone=phone,
        plan=body.plan,
        mrr_value=body.mrr_value,
    )

    return result


# ── POST /onboarding/gate/{client_id}/{phase} ─────────────────

@router.post("/gate/{client_id}/{phase}")
async def gate_check(client_id: str, phase: str, body: Optional[GateCheckRequest] = None):
    """
    AC-3.2: Gate check manual para uma fase especifica.

    Verifica se as condicoes do gate estao satisfeitas.
    Se sim: marca fase como completed, avanca para proxima.
    Se nao: retorna { passed: false, missing: [...] }
    """
    from runtime.onboarding.service import check_gate, PHASE_CONDITIONS

    conditions = (body.conditions if body and body.conditions is not None
                  else PHASE_CONDITIONS.get(phase, []))

    result = await check_gate(client_id, phase, conditions)
    return result


# ── GET /onboarding/status/{client_id} ────────────────────────

@router.get("/status/{client_id}")
async def get_onboarding_status(client_id: str):
    """
    Consulta o status do onboarding de um cliente.

    Retorna: status, phase atual, steps executados,
    soul_prompt gerado, character_slug e workflows por fase.
    """
    try:
        session_result, workflows_result = await asyncio.gather(
            asyncio.to_thread(
                lambda: supabase.table("onboarding_sessions")
                .select("*")
                .eq("client_id", client_id)
                .maybe_single()
                .execute()
            ),
            asyncio.to_thread(
                lambda: supabase.table("onboarding_workflows")
                .select("phase,status,gate_passed,started_at,completed_at,gate_details,error_log")
                .eq("client_id", client_id)
                .order("created_at")
                .execute()
            ),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Falha ao consultar onboarding: {e}",
        ) from e

    data = session_result.data if session_result else None
    workflows = workflows_result.data if workflows_result else []

    if not data and not workflows:
        raise HTTPException(
            status_code=404,
            detail=f"Nenhum onboarding encontrado para client_id={client_id}",
        )

    # Parse steps JSON if stored as string
    steps = data.get("steps", "[]") if data else []
    if isinstance(steps, str):
        try:
            steps = json.loads(steps)
        except json.JSONDecodeError:
            steps = []

    return {
        "status": data.get("status", "unknown") if data else "unknown",
        "phase": data.get("phase", "contract") if data else "contract",
        "client_id": client_id,
        "character_slug": data.get("character_slug", "") if data else "",
        "soul_prompt": data.get("soul_prompt", "") if data else "",
        "steps": steps,
        "workflows": workflows,
        "updated_at": data.get("updated_at", "") if data else "",
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
    6. Atualiza zenya_clients testing_mode para 'live'
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

    from datetime import datetime, timezone
    now_ts = datetime.now(timezone.utc).isoformat()

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

    # 5. Update zenya_clients testing_mode to 'live'
    try:
        await asyncio.to_thread(
            lambda: supabase.table("zenya_clients")
            .update({"testing_mode": "live", "active": True})
            .eq("client_id", client_id)
            .execute()
        )
    except Exception as e:
        print(f"[onboarding] update zenya_clients testing_mode failed (non-fatal): {e}")

    # 6. Update onboarding session
    try:
        await asyncio.to_thread(
            lambda: supabase.table("onboarding_sessions")
            .update({
                "status": "active",
                "soul_prompt": soul_prompt,
                "phase": "post_go_live",
                "completed_at": now_ts,
                "updated_at": now_ts,
            })
            .eq("client_id", client_id)
            .execute()
        )
    except Exception as e:
        print(f"[onboarding] update onboarding session failed (non-fatal): {e}")

    # 7. Mark go_live workflow phase as completed
    try:
        await asyncio.to_thread(
            lambda: supabase.table("onboarding_workflows")
            .update({
                "status": "completed",
                "gate_passed": True,
                "completed_at": now_ts,
                "updated_at": now_ts,
            })
            .eq("client_id", client_id)
            .eq("phase", "go_live")
            .execute()
        )
    except Exception as e:
        print(f"[onboarding] update go_live workflow failed (non-fatal): {e}")

    return {
        "status": "active",
        "client_id": client_id,
        "character_slug": character_slug,
        "message": (
            f"Onboarding aprovado! Zenya ({character_slug}) ativada para {client_id}. "
            f"Character active=true, client status=active, testing_mode=live."
        ),
    }
