"""
ONB-3: Handler onboard_client_v2 — Configuração Automática da Zenya.

Pipeline: DNA extraction → soul_prompt generation → KB generation

REGRAS CRÍTICAS:
- Este handler NÃO clona workflows n8n (AC-4.1)
- Este handler NÃO toca nos 4 clientes existentes (AC-4.2)
- Soul prompt gerado APÓS DNA (ordem obrigatória — AC-3.1)
- KB gerada APÓS soul_prompt (AC-3.2)
- Workflows n8n nascem INATIVOS (não aplicável aqui — sem clone)
- zenya_clients.active = false, testing_mode = 'off' (AC-4.4)
- Cria config de Runtime (webhook Z-API → Runtime) em vez de n8n (AC-4.3)

Ativação automática:
  Disparado pelo service.py quando gate 'intake' passa (intake_complete=True)

Payload esperado:
{
    "client_id": "<uuid>",
    "additional_context": "<opcional: contexto extra>"
}
"""
from __future__ import annotations

import asyncio
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from runtime.config import settings
from runtime.db import supabase


# ── Helpers ───────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log_step(steps: list[dict], name: str, status: str, detail: str = "") -> None:
    entry = {
        "step": name,
        "status": status,
        "detail": detail[:500],
        "timestamp": _now(),
    }
    steps.append(entry)
    print(f"[onboard_client_v2] {name}: {status} — {detail[:120]}")


def _slug_from_name(name: str) -> str:
    """Gera slug URL-safe a partir do nome do negócio."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"zenya-{slug}"


# ── Step helpers ──────────────────────────────────────────────

async def _fetch_client(client_id: str) -> dict | None:
    """Busca dados do cliente no banco."""
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("clients")
            .select("id,name,niche,whatsapp,website,instagram,plan,status")
            .eq("id", client_id)
            .maybe_single()
            .execute()
        )
        return result.data if result else None
    except Exception as e:
        print(f"[onboard_client_v2] fetch_client error: {e}")
        return None


async def _fetch_intake_data(client_id: str) -> dict:
    """
    Busca intake_data da fase 'intake' do onboarding_workflows.
    Retorna dict vazio se não encontrado.
    """
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("onboarding_workflows")
            .select("intake_data,gate_details")
            .eq("client_id", client_id)
            .eq("phase", "intake")
            .maybe_single()
            .execute()
        )
        if result and result.data:
            intake_data = result.data.get("intake_data") or {}
            gate_details = result.data.get("gate_details") or {}
            # Merge gate_details como contexto adicional se disponível
            if isinstance(intake_data, dict):
                return intake_data
        return {}
    except Exception as e:
        print(f"[onboard_client_v2] fetch_intake_data error (non-fatal): {e}")
        return {}


async def _ensure_brain_space(client_id: str) -> bool:
    """
    AC-1.1: Verifica se brain_space existe para o cliente.
    Se não existir, cria via ensure logic.

    Retorna True se brain está pronto (chunks existem).
    """
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("brain_chunks")
            .select("id")
            .eq("brain_owner", client_id)
            .limit(1)
            .execute()
        )
        if result.data:
            return True

        # Tenta também por client_id
        result2 = await asyncio.to_thread(
            lambda: supabase.table("brain_chunks")
            .select("id")
            .eq("client_id", client_id)
            .limit(1)
            .execute()
        )
        return bool(result2.data)
    except Exception as e:
        print(f"[onboard_client_v2] ensure_brain_space error: {e}")
        return False


async def _ingest_intake_data_to_brain(
    client_id: str,
    intake_data: dict,
) -> int:
    """
    AC-1.2: Ingere dados do formulário WhatsApp como chunks no Brain.
    Source_type = 'intake_form'.

    Retorna número de chunks inseridos.
    """
    form_answers = intake_data.get("form_answers", [])
    if not form_answers:
        # Tenta intake_summary como alternativa
        summary = intake_data.get("summary", "")
        if not summary:
            return 0
        form_answers = [{"question": "Resumo intake", "answer": summary}]

    chunks_to_insert = []
    now = _now()

    for qa in form_answers:
        q = qa.get("question", "")
        a = qa.get("answer", "")
        if not (q and a):
            continue

        raw_content = f"Pergunta: {q}\nResposta: {a}"
        chunks_to_insert.append({
            "brain_owner": client_id,
            "client_id": client_id,
            "raw_content": raw_content,
            "source_type": "intake_form",
            "source_title": f"Formulário de onboarding: {q[:80]}",
            "persona": "zenya",
            "processed_stages": [],
            "created_at": now,
        })

    if not chunks_to_insert:
        return 0

    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("brain_chunks").insert(chunks_to_insert).execute()
        )
        inserted = len(result.data) if result.data else 0
        print(f"[onboard_client_v2] {inserted} chunks de intake inseridos no Brain")
        return inserted
    except Exception as e:
        print(f"[onboard_client_v2] ingest_intake_data error: {e}")
        return 0


async def _extract_dna(client_id: str, additional_context: str = "") -> dict:
    """
    AC-1.3: Extrai DNA do cliente usando handler existente.
    Roda sobre TODOS os chunks (site + Instagram + intake).
    """
    from runtime.tasks.handlers.extract_client_dna import handle_extract_client_dna

    task = {
        "id": f"onb3-dna-{client_id[:12]}",
        "task_type": "extract_client_dna",
        "payload": {
            "client_id": client_id,
            "additional_context": additional_context,
            "regenerate_prompt": False,  # Geramos nosso próprio soul_prompt depois
        },
    }
    return await handle_extract_client_dna(task)


async def _fetch_dna_items(client_id: str) -> list[dict]:
    """Busca itens de DNA da tabela client_dna."""
    result = await asyncio.to_thread(
        lambda: supabase.table("client_dna")
        .select("dna_type,key,title,content,confidence")
        .eq("client_id", client_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


async def _build_intake_summary(intake_data: dict) -> str:
    """Constrói resumo textual do intake para uso no soul_prompt/KB."""
    parts = []

    form_answers = intake_data.get("form_answers", [])
    for qa in form_answers:
        q = qa.get("question", "")
        a = qa.get("answer", "")
        if q and a:
            parts.append(f"- {q}: {a}")

    summary = intake_data.get("summary", "")
    if summary and not parts:
        parts.append(summary)

    return "\n".join(parts)


async def _update_gate_condition(
    client_id: str,
    phase: str,
    condition: str,
    value: bool,
) -> None:
    """Atualiza uma condição de gate no onboarding_workflows."""
    try:
        # Fetch current gate_details
        result = await asyncio.to_thread(
            lambda: supabase.table("onboarding_workflows")
            .select("gate_details")
            .eq("client_id", client_id)
            .eq("phase", phase)
            .maybe_single()
            .execute()
        )
        current = {}
        if result and result.data:
            current = result.data.get("gate_details") or {}

        current[condition] = value

        await asyncio.to_thread(
            lambda: supabase.table("onboarding_workflows")
            .update({
                "gate_details": current,
                "updated_at": _now(),
            })
            .eq("client_id", client_id)
            .eq("phase", phase)
            .execute()
        )
    except Exception as e:
        print(f"[onboard_client_v2] update_gate_condition error: {e}")


async def _save_soul_prompt_backup(
    client_id: str,
    business_name: str,
    soul_prompt: str,
) -> None:
    """
    AC-2.8: Salva backup do soul_prompt em notes.
    Isso permite auditoria e override manual.
    """
    try:
        note_row = {
            "client_id": client_id,
            "note_type": "soul_prompt_backup",
            "title": f"Soul Prompt — {business_name}",
            "content": soul_prompt,
            "source": "onboard_client_v2",
            "created_at": _now(),
        }
        await asyncio.to_thread(
            lambda: supabase.table("notes").insert(note_row).execute()
        )
    except Exception as e:
        print(f"[onboard_client_v2] save_soul_prompt_backup error (non-fatal): {e}")


async def _configure_runtime_webhook(
    client_id: str,
    business_name: str,
    webhook_path: str,
) -> dict:
    """
    AC-4.3: Cria configuração de Runtime (webhook Z-API → Runtime).

    Em vez de clonar n8n, registra o client_id como handler de webhooks
    no sistema de roteamento do Runtime.

    Salva em zenya_clients.webhook_config para referência.
    """
    runtime_base_url = getattr(settings, "runtime_base_url", "https://runtime.sparkleai.tech")
    webhook_url = f"{runtime_base_url}/zenya/webhook/{webhook_path}"

    config = {
        "type": "runtime",
        "webhook_path": webhook_path,
        "webhook_url": webhook_url,
        "character_slug": webhook_path,
        "routing": "zenya_router",
        "configured_at": _now(),
        "note": "Runtime webhook — configure Z-API para apontar para webhook_url",
    }

    try:
        await asyncio.to_thread(
            lambda: supabase.table("zenya_clients")
            .update({
                "webhook_config": config,
                "character_slug": webhook_path,
            })
            .eq("client_id", client_id)
            .execute()
        )
        print(
            f"[onboard_client_v2] Runtime webhook configurado: {webhook_url}"
        )
    except Exception as e:
        print(f"[onboard_client_v2] configure_runtime_webhook error (non-fatal): {e}")

    return config


async def _finalize_zenya_client(
    client_id: str,
    business_name: str,
    business_type: str,
    soul_prompt: str,
    webhook_path: str,
) -> None:
    """
    AC-4.4: Garante zenya_clients.active=false e testing_mode='off'.
    Atualiza campos de configuração final.
    """
    try:
        await asyncio.to_thread(
            lambda: supabase.table("zenya_clients")
            .update({
                "active": False,           # AC-4.4: nasce inativo
                "testing_mode": "off",     # AC-4.4: off até ONB-5 mudar para internal_testing
                "soul_prompt_generated": soul_prompt,
                "character_slug": webhook_path,
                "updated_at": _now(),
            })
            .eq("client_id", client_id)
            .execute()
        )
    except Exception as e:
        print(f"[onboard_client_v2] finalize_zenya_client error: {e}")


# ── Main handler ──────────────────────────────────────────────

async def handle_onboard_client_v2(task: dict) -> dict:
    """
    ONB-3: Pipeline completo de configuração da Zenya.

    Sequência:
      Track A: Brain Setup
        A.1: ensure_client_brain_space
        A.2: ingest intake_data como chunks (source_type=intake_form)
        A.3: extract_client_dna (sobre TODOS os chunks)

      Track B: Zenya Instance Setup (após A.3)
        B.1: generate_soul_prompt (INPUT: DNA + intake + template vertical)
        B.2: generate_kb (INPUT: DNA + soul_prompt + intake)
        B.3: salvar em zenya_clients + zenya_knowledge_base + notes

      Gate 3: config_complete
        - Verifica brain_ready, soul_prompt_ready, kb_ready
        - Se passa → avança fase para test_internal

    Payload:
        client_id (str, required)
        additional_context (str, optional)
    """
    payload = task.get("payload", {})
    client_id = payload.get("client_id")

    if not client_id:
        return {"status": "error", "error": "client_id é obrigatório"}

    additional_context = payload.get("additional_context", "")
    steps: list[dict] = []
    config_phase = "config"

    # ── Buscar dados do cliente ───────────────────────────────

    client = await _fetch_client(client_id)
    if not client:
        return {
            "status": "error",
            "error": f"Cliente não encontrado: {client_id}",
        }

    business_name = client.get("name", "Negócio")
    business_type = client.get("niche") or "generico"
    webhook_path = _slug_from_name(business_name)

    print(
        f"[onboard_client_v2] Iniciando configuração para '{business_name}' "
        f"({client_id[:12]}...) — vertical: {business_type}"
    )

    # ── Marcar fase config como in_progress ──────────────────

    try:
        await asyncio.to_thread(
            lambda: supabase.table("onboarding_workflows")
            .update({"status": "in_progress", "started_at": _now(), "updated_at": _now()})
            .eq("client_id", client_id)
            .eq("phase", config_phase)
            .execute()
        )
    except Exception as e:
        print(f"[onboard_client_v2] WARN: falha ao marcar config in_progress: {e}")

    # ── Fetch intake_data ─────────────────────────────────────

    intake_data = await _fetch_intake_data(client_id)
    intake_summary = await _build_intake_summary(intake_data)

    # ============================================================
    # TRACK A — Brain Setup
    # ============================================================

    # A.1: Verificar brain space
    brain_has_chunks = await _ensure_brain_space(client_id)
    _log_step(
        steps, "A1_ensure_brain_space",
        "ok" if brain_has_chunks else "warning",
        f"Brain {'tem' if brain_has_chunks else 'sem'} chunks para {client_id[:12]}",
    )

    # A.2: Ingerir intake_data como chunks adicionais (AC-1.2)
    intake_chunks_inserted = await _ingest_intake_data_to_brain(client_id, intake_data)
    _log_step(
        steps, "A2_ingest_intake_to_brain",
        "ok" if intake_chunks_inserted > 0 else "skipped",
        f"{intake_chunks_inserted} chunks de intake inseridos no Brain",
    )

    if intake_chunks_inserted > 0:
        brain_has_chunks = True

    # Verificar se temos material suficiente para extração
    if not brain_has_chunks:
        _log_step(
            steps, "A3_extract_dna",
            "error",
            "Sem chunks no Brain — intake não processado e site não ingerido.",
        )
        error_msg = (
            "Nenhum chunk encontrado no Brain para este cliente. "
            "Garanta que o intake (site, Instagram ou formulário) foi processado antes de configurar a Zenya."
        )
        await asyncio.to_thread(
            lambda: supabase.table("onboarding_workflows")
            .update({
                "status": "failed",
                "error_log": {"error": error_msg, "step": "A3_extract_dna"},
                "updated_at": _now(),
            })
            .eq("client_id", client_id)
            .eq("phase", config_phase)
            .execute()
        )
        return {
            "status": "error",
            "client_id": client_id,
            "error": error_msg,
            "steps": steps,
        }

    # A.3: Extrair DNA (AC-1.3)
    dna_result = {}
    try:
        context_for_dna = additional_context
        if intake_summary:
            context_for_dna = (
                f"{additional_context}\n\n=== INTAKE DO CLIENTE ===\n{intake_summary}"
                if additional_context
                else f"=== INTAKE DO CLIENTE ===\n{intake_summary}"
            )

        dna_result = await _extract_dna(client_id, context_for_dna)

        if "error" in dna_result:
            raise ValueError(dna_result["error"])

        items_extracted = dna_result.get("items_extracted", 0)
        categories_covered = len(dna_result.get("categories", {}))

        _log_step(
            steps, "A3_extract_dna",
            "ok",
            f"{items_extracted} itens extraídos em {categories_covered} categorias",
        )

        # Marcar brain_ready no gate da fase config (AC-5.1)
        await _update_gate_condition(client_id, config_phase, "brain_ready", True)

    except Exception as e:
        _log_step(steps, "A3_extract_dna", "error", str(e)[:300])

        # AC-3.1: Se DNA falhar, soul_prompt NÃO é gerado — fase config fica failed
        error_msg = f"Falha na extração de DNA: {e}"
        try:
            await asyncio.to_thread(
                lambda: supabase.table("onboarding_workflows")
                .update({
                    "status": "failed",
                    "error_log": {"error": error_msg, "step": "A3_extract_dna"},
                    "updated_at": _now(),
                })
                .eq("client_id", client_id)
                .eq("phase", config_phase)
                .execute()
            )
        except Exception:
            pass

        return {
            "status": "error",
            "client_id": client_id,
            "error": error_msg,
            "steps": steps,
        }

    # AC-1.4: DNA salvo na tabela client_dna (feito pelo extract_client_dna handler)
    # e em zenya_clients.client_dna (blob) — já feito pelo handler

    # ============================================================
    # TRACK B — Zenya Instance Setup
    # ============================================================

    # B.1: Buscar DNA items e gerar soul_prompt (AC-2.2)
    # AC-3.1: Soul prompt SEMPRE após DNA
    from runtime.onboarding.soul_prompt_generator import (
        generate_soul_prompt,
        save_soul_prompt_to_db,
    )

    dna_items = await _fetch_dna_items(client_id)

    if not dna_items:
        _log_step(steps, "B1_generate_soul_prompt", "error", "DNA items não encontrados após extração")
        return {
            "status": "error",
            "client_id": client_id,
            "error": "DNA items não encontrados após extração bem-sucedida. Inconsistência no banco.",
            "steps": steps,
        }

    soul_prompt = ""
    try:
        soul_prompt = await generate_soul_prompt(
            client_id=client_id,
            dna_items=dna_items,
            business_name=business_name,
            business_type=business_type,
            intake_summary=intake_summary,
            task_id=f"onb3-soul-{client_id[:12]}",
        )

        if not soul_prompt or len(soul_prompt) < 200:
            raise ValueError(
                f"Soul prompt gerado é muito curto ({len(soul_prompt)} chars). "
                "Dados insuficientes para personalização."
            )

        await save_soul_prompt_to_db(client_id, soul_prompt)
        await _save_soul_prompt_backup(client_id, business_name, soul_prompt)

        _log_step(
            steps, "B1_generate_soul_prompt",
            "ok",
            f"{len(soul_prompt)} chars gerados com DNA de {len(dna_items)} itens",
        )

        # Marcar soul_prompt_ready no gate (AC-5.1)
        await _update_gate_condition(client_id, config_phase, "soul_prompt_ready", True)

    except Exception as e:
        _log_step(steps, "B1_generate_soul_prompt", "error", str(e)[:300])

        # AC-3.2: KB não é gerada se soul_prompt falhou
        error_msg = f"Falha ao gerar soul_prompt: {e}"
        try:
            await asyncio.to_thread(
                lambda: supabase.table("onboarding_workflows")
                .update({
                    "status": "failed",
                    "error_log": {"error": error_msg, "step": "B1_generate_soul_prompt"},
                    "updated_at": _now(),
                })
                .eq("client_id", client_id)
                .eq("phase", config_phase)
                .execute()
            )
        except Exception:
            pass

        return {
            "status": "error",
            "client_id": client_id,
            "error": error_msg,
            "steps": steps,
        }

    # B.2: Gerar KB (AC-2.5) — AC-3.2: APÓS soul_prompt
    from runtime.onboarding.kb_generator import generate_kb, save_kb_to_db, count_kb_items

    kb_items = []
    try:
        kb_items = await generate_kb(
            client_id=client_id,
            business_name=business_name,
            business_type=business_type,
            dna_items=dna_items,
            soul_prompt=soul_prompt,
            intake_data=intake_data,
            task_id=f"onb3-kb-{client_id[:12]}",
        )

        if not kb_items:
            raise ValueError("KB gerada está vazia")

        _log_step(
            steps, "B2_generate_kb",
            "ok" if len(kb_items) >= 15 else "warning",
            f"{len(kb_items)} itens de KB gerados",
        )

    except Exception as e:
        _log_step(steps, "B2_generate_kb", "error", str(e)[:300])
        # KB é não-bloqueante — registramos erro mas continuamos
        print(f"[onboard_client_v2] WARN: falha ao gerar KB: {e}")

    # B.3: Salvar KB no banco (AC-2.8)
    kb_inserted = 0
    if kb_items:
        try:
            kb_inserted = await save_kb_to_db(client_id, kb_items)
            _log_step(
                steps, "B3_save_kb",
                "ok",
                f"{kb_inserted} itens salvos em zenya_knowledge_base",
            )

            # Marcar kb_ready se temos itens suficientes (AC-5.1)
            kb_count = await count_kb_items(client_id)
            if kb_count >= 15:
                await _update_gate_condition(client_id, config_phase, "kb_ready", True)
            else:
                print(
                    f"[onboard_client_v2] WARN: KB com apenas {kb_count} itens "
                    f"(mínimo 15 para gate). kb_ready não marcado."
                )

        except Exception as e:
            _log_step(steps, "B3_save_kb", "error", str(e)[:300])
            print(f"[onboard_client_v2] ERRO ao salvar KB: {e}")

    # ── Configurar Runtime webhook (AC-4.3) ────────────────────

    webhook_config = {}
    try:
        webhook_config = await _configure_runtime_webhook(
            client_id=client_id,
            business_name=business_name,
            webhook_path=webhook_path,
        )
        _log_step(
            steps, "B4_configure_runtime_webhook",
            "ok",
            f"Webhook path: {webhook_path}",
        )
    except Exception as e:
        _log_step(steps, "B4_configure_runtime_webhook", "warning", str(e)[:200])

    # ── Finalizar zenya_clients (AC-4.4) ──────────────────────

    await _finalize_zenya_client(
        client_id=client_id,
        business_name=business_name,
        business_type=business_type,
        soul_prompt=soul_prompt,
        webhook_path=webhook_path,
    )

    # ── Verificar gate config_complete (AC-5.1) ───────────────

    from runtime.onboarding.service import check_gate, PHASE_CONDITIONS

    gate_conditions = PHASE_CONDITIONS.get(config_phase, [])
    gate_result = await check_gate(client_id, config_phase, gate_conditions)

    gate_passed = gate_result.get("passed", False)
    missing_conditions = gate_result.get("missing", [])

    if gate_passed:
        _log_step(
            steps, "gate_config_complete",
            "ok",
            f"Gate passou! Próxima fase: {gate_result.get('next_phase', 'test_internal')}",
        )
    else:
        _log_step(
            steps, "gate_config_complete",
            "warning",
            f"Gate não passou. Condições faltando: {missing_conditions}",
        )

    # ── Summary ───────────────────────────────────────────────

    ok_steps = [s for s in steps if s["status"] == "ok"]
    warn_steps = [s for s in steps if s["status"] == "warning"]
    err_steps = [s for s in steps if s["status"] == "error"]

    overall_status = "completed" if gate_passed else (
        "partial" if not err_steps else "error"
    )

    summary = (
        f"Configuração da Zenya de '{business_name}': {overall_status.upper()}.\n"
        f"  DNA: {dna_result.get('items_extracted', 0)} itens extraídos\n"
        f"  Soul prompt: {len(soul_prompt)} chars\n"
        f"  KB: {kb_inserted} itens salvos\n"
        f"  Gate config: {'PASSOU' if gate_passed else 'PENDENTE'}"
    )
    if missing_conditions:
        summary += f"\n  Condições faltando: {missing_conditions}"

    print(f"[onboard_client_v2] {summary}")

    return {
        "status": overall_status,
        "client_id": client_id,
        "business_name": business_name,
        "steps": steps,
        "dna_items_extracted": dna_result.get("items_extracted", 0),
        "dna_categories": dna_result.get("categories", {}),
        "soul_prompt_chars": len(soul_prompt),
        "kb_items_count": kb_inserted,
        "webhook_path": webhook_path,
        "gate_passed": gate_passed,
        "gate_missing": missing_conditions,
        "summary": summary,
        "message": summary,
    }
