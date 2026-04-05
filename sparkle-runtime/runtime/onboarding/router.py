"""
Onboarding router — ONB-1 + ONB-2 + ONB-5 + ONB-1.7 + Story 1.8.

POST /onboarding/start              — inicia pipeline de onboarding (AC-2.x)
GET  /onboarding/status/{client_id} — consulta progresso
POST /onboarding/approve/{client_id} — aprovacao humana, ativa Zenya (legado — backward compat)
POST /onboarding/gate/{client_id}/{phase} — gate check manual para uma fase
POST /onboarding/intake/{client_id}       — dispara intake automatico (ONB-2)
POST /onboarding/intake/answer            — recebe resposta do formulario WhatsApp (ONB-2)
POST /onboarding/intake/reminders         — cron: verifica timeouts de formularios (ONB-2)
POST /onboarding/qa/{client_id}           — dispara smoke test (ONB-5)
POST /onboarding/{client_id}/approve-client-test  — ONB-1.7: Mauro aprova inicio do teste com cliente
POST /onboarding/{client_id}/client-feedback      — ONB-1.7: registra feedback do cliente
POST /onboarding/{client_id}/go-live              — Story 1.8: Gate 5 — go-live com checklist pre-go-live
"""
from __future__ import annotations

import asyncio
import json
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from runtime.config import settings
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


class IntakeAnswerRequest(BaseModel):
    """Payload para receber resposta do formulário WhatsApp."""
    client_id: str
    answer_text: str


class SmokeTestRequest(BaseModel):
    """Payload opcional para POST /onboarding/qa/{client_id}"""
    business_type: Optional[str] = None
    retry_count: Optional[int] = 0


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

    # Derivar status dinamicamente a partir dos workflows (BUG-1 fix)
    derived_status = "unknown"
    if workflows:
        phase_statuses = {w["phase"]: w["status"] for w in workflows}
        if any(s == "failed" for s in phase_statuses.values()):
            derived_status = "failed"
        elif phase_statuses.get("go_live") == "completed":
            derived_status = "live"
        elif any(s == "completed" for s in phase_statuses.values()) and all(
            s in ("completed", "pending") for s in phase_statuses.values()
        ) and all(s == "completed" for s in phase_statuses.values()):
            derived_status = "completed"
        else:
            in_progress = next(
                (w["phase"] for w in workflows if w["status"] == "in_progress"), None
            )
            if in_progress:
                derived_status = in_progress
            elif all(s == "pending" for s in phase_statuses.values()):
                derived_status = "pending"
            elif all(s == "completed" for s in phase_statuses.values()):
                derived_status = "completed"
    elif data:
        derived_status = data.get("status", "unknown") or "unknown"

    return {
        "status": derived_status,
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


# ── POST /onboarding/intake/{client_id} ──────────────────────

@router.post("/intake/{client_id}")
async def trigger_intake(client_id: str):
    """
    ONB-2: Dispara intake automático para um cliente.

    Executa em paralelo:
    - Scrape do site (se client.website preenchido)
    - Scrape do Instagram via Apify (se client.instagram preenchido)
    - Formulário WhatsApp sequencial (se client.whatsapp preenchido)

    Consolida resultados em intake_data na fase 'intake' de onboarding_workflows.
    Retorna intake_summary com completeness_score.
    """
    from runtime.tasks.handlers.intake_orchestrator import handle_intake_orchestrator

    task = {
        "id": f"intake-{client_id}",
        "client_id": client_id,
        "payload": {"client_id": client_id},
    }
    try:
        result = await handle_intake_orchestrator(task)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Falha ao iniciar intake: {e}",
        ) from e


# ── POST /onboarding/intake/answer ───────────────────────────

@router.post("/intake/answer")
async def receive_intake_answer(body: IntakeAnswerRequest):
    """
    ONB-2: Recebe resposta do formulário WhatsApp.

    Chamado pelo webhook Z-API quando o cliente responde uma pergunta.
    Registra a resposta e envia a próxima pergunta automaticamente.

    Body: { "client_id": "...", "answer_text": "..." }
    """
    from runtime.tasks.handlers.intake_form_whatsapp import handle_intake_form_whatsapp

    task = {
        "id": f"intake-answer-{body.client_id}",
        "client_id": body.client_id,
        "payload": {
            "action": "answer",
            "client_id": body.client_id,
            "answer_text": body.answer_text,
        },
    }
    try:
        result = await handle_intake_form_whatsapp(task)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Falha ao registrar resposta: {e}",
        ) from e


# ── POST /onboarding/intake/reminders ────────────────────────

@router.post("/intake/reminders")
async def check_intake_reminders():
    """
    ONB-2: Cron endpoint — verifica formulários com timeout e envia lembretes.

    - Sem resposta >= 24h: envia lembrete
    - Sem resposta >= 48h (reminder 2): envia segundo lembrete
    - Sem resposta >= 72h (após 2 lembretes): marca partial, alerta Friday

    Deve ser chamado via cron a cada hora (ou a cada 6h).
    """
    from runtime.tasks.handlers.intake_form_whatsapp import handle_intake_form_whatsapp

    task = {
        "id": "intake-reminders-cron",
        "payload": {"action": "check_timeouts"},
    }
    try:
        result = await handle_intake_form_whatsapp(task)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Falha ao verificar timeouts: {e}",
        ) from e


# ── POST /onboarding/{client_id}/approve-client-test ─────────

class ApproveClientTestRequest(BaseModel):
    """ONB-1.7 AC-1.2: payload opcional (sem campos obrigatorios)."""
    pass


@router.post("/{client_id}/approve-client-test")
async def approve_client_test(client_id: str, body: Optional[ApproveClientTestRequest] = None):
    """
    ONB-1.7 AC-1.2/1.3/1.4/1.5: Mauro aprova inicio do teste com cliente.

    - Ativa client_testing_active=true em zenya_clients
    - Salva client_test_started_at em gate_details da fase test_client
    - Envia WhatsApp para o cliente avisando que pode testar
    - Envia alerta Friday confirmando inicio do teste
    - Insere evento client_test_started em onboarding_events
    """
    from runtime.onboarding.service import approve_client_test as svc_approve_client_test

    try:
        result = await svc_approve_client_test(client_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Falha ao aprovar teste com cliente: {e}",
        ) from e


# ── POST /onboarding/{client_id}/client-feedback ─────────────

class ClientFeedbackRequest(BaseModel):
    """ONB-1.7 AC-3.2/3.3/3.4: payload do feedback do cliente."""
    approved: bool
    feedback_text: Optional[str] = ""


@router.post("/{client_id}/client-feedback")
async def client_feedback(client_id: str, body: ClientFeedbackRequest):
    """
    ONB-1.7 AC-3.x / AC-4.x: Registra feedback do cliente apos periodo de teste.

    Payload: { "approved": bool, "feedback_text": str }

    - Se approved=true: gate client_approved=true → avanca para go_live
    - Se approved=false e loops < 3: volta para config, re-executa ONB-3
    - Se approved=false e loops >= 3: alerta Friday para intervencao manual
    """
    from runtime.onboarding.service import register_client_feedback

    if body.approved is None:
        raise HTTPException(
            status_code=422,
            detail="Campo 'approved' e obrigatorio (true/false)",
        )

    try:
        result = await register_client_feedback(
            client_id=client_id,
            approved=body.approved,
            feedback_text=body.feedback_text or "",
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Falha ao registrar feedback do cliente: {e}",
        ) from e


# ── POST /onboarding/{client_id}/go-live ─────────────────────

@router.post("/{client_id}/go-live")
async def go_live(
    client_id: str,
    authorization: Optional[str] = Header(default=None),
):
    """
    Story 1.8 — Gate 5: Confirmacao de go-live por Mauro.

    AC-1.3: Exige header Authorization: Bearer <RUNTIME_API_KEY>
    AC-4.1/4.2/4.3: Executa checklist pre-go-live antes de ativar
    AC-2.1/2.2: Transicao atomica testing -> live com rollback best-effort
    AC-3.x: Notificacoes pos-go-live (Friday, cliente, onboarding_events)

    Retorna: { status, checks, client_id, go_live_at } ou HTTP 409 se checklist falhar.
    """
    from runtime.onboarding.service import pre_go_live_checklist, execute_go_live

    # AC-1.3: Autenticacao via Authorization: Bearer token
    # (A rota ja esta protegida pelo APIKeyMiddleware via X-API-Key,
    #  mas adicionamos uma segunda camada com Bearer para confirmar intencao explicita)
    runtime_api_key = settings.runtime_api_key
    if runtime_api_key:
        bearer_token = None
        if authorization and authorization.startswith("Bearer "):
            bearer_token = authorization[len("Bearer "):]
        if bearer_token != runtime_api_key:
            raise HTTPException(
                status_code=401,
                detail=(
                    "Autenticacao Bearer invalida ou ausente. "
                    "Envie o header: Authorization: Bearer <RUNTIME_API_KEY>"
                ),
            )

    # AC-4.1/4.2/4.3: Executa checklist pre-go-live
    try:
        checklist = await pre_go_live_checklist(client_id)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Falha ao executar checklist pre-go-live: {e}",
        ) from e

    if not checklist.get("can_go_live"):
        blocking_issues = checklist.get("blocking_issues", [])
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Go-live bloqueado — checklist nao passou",
                "blocking_issues": blocking_issues,
                "checks": checklist.get("checks"),
            },
        )

    # AC-2.1/2.2: Executa transicao atomica
    try:
        result = await execute_go_live(client_id)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Falha ao executar go-live: {e}",
        ) from e

    if result.get("status") == "error":
        raise HTTPException(
            status_code=500,
            detail={
                "message": result.get("error", "Erro desconhecido no go-live"),
                "rollback": result.get("rollback"),
            },
        )

    # Inclui resultado do checklist na resposta (AC-4.3)
    return {
        **result,
        "checks": checklist.get("checks"),
    }


# ── POST /onboarding/qa/{client_id} ──────────────────────────

@router.post("/qa/{client_id}")
async def run_smoke_test(client_id: str, body: Optional[SmokeTestRequest] = None):
    """
    ONB-5: Dispara smoke test completo da Zenya.

    Executa:
    1. Checklist de qualidade do soul_prompt (AC-2.x)
    2. Checklist de qualidade da KB (AC-3.x)
    3. 10 perguntas de teste (7 genericas + 3 da vertical)
    4. Avaliacao automatica por criterios objetivos

    Se pass_rate >= 80% e checklists OK:
      - testing_mode -> 'client_testing'
      - gate test_internal passa automaticamente
      - pipeline avanca para fase test_client

    Se fail:
      - Friday e alertado com detalhes
      - retry_count incrementado (max 3 tentativas)
    """
    from runtime.tasks.handlers.smoke_test_zenya import handle_smoke_test_zenya

    task = {
        "id": f"qa-{client_id}",
        "client_id": client_id,
        "payload": {
            "client_id": client_id,
            "business_type": body.business_type if body else None,
            "retry_count": body.retry_count if body else 0,
        },
    }
    try:
        result = await handle_smoke_test_zenya(task)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Falha ao executar smoke test: {e}",
        ) from e
