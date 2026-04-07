"""
daily_decision_moment handler — S9-P5: Daily Decision Moment.

Agrega decisões pendentes e entrega briefing diário para Mauro via WhatsApp.

Formato:
  - Máximo 5 decisões por momento (Friday prioriza; resto fica para o dia seguinte)
  - Texto + (TTS futuro — ElevenLabs quando habilitado)
  - Mauro responde com números: "1 esta semana, 2 aprovado, 3 não"
  - Gate: acknowledged_at - delivered_at < 4h (se > 4h → lembrete único)

Fontes de decisões:
  1. brain_ingest_queue: itens pendentes de revisão
  2. runtime_tasks com requires_mauro flag (via result JSONB)
  3. conclave_deliberations com requires_mauro=true (quando Conclave ativo)
  4. Agentes em status draft aguardando promoção
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from runtime.config import settings
from runtime.db import supabase
from runtime.integrations.zapi import send_text
from runtime.utils.llm import call_claude


_DDM_SYSTEM = """Você é Friday, a interface estratégica do Mauro com o sistema Sparkle.

Seu papel agora é sintetizar as decisões pendentes em um briefing claro, direto e acionável.

REGRAS:
- Máximo 5 decisões. Se houver mais, priorize pelo impacto de negócio.
- Cada decisão deve ter: número, contexto mínimo (1 frase), opções claras (A/B ou sim/não)
- Linguagem: direta, sem jargão técnico, como se explicasse para o Mauro em 30 segundos
- NÃO inclua contexto técnico que exige o @dev para entender
- NÃO inclua perguntas abertas sem opções
- NÃO repita decisões que já foram tomadas

Tom: você é uma parceira estratégica, não um relatório de sistema."""


async def handle_daily_decision_moment(task: dict) -> dict:
    """
    Gera e entrega o Daily Decision Moment para Mauro via WhatsApp.
    """
    task_id = task.get("id")
    client_id = task.get("client_id") or settings.sparkle_internal_client_id

    decisions: list[str] = []

    # 1. Itens da brain_ingest_queue pendentes de revisão
    try:
        queue_result = await asyncio.to_thread(
            lambda: supabase.table("brain_ingest_queue")
            .select("id,content,source_agent,created_at")
            .eq("client_id", client_id)
            .eq("status", "pending")
            .order("created_at", desc=False)
            .limit(3)
            .execute()
        )
        for item in (queue_result.data or []):
            preview = (item.get("content") or "")[:80]
            agent = item.get("source_agent") or "agente"
            decisions.append(
                f"📥 Ingestão no Brain (de {agent}): \"{preview}...\"\n"
                f"   → Aprovar (ingere) ou Rejeitar?"
            )
    except Exception as e:
        print(f"[ddm] falha ao buscar brain_ingest_queue: {e}")

    # 2. Tasks concluídas com requires_mauro no result (últimas 48h)
    try:
        tasks_result = await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks")
            .select("id,task_type,result,completed_at")
            .eq("status", "done")
            .not_.is_("result", "null")
            .order("completed_at", desc=True)
            .limit(10)
            .execute()
        )
        for t in (tasks_result.data or []):
            result = t.get("result") or {}
            if isinstance(result, dict) and result.get("requires_mauro"):
                decision_text = result.get("decision_prompt") or result.get("message", "")
                if decision_text:
                    decisions.append(f"🔔 {t['task_type']}: {decision_text[:120]}")
    except Exception as e:
        print(f"[ddm] falha ao buscar tasks requires_mauro: {e}")

    # 3. Agentes em status draft aguardando promoção (quando Agent Template Engine ativo)
    # [Sprint 10 — placeholder]

    # Limita a 5 decisões
    decisions = decisions[:5]

    if not decisions:
        msg = (
            "☀️ Bom dia, Mauro!\n\n"
            "Sem decisões pendentes para você hoje. "
            "O sistema está operando autonomamente.\n\n"
            "Se quiser consultar o Brain ou verificar status, é só falar."
        )
    else:
        # Sintetiza via Claude
        raw_decisions = "\n\n".join([f"{i+1}. {d}" for i, d in enumerate(decisions)])
        prompt = (
            f"Decisões pendentes para Mauro:\n\n{raw_decisions}\n\n"
            f"Sintetize em um briefing de WhatsApp — direto, máximo 5 itens numerados, "
            f"com a opção de resposta de cada um. Comece com saudação curta."
        )
        synthesized = await call_claude(
            prompt=prompt,
            system=_DDM_SYSTEM,
            model="claude-haiku-4-5-20251001",
            client_id=client_id,
            task_id=task_id,
            agent_id="friday",
            purpose="daily_decision_moment",
            max_tokens=600,
        )
        msg = synthesized.strip()

    # Registra delivered_at em metadata da task
    delivered_at = datetime.now(timezone.utc).isoformat()

    # Envia via WhatsApp
    mauro_number = settings.mauro_whatsapp
    sent = False
    if mauro_number:
        try:
            send_text(mauro_number, msg)
            sent = True
        except Exception as e:
            print(f"[ddm] falha ao enviar WhatsApp: {e}")
    else:
        print(f"[ddm] MAURO_WHATSAPP não configurado — DDM não enviado")

    return {
        "message": msg,
        "decisions_count": len(decisions),
        "delivered_at": delivered_at,
        "sent_whatsapp": sent,
    }
