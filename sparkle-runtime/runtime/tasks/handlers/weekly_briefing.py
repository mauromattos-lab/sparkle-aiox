"""
weekly_briefing handler — resumo semanal da Sparkle AIOX.

Conteúdo:
  - MRR total e por cliente
  - Tasks executadas nos últimos 7 dias (por tipo e status)
  - Notas criadas nos últimos 7 dias
  - Conversas atendidas (mensagens únicas por número)
  - Frase de encerramento gerada pela Friday (claude-haiku)

Acionado manualmente ("me dá o briefing semanal") ou via cron.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from runtime.config import settings
from runtime.db import supabase
from runtime.tasks.handlers.status_mrr import handle_status_mrr
from runtime.utils.llm import call_claude


def handle_weekly_briefing(task: dict) -> dict:
    """
    Monta o relatório semanal e opcionalmente envia via WhatsApp.
    Retorna {"message": "<texto>"}.
    """
    texto = _build_weekly_text(task)

    if settings.mauro_whatsapp:
        try:
            from runtime.integrations.zapi import send_text
            send_text(settings.mauro_whatsapp, texto)
        except Exception as e:
            print(f"[weekly_briefing] failed to send WhatsApp: {e}")

    return {"message": texto}


# ── Builder ────────────────────────────────────────────────────────────────────

def _build_weekly_text(task: dict) -> str:
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("America/Sao_Paulo")
    now_brt = datetime.now(tz)
    cutoff_utc = datetime.now(timezone.utc) - timedelta(days=7)
    cutoff_iso = cutoff_utc.isoformat()

    lines: list[str] = [
        f"*Briefing Semanal Sparkle AIOX* — {now_brt.strftime('%d/%m/%Y')}",
        "",
    ]

    # ── 1. MRR ──────────────────────────────────────────────
    try:
        mrr_result = handle_status_mrr({})
        total_mrr = mrr_result.get("total_mrr", 0)
        clients = mrr_result.get("clients", [])
        mrr_fmt = f"R$ {total_mrr:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        lines.append(f"*MRR Total:* {mrr_fmt}/mês ({len(clients)} clientes)")
        for c in clients:
            name = c.get("name") or c.get("client_name") or "—"
            mrr = c.get("mrr", 0)
            mrr_c = f"R$ {mrr:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            lines.append(f"  • {name}: {mrr_c}")
        lines.append("")
    except Exception as e:
        lines.append(f"*MRR:* erro ao buscar ({e})")
        lines.append("")

    # ── 2. Tasks dos últimos 7 dias ──────────────────────────
    try:
        res = (
            supabase.table("runtime_tasks")
            .select("task_type,status")
            .gte("created_at", cutoff_iso)
            .execute()
        )
        tasks_data = res.data or []
        total_tasks = len(tasks_data)

        # Agrupa por tipo
        by_type: dict[str, int] = {}
        for t in tasks_data:
            tt = t.get("task_type", "unknown")
            by_type[tt] = by_type.get(tt, 0) + 1

        # Conta por status
        done_count = sum(1 for t in tasks_data if t.get("status") == "done")
        failed_count = sum(1 for t in tasks_data if t.get("status") == "failed")

        lines.append(f"*Tasks (7 dias):* {total_tasks} total — {done_count} concluídas, {failed_count} com erro")
        for tt, count in sorted(by_type.items(), key=lambda x: -x[1]):
            lines.append(f"  • {tt}: {count}")
        lines.append("")
    except Exception as e:
        lines.append(f"*Tasks:* erro ao buscar ({e})")
        lines.append("")

    # ── 3. Notas criadas nos últimos 7 dias ──────────────────
    try:
        res = (
            supabase.table("notes")
            .select("summary,content,created_at")
            .gte("created_at", cutoff_iso)
            .order("created_at", desc=True)
            .execute()
        )
        notes_data = res.data or []
        lines.append(f"*Notas criadas (7 dias):* {len(notes_data)}")
        for note in notes_data[:5]:
            title = note.get("summary") or (note.get("content") or "")[:50]
            lines.append(f"  • {title}")
        lines.append("")
    except Exception as e:
        lines.append(f"*Notas:* erro ao buscar ({e})")
        lines.append("")

    # ── 4. Conversas atendidas ───────────────────────────────
    try:
        res = (
            supabase.table("conversation_history")
            .select("phone")
            .gte("created_at", cutoff_iso)
            .eq("role", "user")
            .execute()
        )
        msgs_data = res.data or []
        phones_unicos = len({r["phone"] for r in msgs_data})
        lines.append(
            f"*Conversas (7 dias):* {len(msgs_data)} mensagens de {phones_unicos} número(s)"
        )
        lines.append("")
    except Exception as e:
        lines.append(f"*Conversas:* erro ao buscar ({e})")
        lines.append("")

    # ── 5. Frase de encerramento gerada pela Friday ──────────
    try:
        task_id = task.get("id")
        closing = call_claude(
            prompt=(
                "Você é Friday, assistente da Sparkle AIOX. "
                "Escreva UMA frase de encerramento motivadora e direta para o briefing semanal do Mauro. "
                "Máximo 2 linhas. Sem markdown. Em português."
            ),
            model="claude-haiku-4-5-20251001",
            client_id=settings.sparkle_internal_client_id,
            task_id=task_id,
            agent_id="friday",
            purpose="weekly_briefing_closing",
            max_tokens=80,
        )
        lines.append(closing.strip())
        lines.append("")
    except Exception as e:
        lines.append("_Sparkle AIOX Runtime — briefing semanal automático_")
        lines.append("")

    return "\n".join(lines)
