"""
Handler: client_report / client_reports_bulk

Generates a monthly performance report per client and delivers it via
WhatsApp (Z-API) when the client has a whatsapp number on file.

Metrics aggregated per client:
  - Zenya conversations (zenya_conversations.client_id)
  - Total messages handled (sum of message_count in zenya_conversations)
  - Brain chunks belonging to that client
  - Runtime tasks completed for that client
  - MRR value from clients table
  - Tenure (days since client was created)
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from runtime.db import supabase

_TZ = ZoneInfo("America/Sao_Paulo")


# ── Helpers ─────────────────────────────────────────────────


def _fmt_brl(value: float) -> str:
    """Format a float as Brazilian currency string, e.g. 1500.00 -> '1.500,00'."""
    # Python's default comma-as-thousands separator then swap
    s = f"{value:,.2f}"           # e.g. "1,500.00"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")  # "1.500,00"
    return s


async def _fetch_client(client_id: str) -> dict | None:
    """Return the clients row for the given id, or None if not found."""
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("clients")
            .select("id,name,company,whatsapp,mrr,status,created_at,has_zenya,has_trafego")
            .eq("id", client_id)
            .single()
            .execute()
        )
        return res.data or None
    except Exception as e:
        print(f"[client_report] fetch_client error for {client_id}: {e}")
        return None


async def _fetch_active_clients() -> list[dict]:
    """Return all active (paying) clients."""
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("clients")
            .select("id,name,company,whatsapp,mrr,status,created_at,has_zenya,has_trafego")
            .eq("status", "active")
            .gt("mrr", 0)
            .order("name")
            .execute()
        )
        return res.data or []
    except Exception as e:
        print(f"[client_report] fetch_active_clients error: {e}")
        return []


async def _count_zenya_conversations(client_id: str) -> tuple[int, int]:
    """
    Return (conversation_count, total_messages) from zenya_conversations.
    total_messages is the sum of message_count across all conversations.
    """
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("zenya_conversations")
            .select("id,message_count")
            .eq("client_id", client_id)
            .execute()
        )
        rows = res.data or []
        convos = len(rows)
        msgs = sum(r.get("message_count") or 0 for r in rows)
        return convos, msgs
    except Exception as e:
        print(f"[client_report] zenya_conversations count error for {client_id}: {e}")
        return 0, 0


async def _count_brain_chunks(client_id: str) -> int:
    """Count brain_chunks rows where client_id matches."""
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("brain_chunks")
            .select("id", count="exact")
            .eq("client_id", client_id)
            .limit(1)
            .execute()
        )
        return res.count if res.count is not None else len(res.data or [])
    except Exception as e:
        print(f"[client_report] brain_chunks count error for {client_id}: {e}")
        return 0


async def _count_runtime_tasks(client_id: str) -> int:
    """Count completed runtime_tasks for the client."""
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks")
            .select("id", count="exact")
            .eq("client_id", client_id)
            .eq("status", "done")
            .limit(1)
            .execute()
        )
        return res.count if res.count is not None else len(res.data or [])
    except Exception as e:
        print(f"[client_report] runtime_tasks count error for {client_id}: {e}")
        return 0


def _build_report_text(
    client: dict,
    convos: int,
    messages: int,
    chunks: int,
    tasks_done: int,
    tenure_days: int,
    period_label: str,
) -> str:
    """
    Assemble the WhatsApp-friendly report text.
    No markdown formatting — WhatsApp does not render it.
    """
    name = client.get("name") or client.get("company") or "Cliente"
    mrr = float(client.get("mrr") or 0)

    lines = [
        f"Relatorio Mensal — {name}",
        f"Periodo: {period_label}",
        "",
        f"Atendimentos Zenya: {convos} conversas ({messages} mensagens)",
        f"Base de conhecimento: {chunks} itens",
        f"Tarefas do sistema: {tasks_done} completadas",
        f"Investimento: R${_fmt_brl(mrr)}/mes",
        f"Cliente ha {tenure_days} dias",
        "",
        "Sua Zenya esta trabalhando 24/7 para voce!",
        "",
        "_Sparkle AIOX — relatorio automatico_",
    ]
    return "\n".join(lines)


async def _aggregate_and_build(client: dict) -> dict:
    """
    Aggregate all metrics for a single client and build the report dict.
    Returns {client_id, name, whatsapp, report_text, metrics}.
    """
    client_id = client["id"]

    # Parallel metric fetch
    (convos, messages), chunks, tasks_done = await asyncio.gather(
        _count_zenya_conversations(client_id),
        _count_brain_chunks(client_id),
        _count_runtime_tasks(client_id),
    )

    # Tenure
    created_raw = client.get("created_at") or ""
    try:
        created_dt = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
        tenure_days = (datetime.now(timezone.utc) - created_dt).days
    except Exception:
        tenure_days = 0

    # Period label: current month/year in Portuguese
    now_brt = datetime.now(_TZ)
    month_names = [
        "janeiro", "fevereiro", "marco", "abril", "maio", "junho",
        "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
    ]
    period_label = f"{month_names[now_brt.month - 1].capitalize()} {now_brt.year}"

    report_text = _build_report_text(
        client=client,
        convos=convos,
        messages=messages,
        chunks=chunks,
        tasks_done=tasks_done,
        tenure_days=tenure_days,
        period_label=period_label,
    )

    return {
        "client_id": client_id,
        "name": client.get("name") or client.get("company"),
        "whatsapp": client.get("whatsapp"),
        "report_text": report_text,
        "metrics": {
            "conversations": convos,
            "messages": messages,
            "brain_chunks": chunks,
            "tasks_done": tasks_done,
            "tenure_days": tenure_days,
            "mrr": float(client.get("mrr") or 0),
        },
    }


async def _send_report(whatsapp: str, report_text: str) -> bool:
    """Send report via Z-API. Returns True on success, False on failure."""
    try:
        from runtime.integrations.zapi import send_text
        await asyncio.to_thread(send_text, whatsapp, report_text)
        return True
    except Exception as e:
        print(f"[client_report] send_report to {whatsapp} failed: {e}")
        return False


# ── Handlers ────────────────────────────────────────────────


async def handle_client_report(task: dict) -> dict:
    """
    Generate and send a monthly report for a single client.

    Payload:
        client_id (str) — required
        send (bool)     — default True; set False for preview-only
    """
    payload = task.get("payload") or {}
    client_id = payload.get("client_id")
    do_send = payload.get("send", True)

    if not client_id:
        return {"error": "client_id obrigatorio no payload"}

    client = await _fetch_client(client_id)
    if not client:
        return {"error": f"cliente {client_id} nao encontrado"}

    report = await _aggregate_and_build(client)
    sent = False

    if do_send and report["whatsapp"]:
        sent = await _send_report(report["whatsapp"], report["report_text"])
        print(f"[client_report] relatorio enviado para {report['name']} ({report['whatsapp']}): {sent}")
    elif do_send and not report["whatsapp"]:
        print(f"[client_report] {report['name']} sem whatsapp — relatorio gerado mas nao enviado")

    return {
        "message": report["report_text"],
        "sent": sent,
        "client_id": client_id,
        "client_name": report["name"],
        "whatsapp": report["whatsapp"],
        "metrics": report["metrics"],
    }


async def handle_client_reports_bulk(task: dict) -> dict:
    """
    Generate and send monthly reports for ALL active clients.

    Payload:
        send (bool) — default True; set False for dry-run / preview
    """
    payload = task.get("payload") or {}
    do_send = payload.get("send", True)

    clients = await _fetch_active_clients()
    if not clients:
        return {"message": "Nenhum cliente ativo encontrado", "sent": 0, "total": 0}

    # Aggregate all in parallel
    reports = await asyncio.gather(
        *[_aggregate_and_build(c) for c in clients],
        return_exceptions=True,
    )

    sent_count = 0
    skipped_count = 0
    failed_count = 0
    results = []

    for report in reports:
        if isinstance(report, Exception):
            print(f"[client_reports_bulk] aggregate error: {report}")
            failed_count += 1
            continue

        if do_send and report["whatsapp"]:
            ok = await _send_report(report["whatsapp"], report["report_text"])
            if ok:
                sent_count += 1
            else:
                failed_count += 1
        else:
            skipped_count += 1

        results.append({
            "client_id": report["client_id"],
            "name": report["name"],
            "whatsapp": report["whatsapp"],
            "sent": do_send and bool(report["whatsapp"]) and report in reports,
            "metrics": report["metrics"],
        })

    summary = (
        f"Relatorios mensais: {sent_count} enviados, "
        f"{skipped_count} sem whatsapp, {failed_count} erros — "
        f"{len(clients)} clientes processados"
    )
    print(f"[client_reports_bulk] {summary}")

    return {
        "message": summary,
        "total": len(clients),
        "sent": sent_count,
        "skipped": skipped_count,
        "failed": failed_count,
        "results": results,
    }
