"""
Handler intake_form_whatsapp — ONB-2: Formulário WhatsApp sequencial.

Envia perguntas uma por vez via Z-API, salva respostas em intake_form_state.
Máximo 8 perguntas (benchmark PME).

ACs implementados:
- AC-3.1: handler registrado no registry (vide registry.py)
- AC-3.2: perguntas enviadas uma por vez via Z-API
- AC-3.3: template selecionado por business_type
- AC-3.4: respostas salvas em intake_form_state + intake_data no workflow
- AC-3.5: lembrete automático se sem resposta em 24h
- AC-3.6: após 2 lembretes (48h), marcar como partial e alertar Friday
- AC-3.7: se phone vazio, pula silenciosamente

Modo de operação:
- action="start": envia a primeira pergunta
- action="answer": registra resposta e envia a próxima pergunta
- action="reminder": envia lembrete para a pergunta atual
- action="check_timeouts": verifica todos os forms pendentes (cron job)
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional

from runtime.config import settings
from runtime.db import supabase
from runtime.onboarding.intake_templates import get_questions


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


async def _send_whatsapp(phone: str, message: str) -> None:
    """Envia mensagem WhatsApp via Z-API. Falha silenciosamente."""
    try:
        from runtime.integrations.zapi import send_text
        await asyncio.to_thread(send_text, phone, message)
        print(f"[intake_form] WhatsApp enviado para {phone[:8]}...")
    except Exception as e:
        print(f"[intake_form] WARN: falha ao enviar WhatsApp para {phone[:8]}...: {e}")


async def _alert_friday(message: str) -> None:
    """Alerta Friday (Mauro) via WhatsApp."""
    mauro_phone = settings.mauro_whatsapp
    if not mauro_phone:
        print(f"[intake_form] WARN: MAURO_WHATSAPP nao configurado — alerta perdido: {message}")
        return
    try:
        from runtime.integrations.zapi import send_text
        await asyncio.to_thread(send_text, mauro_phone, f"[Friday/Onboarding] {message}")
    except Exception as e:
        print(f"[intake_form] WARN: falha ao alertar Friday: {e}")


async def _get_form_state(client_id: str) -> Optional[dict]:
    """Busca estado atual do formulário para o cliente."""
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("intake_form_state")
            .select("*")
            .eq("client_id", client_id)
            .maybe_single()
            .execute()
        )
        return result.data if result else None
    except Exception as e:
        print(f"[intake_form] falha ao buscar form_state: {e}")
        return None


async def _upsert_form_state(state: dict) -> None:
    """Persiste estado do formulário."""
    state["updated_at"] = _now()
    try:
        await asyncio.to_thread(
            lambda: supabase.table("intake_form_state")
            .upsert(state, on_conflict="client_id")
            .execute()
        )
    except Exception as e:
        print(f"[intake_form] WARN: falha ao salvar form_state: {e}")


async def _save_answers_to_workflow(client_id: str, answers: list, complete: bool, partial: bool) -> None:
    """Persiste respostas no intake_data do workflow de intake."""
    from runtime.onboarding.consolidator import consolidate_intake
    try:
        await consolidate_intake(
            client_id=client_id,
            form_answers=answers,
            form_complete=complete,
            form_partial=partial,
        )
    except Exception as e:
        print(f"[intake_form] WARN: falha ao consolidar intake: {e}")


# ── Actions ────────────────────────────────────────────────────

async def _action_start(client_id: str, phone: str, business_type: str, client_name: str) -> dict:
    """
    Inicia o formulário: cria estado e envia a primeira pergunta.
    Idempotente: se já existe estado não-completado, continua de onde parou.
    """
    # AC-3.7: sem phone, pula
    if not phone:
        print(f"[intake_form] phone vazio para client_id={client_id} — skip")
        return {"skipped": True, "reason": "phone nao fornecido"}

    questions = get_questions(business_type)
    if not questions:
        return {"error": "sem perguntas para business_type"}

    # Verificar se já existe estado
    existing = await _get_form_state(client_id)
    if existing and existing.get("completed"):
        return {"skipped": True, "reason": "formulario ja completado", "completed": True}

    # Estado inicial
    state = {
        "client_id": client_id,
        "phone": phone,
        "business_type": business_type,
        "current_question": 0,
        "answers": [],
        "reminder_count": 0,
        "last_sent_at": _now(),
        "completed": False,
        "partial": False,
    }
    if existing:
        # Retoma de onde parou
        state["current_question"] = existing.get("current_question", 0)
        state["answers"] = existing.get("answers") or []

    await _upsert_form_state(state)

    q_idx = state["current_question"]
    first_name = client_name.split()[0] if client_name else "você"

    # Introdução + primeira pergunta
    intro = (
        f"Olá {first_name}! Sou da Sparkle e vou configurar a Zenya para o seu negócio. "
        f"Tenho só {len(questions)} perguntinhas rápidas para personalizar tudo para você. "
        f"Pode responder quando tiver um tempinho!"
    )
    await _send_whatsapp(phone, intro)

    # Pequena pausa para não parecer spam
    await asyncio.sleep(1)

    question_msg = f"({q_idx + 1}/{len(questions)}) {questions[q_idx]}"
    await _send_whatsapp(phone, question_msg)

    return {
        "started": True,
        "question_sent": q_idx + 1,
        "total_questions": len(questions),
        "question_text": questions[q_idx],
    }


async def _action_answer(client_id: str, answer_text: str) -> dict:
    """
    Registra resposta e envia próxima pergunta (se houver).
    """
    state = await _get_form_state(client_id)
    if not state:
        return {"error": f"form_state nao encontrado para client_id={client_id}"}

    if state.get("completed") or state.get("partial"):
        return {"skipped": True, "reason": "formulario ja encerrado"}

    phone = state.get("phone", "")
    business_type = state.get("business_type", "")
    questions = get_questions(business_type)
    current_q = state.get("current_question", 0)

    # Salva resposta
    answers: list = state.get("answers") or []
    answers.append({
        "question": questions[current_q] if current_q < len(questions) else "",
        "answer": answer_text,
        "answered_at": _now(),
    })

    next_q = current_q + 1

    if next_q >= len(questions):
        # Formulário completo
        state.update({
            "current_question": next_q,
            "answers": answers,
            "reminder_count": 0,
            "last_sent_at": _now(),
            "completed": True,
        })
        await _upsert_form_state(state)
        await _save_answers_to_workflow(client_id, answers, complete=True, partial=False)

        if phone:
            await _send_whatsapp(
                phone,
                "Perfeito! Recebi todas as informações. "
                "Nossa equipe vai configurar sua Zenya agora. "
                "Em breve entraremos em contato!"
            )

        return {
            "completed": True,
            "answers_count": len(answers),
            "message": "Formulario completado",
        }
    else:
        # Próxima pergunta
        state.update({
            "current_question": next_q,
            "answers": answers,
            "reminder_count": 0,
            "last_sent_at": _now(),
        })
        await _upsert_form_state(state)

        if phone:
            q_msg = f"({next_q + 1}/{len(questions)}) {questions[next_q]}"
            await _send_whatsapp(phone, q_msg)

        return {
            "completed": False,
            "question_sent": next_q + 1,
            "total_questions": len(questions),
            "answers_count": len(answers),
        }


async def _action_reminder(client_id: str) -> dict:
    """
    Envia lembrete para a pergunta atual.
    AC-3.5: lembrete automático após 24h sem resposta.
    AC-3.6: após 2 lembretes (48h), marcar como partial e alertar Friday.
    """
    state = await _get_form_state(client_id)
    if not state:
        return {"error": f"form_state nao encontrado para client_id={client_id}"}

    if state.get("completed") or state.get("partial"):
        return {"skipped": True, "reason": "formulario ja encerrado"}

    phone = state.get("phone", "")
    business_type = state.get("business_type", "")
    questions = get_questions(business_type)
    current_q = state.get("current_question", 0)
    reminder_count = state.get("reminder_count", 0)
    answers: list = state.get("answers") or []

    if not phone:
        return {"skipped": True, "reason": "phone nao disponivel"}

    # AC-3.6: após 2 lembretes, marcar partial
    if reminder_count >= 2:
        state.update({
            "partial": True,
            "updated_at": _now(),
        })
        await _upsert_form_state(state)
        await _save_answers_to_workflow(client_id, answers, complete=False, partial=True)

        # Alerta Friday
        await _alert_friday(
            f"Cliente {client_id[:12]}... não respondeu o formulário de intake após 2 lembretes "
            f"({len(answers)}/{len(questions)} respostas). Intake marcado como partial."
        )
        return {
            "partial": True,
            "answers_count": len(answers),
            "message": "Intake marcado como partial apos 2 lembretes",
        }

    # AC-3.5: envia lembrete
    question_text = questions[current_q] if current_q < len(questions) else ""

    # Busca nome do cliente
    client_name = ""
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("clients")
            .select("name")
            .eq("id", client_id)
            .maybe_single()
            .execute()
        )
        if result and result.data:
            client_name = (result.data.get("name") or "").split()[0]
    except Exception:
        pass

    reminder_msg = (
        f"Oi {client_name or 'você'}! Estamos configurando sua Zenya. "
        f"Só falta responder a pergunta anterior para continuarmos: "
        f"({current_q + 1}/{len(questions)}) {question_text}"
    )
    await _send_whatsapp(phone, reminder_msg)

    state.update({
        "reminder_count": reminder_count + 1,
        "last_sent_at": _now(),
    })
    await _upsert_form_state(state)

    return {
        "reminder_sent": True,
        "reminder_count": reminder_count + 1,
        "question_index": current_q + 1,
    }


async def _action_check_timeouts() -> dict:
    """
    Verifica todos os formulários pendentes e envia lembretes se necessário.
    Chamado pelo cron job de onboarding.

    - Sem resposta por >= 24h: envia lembrete
    - Sem resposta por >= 48h (reminder_count >= 1): envia segundo lembrete
    - Sem resposta por >= 72h (reminder_count >= 2): marca partial
    """
    now = _now_dt()
    reminded = 0
    partial_count = 0

    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("intake_form_state")
            .select("*")
            .eq("completed", False)
            .eq("partial", False)
            .execute()
        )
        pending = result.data or []
    except Exception as e:
        return {"error": str(e), "reminded": 0}

    for state in pending:
        client_id = state["client_id"]
        last_sent_raw = state.get("last_sent_at")
        if not last_sent_raw:
            continue

        try:
            last_sent = datetime.fromisoformat(last_sent_raw.replace("Z", "+00:00"))
            hours_elapsed = (now - last_sent).total_seconds() / 3600
        except Exception:
            continue

        reminder_count = state.get("reminder_count", 0)

        if hours_elapsed >= 24:
            # Tempo de lembrete
            fake_task = {"payload": {"client_id": client_id}, "client_id": client_id}
            result_r = await _action_reminder(client_id)
            if result_r.get("partial"):
                partial_count += 1
            elif result_r.get("reminder_sent"):
                reminded += 1

    return {
        "pending_checked": len(pending),
        "reminders_sent": reminded,
        "partial_marked": partial_count,
        "timestamp": now.isoformat(),
    }


# ── Main handler ──────────────────────────────────────────────

async def handle_intake_form_whatsapp(task: dict) -> dict:
    """
    Handler principal para formulário WhatsApp sequencial de intake.

    Payload:
    {
        "action": "start" | "answer" | "reminder" | "check_timeouts",
        "client_id": "...",
        "phone": "...",             // para action=start
        "business_type": "...",     // para action=start
        "client_name": "...",       // para action=start
        "answer_text": "...",       // para action=answer
    }
    """
    payload = task.get("payload", {})
    action = payload.get("action", "start")
    client_id: Optional[str] = payload.get("client_id") or task.get("client_id")

    if action == "check_timeouts":
        return await _action_check_timeouts()

    if not client_id:
        return {"error": "client_id obrigatorio"}

    if action == "start":
        phone = payload.get("phone", "")
        business_type = payload.get("business_type", "generico")
        client_name = payload.get("client_name", "")
        return await _action_start(client_id, phone, business_type, client_name)

    elif action == "answer":
        answer_text = payload.get("answer_text", "").strip()
        if not answer_text:
            return {"error": "answer_text obrigatorio para action=answer"}
        return await _action_answer(client_id, answer_text)

    elif action == "reminder":
        return await _action_reminder(client_id)

    else:
        return {"error": f"action desconhecida: '{action}'"}
