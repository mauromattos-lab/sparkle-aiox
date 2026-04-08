"""
Chat handler — conversa livre com a Friday.
Activated when intent = "chat" (perguntas, bate-papo, tudo que não é tarefa estruturada).

Persona: Friday é a assistente executiva do Mauro Mattos, fundador da Sparkle AIOX.
Ela conhece o ecossistema, os clientes, o MRR e os agentes ativos.
Modelo: claude-sonnet-4-6 — conversa real merece modelo real.

Sprint 3:
- Datetime injetado no system prompt (fuso horário de Brasília)
- Histórico de conversa por número (últimas 5 mensagens do Supabase)

W1-FRIDAY-1:
- Brain consultado antes de cada resposta (namespace mauro-personal)
- System prompt com persona Friday completa + contexto Brain injetado
- Registro em friday_context_log a cada interação de chat
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from runtime.config import settings
from runtime.db import supabase
from runtime.utils.llm import call_claude
from runtime.friday.brain_context import (
    build_friday_system_prompt,
    get_friday_brain_context,
    get_mauro_dna_context,
    log_friday_context,
)

_TZ_BRASILIA = ZoneInfo("America/Sao_Paulo")

# Contexto operacional complementar — adicionado ao system prompt da Friday
# junto com o prompt de persona do brain_context.py
_FRIDAY_OPERATIONAL_CONTEXT = """
CONTEXTO OPERACIONAL
Idioma: português brasileiro.
Interface: WhatsApp — respostas curtas e objetivas, sem markdown excessivo.

SPARKLE AIOX
Empresa de IA aplicada ao marketing e atendimento para PMEs brasileiras.
Stack: Sparkle Runtime (FastAPI) + Claude API + Z-API + Supabase + Groq Whisper.

CLIENTES ATIVOS (MRR total: R$4.594/mês)
- Vitalis Life (João Lúcio) — Tráfego pago Google+Meta Ads — R$1.500/mês
- Alexsandro Confeitaria — Zenya chatbot WhatsApp — R$500/mês
- Ensinaja (Douglas) — Zenya escola Guaratinguetá — R$650/mês
- Plaka (Luiza/Roberta) — Zenya SAC — R$297/mês
- Fun Personalize (Julia Gomes) — Zenya Premium — R$897/mês
- Gabriela — Meta Ads consórcio — R$750/mês

AGENTES AIOS DISPONÍVEIS
@dev (Dex), @qa, @architect, @analyst, @pm, @po, @sm, @squad-creator, @devops

REGRAS
- Responda sempre em português
- Seja concisa — WhatsApp não é lugar para redação
- Quando não souber algo específico, diga claramente e sugira próximo passo
- Nunca invente dados — se não tiver certeza, sinalize
- Use o histórico de conversa para manter contexto e continuidade natural
"""


def _get_current_datetime() -> str:
    """Retorna data e hora atual no fuso de Brasília em português."""
    now = datetime.now(_TZ_BRASILIA)
    # Formatar manualmente para português sem depender de locale do sistema
    dias_semana = {
        0: "segunda-feira",
        1: "terça-feira",
        2: "quarta-feira",
        3: "quinta-feira",
        4: "sexta-feira",
        5: "sábado",
        6: "domingo",
    }
    meses = {
        1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
        5: "maio", 6: "junho", 7: "julho", 8: "agosto",
        9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro",
    }
    dia_semana = dias_semana[now.weekday()]
    mes = meses[now.month]
    return f"{dia_semana}, {now.day:02d} de {mes} de {now.year} às {now.hour:02d}:{now.minute:02d}"


async def _get_history(phone: str, limit: int = 5) -> list[dict]:
    """Busca histórico de conversa do número (ordem cronológica)."""
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("conversation_history")
            .select("role,content")
            .eq("phone", phone)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        # Inverter para ordem cronológica (mais antigo primeiro)
        return list(reversed(res.data or []))
    except Exception as e:
        print(f"[chat] history fetch failed: {e}")
        return []


async def _save_to_history(phone: str, user_msg: str, assistant_msg: str) -> None:
    """Salva par de mensagens no histórico com timestamps distintos (BUG-02 fix)."""
    try:
        now = datetime.now(timezone.utc)
        await asyncio.to_thread(
            lambda: supabase.table("conversation_history").insert([
                {"phone": phone, "role": "user", "content": user_msg, "created_at": now.isoformat()},
                {"phone": phone, "role": "assistant", "content": assistant_msg, "created_at": (now + timedelta(seconds=1)).isoformat()},
            ]).execute()
        )
    except Exception as e:
        print(f"[chat] history save failed: {e}")


async def handle_chat(task: dict) -> dict:
    """
    Conversa livre com Claude Sonnet usando a persona da Friday.
    W1-FRIDAY-1: Consulta Brain (namespace mauro-personal) antes de responder.
    Injeta datetime atual + histórico de conversa + contexto Brain no system prompt.
    Recebe o task dict com payload.original_text e retorna {"message": "<resposta>"}
    """
    payload = task.get("payload", {})
    user_text = payload.get("original_text", "")

    if not user_text:
        return {"message": "Recebi uma mensagem vazia. Pode repetir?"}

    task_id = task.get("id")
    phone = payload.get("from_number") or "internal"

    # --- W1-FRIDAY-1 + W2-FRIDAY-1: Consultar Brain e DNA em paralelo ---
    (brain_context, chunks_retrieved, fallback_used), dna_context = await asyncio.gather(
        get_friday_brain_context(user_text),
        get_mauro_dna_context(),
    )

    # --- Registrar consulta em friday_context_log (fire and forget) ---
    asyncio.create_task(log_friday_context(
        interaction_id=task_id,
        chunks_retrieved=chunks_retrieved,
        used_in_response=True,
        fallback_used=fallback_used,
    ))

    # --- Montar system prompt com persona Friday + contexto Brain + DNA ---
    friday_persona_prompt = build_friday_system_prompt(brain_context, dna_context)
    current_datetime = _get_current_datetime()
    system_prompt = (
        friday_persona_prompt
        + _FRIDAY_OPERATIONAL_CONTEXT
        + f"\nData e hora atual: {current_datetime} (horário de Brasília)\n"
    )

    # --- Histórico de conversa ---
    history = await _get_history(phone)
    history_text = ""
    for msg in history:
        role_label = "Mauro" if msg["role"] == "user" else "Friday"
        history_text += f"{role_label}: {msg['content']}\n"

    if history_text:
        prompt_with_history = f"{history_text}Mauro: {user_text}\nFriday:"
    else:
        prompt_with_history = user_text

    # --- Chamada ao Claude ---
    response = await call_claude(
        prompt=prompt_with_history,
        system=system_prompt,
        model="claude-sonnet-4-6",
        client_id=settings.sparkle_internal_client_id,
        task_id=task_id,
        agent_id="friday",
        purpose="friday_chat",
        max_tokens=512,
    )

    # --- Salva no histórico ---
    await _save_to_history(phone, user_text, response)

    return {"message": response}
