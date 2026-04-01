"""
Handler para relatório diário automático.
Enviado às 8h todo dia para MAURO_WHATSAPP.

Conteúdo: resumo do dia anterior — tasks executadas, conversas, notas criadas, MRR.
Acionado automaticamente pelo ARQ cron job em worker.py (11h UTC = 8h Brasília).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from runtime.config import settings
from runtime.db import supabase
from runtime.tasks.handlers.status_mrr import handle_status_mrr


async def handle_daily_briefing(task: dict) -> dict:
    """
    Monta e envia o relatório diário às 8h de Brasília.
    Retorna {"message": "<texto enviado>"} para o result da task.
    """
    texto = await _build_briefing_text()

    # Envia via WhatsApp se o número estiver configurado
    if settings.mauro_whatsapp:
        try:
            from runtime.integrations.zapi import send_text
            await asyncio.to_thread(send_text, settings.mauro_whatsapp, texto)
        except Exception as e:
            print(f"[daily_briefing] failed to send WhatsApp: {e}")

    return {"message": texto}


async def _build_briefing_text() -> str:
    """Constrói o texto amigável do relatório diário."""
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("America/Sao_Paulo")
    now_brt = datetime.now(tz)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    cutoff_iso = cutoff.isoformat()

    lines = [
        f"*Bom dia, Mauro!* ☀️ Relatório de {now_brt.strftime('%d/%m/%Y')}",
        "",
    ]

    # --- 1. Tasks executadas nas últimas 24h por tipo ---
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks")
            .select("task_type")
            .gte("completed_at", cutoff_iso)
            .eq("status", "done")
            .execute()
        )
        tasks_data = res.data or []
        task_counts: dict[str, int] = {}
        for t in tasks_data:
            tt = t.get("task_type", "unknown")
            task_counts[tt] = task_counts.get(tt, 0) + 1

        total_tasks = sum(task_counts.values())
        lines.append(f"*Tasks executadas (24h):* {total_tasks}")
        for tt, count in sorted(task_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  • {tt}: {count}")
        lines.append("")
    except Exception as e:
        lines.append(f"*Tasks:* erro ao buscar ({e})")
        lines.append("")

    # --- 2. Mensagens recebidas (conversation_history) nas últimas 24h ---
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("conversation_history")
            .select("phone")
            .gte("created_at", cutoff_iso)
            .eq("role", "user")
            .execute()
        )
        msgs_data = res.data or []
        phones_unicos = len({r["phone"] for r in msgs_data})
        lines.append(f"*Conversas (24h):* {len(msgs_data)} mensagens de {phones_unicos} número(s)")
        lines.append("")
    except Exception as e:
        lines.append(f"*Conversas:* erro ao buscar ({e})")
        lines.append("")

    # --- 3. Notas criadas nas últimas 24h ---
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("notes")
            .select("summary,content")
            .gte("created_at", cutoff_iso)
            .execute()
        )
        notes_data = res.data or []
        lines.append(f"*Notas criadas (24h):* {len(notes_data)}")
        for note in notes_data[:5]:  # mostra até 5
            title = note.get("summary") or note.get("content", "")[:40]
            lines.append(f"  • {title}")
        lines.append("")
    except Exception as e:
        lines.append(f"*Notas:* erro ao buscar ({e})")
        lines.append("")

    # --- 4. MRR atual ---
    try:
        mrr_result = await handle_status_mrr({})
        total_mrr = mrr_result.get("total_mrr", 0)
        n_clients = len(mrr_result.get("clients", []))
        mrr_formatted = f"R$ {total_mrr:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        lines.append(f"*MRR atual:* {mrr_formatted}/mês ({n_clients} clientes)")
        lines.append("")
    except Exception as e:
        lines.append(f"*MRR:* erro ao buscar ({e})")
        lines.append("")

    lines.append("_Sparkle AIOX Runtime — relatório automático_")

    return "\n".join(lines)
