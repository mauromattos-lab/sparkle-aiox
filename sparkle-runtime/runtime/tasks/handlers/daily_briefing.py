"""
Handler para relatório diário automático.
Enviado às 8h todo dia para MAURO_WHATSAPP.

Conteúdo: resumo do dia anterior — tasks executadas, conversas, notas criadas, MRR,
Brain stats, content pipeline, gaps pendentes, workflow status, system health.
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

    # --- 5. Brain stats (24h) — chunks e insights novos ---
    try:
        chunk_res = await asyncio.to_thread(
            lambda: supabase.table("brain_chunks")
            .select("id", count="exact")
            .gte("created_at", cutoff_iso)
            .execute()
        )
        new_chunks = chunk_res.count if chunk_res.count is not None else len(chunk_res.data or [])

        insight_res = await asyncio.to_thread(
            lambda: supabase.table("brain_insights")
            .select("id", count="exact")
            .gte("created_at", cutoff_iso)
            .execute()
        )
        new_insights = insight_res.count if insight_res.count is not None else len(insight_res.data or [])

        lines.append(f"*Brain (24h):* {new_chunks} chunks, {new_insights} insights novos")
        lines.append("")
    except Exception as e:
        lines.append(f"*Brain:* erro ao buscar ({e})")
        lines.append("")

    # --- 6. Content pipeline — drafts aguardando e agendados para hoje ---
    try:
        draft_res = await asyncio.to_thread(
            lambda: supabase.table("generated_content")
            .select("id", count="exact")
            .eq("status", "draft")
            .execute()
        )
        draft_count = draft_res.count if draft_res.count is not None else len(draft_res.data or [])

        today_str = now_brt.strftime("%Y-%m-%d")
        scheduled_res = await asyncio.to_thread(
            lambda: supabase.table("generated_content")
            .select("id", count="exact")
            .eq("status", "scheduled")
            .gte("scheduled_at", f"{today_str}T00:00:00")
            .lt("scheduled_at", f"{today_str}T23:59:59")
            .execute()
        )
        scheduled_count = scheduled_res.count if scheduled_res.count is not None else len(scheduled_res.data or [])

        lines.append(f"*Conteúdo:* {draft_count} drafts aguardando, {scheduled_count} agendados hoje")
        lines.append("")
    except Exception as e:
        lines.append(f"*Conteúdo:* erro ao buscar ({e})")
        lines.append("")

    # --- 7. Gaps pendentes do Observer ---
    try:
        gap_res = await asyncio.to_thread(
            lambda: supabase.table("gap_reports")
            .select("id", count="exact")
            .eq("status", "pending")
            .execute()
        )
        gap_count = gap_res.count if gap_res.count is not None else len(gap_res.data or [])
        if gap_count > 0:
            lines.append(f"*Gaps pendentes:* {gap_count} aguardando aprovação")
            lines.append("")
    except Exception:
        pass  # Non-critical, skip silently

    # --- 8. Active workflow status ---
    try:
        wf_res = await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks")
            .select("task_type, status")
            .in_("status", ["pending", "running"])
            .execute()
        )
        active_tasks = wf_res.data or []
        if active_tasks:
            pending = sum(1 for t in active_tasks if t.get("status") == "pending")
            running = sum(1 for t in active_tasks if t.get("status") == "running")
            lines.append(f"*Workflows ativos:* {running} rodando, {pending} na fila")
            lines.append("")
    except Exception:
        pass  # Non-critical

    # --- 9. System health summary ---
    try:
        failed_res = await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks")
            .select("id", count="exact")
            .eq("status", "failed")
            .gte("completed_at", cutoff_iso)
            .execute()
        )
        failed_count = failed_res.count if failed_res.count is not None else len(failed_res.data or [])
        if failed_count == 0:
            lines.append("*Sistema:* tudo ok, zero falhas em 24h ✅")
        elif failed_count <= 3:
            lines.append(f"*Sistema:* {failed_count} falha(s) em 24h — normal")
        else:
            lines.append(f"*Sistema:* ⚠️ {failed_count} falhas em 24h — verificar logs")
        lines.append("")
    except Exception:
        pass

    lines.append("_Sparkle AIOX Runtime — relatório automático_")

    return "\n".join(lines)
