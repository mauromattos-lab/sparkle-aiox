"""
Handler: client_report / client_reports_bulk

Generates a monthly performance report per client and delivers it via
WhatsApp (Z-API) when the client has a whatsapp number on file.

Metrics aggregated per client (for the PREVIOUS calendar month):
  - Zenya conversations + messages (zenya_conversations.client_id, started_at filter)
  - Escalation rate, sentiment distribution, outcome distribution
  - Brain chunks count (brain_chunks.client_id)
  - MRR value from clients table
  - Tenure (days since client was created)

Templates:
  1. Zenya client WITH conversation data → full metrics
  2. Zenya client WITHOUT conversation data → "system active, metrics being collected"
  3. Trafego-only client (has_trafego=True, has_zenya=False) → service confirmation

Design spec: docs/stories/sprint-core/sub-5-relatorio-mensal.md
"""
from __future__ import annotations

import asyncio
from calendar import monthrange
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from runtime.db import supabase

_TZ = ZoneInfo("America/Sao_Paulo")

_MONTH_NAMES_PT = [
    "Janeiro", "Fevereiro", "Marco", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


# ── Period helpers ───────────────────────────────────────────


def _previous_month_range() -> tuple[datetime, datetime, str]:
    """
    Return (start_dt, end_dt, label) for the previous calendar month.
    start_dt is inclusive (first day 00:00 BRT → UTC).
    end_dt is exclusive (first day of current month 00:00 BRT → UTC).
    label is e.g. "Marco 2026".
    """
    now_brt = datetime.now(_TZ)
    year, month = now_brt.year, now_brt.month

    # Previous month
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1

    start = datetime(prev_year, prev_month, 1, tzinfo=_TZ)
    # end = first day of current month (exclusive upper bound)
    end = datetime(year, month, 1, tzinfo=_TZ)

    label = f"{_MONTH_NAMES_PT[prev_month - 1]} {prev_year}"
    return start, end, label


# ── Formatters ────────────────────────────────────────────────


def _fmt_brl(value: float) -> str:
    """Format float as Brazilian currency: 1500.00 -> '1.500,00'."""
    s = f"{value:,.2f}"  # "1,500.00"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


# ── DB fetchers ───────────────────────────────────────────────


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


async def _count_zenya_conversations_period(
    client_id: str, start: datetime, end: datetime
) -> dict:
    """
    Aggregate conversation metrics for the given period.

    Returns a dict with:
      conversations, messages, escalations,
      sentiment_positive, sentiment_neutral, sentiment_negative,
      outcome_converted, outcome_attended, outcome_escalated
    """
    zero = {
        "conversations": 0,
        "messages": 0,
        "escalations": 0,
        "sentiment_positive": 0,
        "sentiment_neutral": 0,
        "sentiment_negative": 0,
        "outcome_converted": 0,
        "outcome_attended": 0,
        "outcome_escalated": 0,
    }
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("zenya_conversations")
            .select(
                "id,message_count,escalated_to_human,sentiment,outcome"
            )
            .eq("client_id", client_id)
            .gte("started_at", start.isoformat())
            .lt("started_at", end.isoformat())
            .execute()
        )
        rows = res.data or []
        if not rows:
            return zero

        result = dict(zero)
        result["conversations"] = len(rows)
        result["messages"] = sum(r.get("message_count") or 0 for r in rows)

        for r in rows:
            if r.get("escalated_to_human"):
                result["escalations"] += 1

            sentiment = (r.get("sentiment") or "").lower()
            if sentiment == "positive":
                result["sentiment_positive"] += 1
            elif sentiment == "negative":
                result["sentiment_negative"] += 1
            else:
                result["sentiment_neutral"] += 1

            outcome = (r.get("outcome") or "").lower()
            if outcome in ("converted", "conversao", "conversion"):
                result["outcome_converted"] += 1
            elif outcome in ("escalated", "escalado"):
                result["outcome_escalated"] += 1
            else:
                result["outcome_attended"] += 1

        return result
    except Exception as e:
        print(f"[client_report] zenya_conversations period error for {client_id}: {e}")
        return zero


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


# ── Text builders ─────────────────────────────────────────────


def _build_zenya_with_data(
    client: dict,
    metrics: dict,
    chunks: int,
    tenure_days: int,
    period_label: str,
) -> str:
    """
    Template 1 — Zenya client with real conversation data.
    Matches design spec Case 1 in the story.
    """
    name = client.get("name") or client.get("company") or "Cliente"
    mrr = float(client.get("mrr") or 0)

    convos = metrics["conversations"]
    messages = metrics["messages"]
    escalations = metrics["escalations"]
    resolved = convos - escalations

    # Resolution rate
    if convos > 0:
        resolution_pct = round((resolved / convos) * 100)
    else:
        resolution_pct = 0

    lines = [
        f"Relatorio Zenya — {name}",
        f"Referencia: {period_label}",
        "",
    ]

    # Core metric sentence
    lines.append(
        f"Este mes, sua Zenya fez {convos} atendimento{'s' if convos != 1 else ''} "
        f"e trocou {messages} {'mensagens' if messages != 1 else 'mensagem'} "
        f"com seus clientes, sem precisar te chamar em "
        f"{resolved} deles (taxa de resolucao: {resolution_pct}%)."
    )
    lines.append("")

    # Outcomes
    converted = metrics["outcome_converted"]
    escalated = metrics["outcome_escalated"]
    if converted > 0:
        lines.append(
            f"Dos atendimentos, {converted} terminaram em conversao ou interesse direto "
            f"no produto."
        )
    if escalated > 0:
        lines.append(
            f"{escalated} precisaram de atencao humana (escalamentos)."
        )
    if converted > 0 or escalated > 0:
        lines.append("")

    # Sentiment
    pos = metrics["sentiment_positive"]
    neu = metrics["sentiment_neutral"]
    neg = metrics["sentiment_negative"]
    if pos + neu + neg > 0:
        lines.append(
            f"O sentimento geral dos seus clientes foi positivo: "
            f"{pos} atendimentos positivos, {neu} neutros, {neg} negativos."
        )
        lines.append("")

    # Knowledge base + tenure
    if chunks > 0:
        lines.append(f"Base de conhecimento: {chunks} itens sobre seu negocio.")
    lines.append(f"Voce esta conosco ha {tenure_days} dias.")
    lines.append("")

    lines.append(f"Investimento este mes: R${_fmt_brl(mrr)}")
    lines.append("")
    lines.append("Tem duvidas ou quer ajustar algo? Me chama aqui.")
    lines.append("")
    lines.append("— Sparkle AIOX")

    return "\n".join(lines)


def _build_zenya_no_data(
    client: dict,
    chunks: int,
    tenure_days: int,
    period_label: str,
) -> str:
    """
    Template 2 — Zenya client with no conversation data yet.
    Honest about the early stage. Matches design spec Case 2.
    """
    name = client.get("name") or client.get("company") or "Cliente"
    mrr = float(client.get("mrr") or 0)

    lines = [
        f"Relatorio Zenya — {name}",
        f"Referencia: {period_label}",
        "",
        "Sua Zenya esta configurada e ativa. Estamos no inicio da operacao "
        "e as metricas de atendimento estao sendo coletadas.",
        "",
    ]

    if chunks > 0:
        lines.append(f"Base de conhecimento: {chunks} itens sobre seu negocio.")
    lines.append(f"Voce esta conosco ha {tenure_days} dias.")
    lines.append("")
    lines.append(f"Investimento este mes: R${_fmt_brl(mrr)}")
    lines.append("")
    lines.append("Qualquer duvida ou ajuste, e so me chamar aqui.")
    lines.append("")
    lines.append("— Sparkle AIOX")

    return "\n".join(lines)


def _build_trafego_report(
    client: dict,
    tenure_days: int,
    period_label: str,
) -> str:
    """
    Template 3 — Trafego pago client (no Zenya).
    Matches design spec Case 3.
    """
    name = client.get("name") or client.get("company") or "Cliente"
    mrr = float(client.get("mrr") or 0)

    lines = [
        f"Relatorio de Servico — {name}",
        f"Referencia: {period_label}",
        "",
        "Servico de gestao de trafego pago ativo neste mes.",
        "Contas gerenciadas: Meta Ads + Google Ads.",
        "",
        f"Voce esta conosco ha {tenure_days} dias.",
        f"Investimento este mes: R${_fmt_brl(mrr)}",
        "",
        "Para ver resultados das campanhas, solicite o relatorio "
        "de performance de anuncios.",
        "",
        "— Sparkle AIOX",
    ]

    return "\n".join(lines)


def _build_report_text(
    client: dict,
    metrics: dict,
    chunks: int,
    tenure_days: int,
    period_label: str,
) -> str:
    """
    Route to the correct template based on client type and available data.
    - has_zenya + data    → Template 1
    - has_zenya + no data → Template 2
    - trafego only        → Template 3
    """
    has_zenya = bool(client.get("has_zenya"))
    has_trafego = bool(client.get("has_trafego"))

    if has_zenya:
        if metrics["conversations"] > 0:
            return _build_zenya_with_data(client, metrics, chunks, tenure_days, period_label)
        else:
            return _build_zenya_no_data(client, chunks, tenure_days, period_label)
    elif has_trafego:
        return _build_trafego_report(client, tenure_days, period_label)
    else:
        # Fallback: treat as Zenya without data
        return _build_zenya_no_data(client, chunks, tenure_days, period_label)


# ── Persistence ───────────────────────────────────────────────


async def _save_result_to_task(task: dict, report_text: str, send_ok: bool) -> None:
    """
    Persist the generated report text in runtime_tasks.result before sending.
    Only updates if the task has an 'id' field (i.e. was dispatched via task queue).
    """
    task_id = task.get("id")
    if not task_id:
        return
    try:
        payload = {
            "result": {
                "report_text": report_text,
                "send_attempted": True,
                "send_ok": send_ok,
            },
            "status": "done",
        }
        await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks")
            .update(payload)
            .eq("id", task_id)
            .execute()
        )
    except Exception as e:
        print(f"[client_report] save_result_to_task error for task {task_id}: {e}")


# ── Aggregate & build ─────────────────────────────────────────


async def _aggregate_and_build(client: dict) -> dict:
    """
    Aggregate all metrics for a single client and build the report dict.
    Returns {client_id, name, whatsapp, report_text, metrics, has_data}.
    """
    client_id = client["id"]
    start, end, period_label = _previous_month_range()

    # Parallel metric fetch
    conv_metrics, chunks = await asyncio.gather(
        _count_zenya_conversations_period(client_id, start, end),
        _count_brain_chunks(client_id),
    )

    # Tenure
    created_raw = client.get("created_at") or ""
    try:
        created_dt = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
        tenure_days = (datetime.now(timezone.utc) - created_dt).days
    except Exception:
        tenure_days = 0

    report_text = _build_report_text(
        client=client,
        metrics=conv_metrics,
        chunks=chunks,
        tenure_days=tenure_days,
        period_label=period_label,
    )

    return {
        "client_id": client_id,
        "name": client.get("name") or client.get("company"),
        "whatsapp": client.get("whatsapp"),
        "report_text": report_text,
        "has_data": conv_metrics["conversations"] > 0,
        "metrics": {
            "period": period_label,
            "conversations": conv_metrics["conversations"],
            "messages": conv_metrics["messages"],
            "escalations": conv_metrics["escalations"],
            "sentiment_positive": conv_metrics["sentiment_positive"],
            "sentiment_neutral": conv_metrics["sentiment_neutral"],
            "sentiment_negative": conv_metrics["sentiment_negative"],
            "outcome_converted": conv_metrics["outcome_converted"],
            "outcome_attended": conv_metrics["outcome_attended"],
            "outcome_escalated": conv_metrics["outcome_escalated"],
            "brain_chunks": chunks,
            "tenure_days": tenure_days,
            "mrr": float(client.get("mrr") or 0),
        },
    }


# ── Z-API sender ─────────────────────────────────────────────


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
    Generate (and optionally send) a monthly report for a single client.

    Payload:
        client_id (str)  — required
        send (bool)      — default True; set False for preview/dry-run

    AC-6: report_text is saved to runtime_tasks.result BEFORE sending.
    AC-5: clients without whatsapp get report saved but not sent; no_whatsapp=True in result.
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
    no_whatsapp = False
    send_failed = False

    if do_send:
        if report["whatsapp"]:
            # AC-6: persist before sending
            await _save_result_to_task(task, report["report_text"], send_ok=False)
            sent = await _send_report(report["whatsapp"], report["report_text"])
            if sent:
                print(
                    f"[client_report] relatorio enviado para {report['name']} "
                    f"({report['whatsapp']})"
                )
            else:
                send_failed = True
                print(
                    f"[client_report] falha ao enviar para {report['name']} "
                    f"({report['whatsapp']}) — relatorio salvo em task.result"
                )
            # Update with final send status
            await _save_result_to_task(task, report["report_text"], send_ok=sent)
        else:
            # AC-5: no whatsapp — save report, log clearly, do NOT send
            no_whatsapp = True
            await _save_result_to_task(task, report["report_text"], send_ok=False)
            print(
                f"[client_report] {report['name']} sem whatsapp — "
                f"relatorio salvo em task.result para envio manual"
            )

    return {
        "message": report["report_text"],
        "sent": sent,
        "no_whatsapp": no_whatsapp,
        "send_failed": send_failed,
        "client_id": client_id,
        "client_name": report["name"],
        "whatsapp": report["whatsapp"],
        "has_data": report["has_data"],
        "metrics": report["metrics"],
    }


async def handle_client_reports_bulk(task: dict) -> dict:
    """
    Generate and send monthly reports for ALL active clients.

    Payload:
        send (bool) — default True; set False for dry-run / preview

    AC-9: bug fix — 'sent' field now reflects actual send outcome per client.
    AC-5: no_whatsapp counter added to response.
    """
    payload = task.get("payload") or {}
    do_send = payload.get("send", True)

    clients = await _fetch_active_clients()
    if not clients:
        return {"message": "Nenhum cliente ativo encontrado", "sent": 0, "total": 0}

    # Aggregate all in parallel
    aggregated = await asyncio.gather(
        *[_aggregate_and_build(c) for c in clients],
        return_exceptions=True,
    )

    sent_count = 0
    no_whatsapp_count = 0
    skipped_count = 0  # dry-run
    failed_count = 0
    results = []

    for report in aggregated:
        if isinstance(report, Exception):
            print(f"[client_reports_bulk] aggregate error: {report}")
            failed_count += 1
            continue

        item_sent = False
        item_no_whatsapp = False
        item_send_failed = False

        if do_send:
            if report["whatsapp"]:
                ok = await _send_report(report["whatsapp"], report["report_text"])
                if ok:
                    sent_count += 1
                    item_sent = True
                else:
                    failed_count += 1
                    item_send_failed = True
            else:
                # AC-5: track no_whatsapp separately
                no_whatsapp_count += 1
                item_no_whatsapp = True
                print(
                    f"[client_reports_bulk] {report['name']} sem whatsapp — "
                    f"relatorio gerado mas nao enviado"
                )
        else:
            skipped_count += 1

        # AC-9: 'sent' reflects actual result, not membership check
        results.append({
            "client_id": report["client_id"],
            "name": report["name"],
            "whatsapp": report["whatsapp"],
            "sent": item_sent,
            "no_whatsapp": item_no_whatsapp,
            "send_failed": item_send_failed,
            "has_data": report["has_data"],
            "metrics": report["metrics"],
            # Include report text for audit/preview
            "report_text": report["report_text"],
        })

    summary = (
        f"Relatorios mensais: {sent_count} enviados, "
        f"{no_whatsapp_count} sem whatsapp, "
        f"{skipped_count} modo preview, "
        f"{failed_count} erros — "
        f"{len(clients)} clientes processados"
    )
    print(f"[client_reports_bulk] {summary}")

    return {
        "message": summary,
        "total": len(clients),
        "sent": sent_count,
        "no_whatsapp": no_whatsapp_count,
        "skipped": skipped_count,
        "failed": failed_count,
        "results": results,
    }
