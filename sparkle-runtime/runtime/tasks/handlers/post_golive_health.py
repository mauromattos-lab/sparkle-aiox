"""
ONB-1.9: Handler de health check pos-go-live.

Verifica saude da Zenya para todos os clientes em fase post_go_live.

Responsabilidades:
1. Busca clientes com onboarding em fase post_go_live / in_progress
2. Para cada cliente: coleta metricas, avalia limiares, alerta Friday se necessario
3. Dia 7 apos go-live: gera relatorio de 1a semana
4. Dia 30 apos go-live: marca onboarding como completed (ou alerta para decidir)

Idempotencia:
- Sentiment max 1x/dia (verificado em health_analyzer via last_sentiment_at)
- Relatorio semanal enviado 1x (gate_details.weekly_report_sent)
- Completion marcada 1x (gate_passed = true ja marca saida do monitoramento)

REGRAS:
- NAO modifica dados de clientes reais em producao (testing_mode != 'off' sao pulados)
- NAO envia mensagens WhatsApp diretamente ao cliente — apenas alerta Friday
- Fallback graceful em todas as consultas
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

from runtime.db import supabase
from runtime.config import settings


# ── Constantes ─────────────────────────────────────────────────

PHASE = "post_go_live"
WEEKLY_REPORT_DAY = 7    # dias apos go-live
COMPLETION_DAY = 30      # dias para marcar completed
CRITICAL_LOOKBACK_DAYS = 7  # janela para verificar incidentes criticos no completion


# ── Helpers ────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _alert_friday(message: str) -> None:
    """Alerta Friday (Mauro) via WhatsApp."""
    mauro_phone = settings.mauro_whatsapp
    if not mauro_phone:
        print(f"[post_golive_health] WARN: MAURO_WHATSAPP nao configurado — alerta nao enviado: {message[:100]}")
        return
    try:
        from runtime.integrations.zapi import send_text
        await asyncio.to_thread(send_text, mauro_phone, f"[Friday] {message}")
    except Exception as e:
        print(f"[post_golive_health] WARN: falha ao alertar Friday: {e}")


async def _log_onboarding_event(
    client_id: str,
    event_type: str,
    phase: str,
    payload: dict,
) -> None:
    """Registra evento no onboarding_events (auditoria)."""
    try:
        await asyncio.to_thread(
            lambda: supabase.table("onboarding_events").insert({
                "client_id": client_id,
                "event_type": event_type,
                "phase": phase,
                "payload": payload,
            }).execute()
        )
    except Exception as e:
        print(f"[post_golive_health] WARN: falha ao registrar evento {event_type}: {e}")


async def _update_gate_details(workflow_id: str, health_metrics: dict) -> None:
    """Atualiza gate_details com health_metrics no onboarding_workflows."""
    try:
        # Busca gate_details atual para merge (nao sobrescrever outros campos)
        current_res = await asyncio.to_thread(
            lambda: supabase.table("onboarding_workflows")
            .select("gate_details")
            .eq("id", workflow_id)
            .single()
            .execute()
        )
        current_gate = (current_res.data or {}).get("gate_details") or {}
        current_gate["health_metrics"] = health_metrics
        current_gate["health_metrics"]["last_check_at"] = _now().isoformat()

        await asyncio.to_thread(
            lambda: supabase.table("onboarding_workflows")
            .update({"gate_details": current_gate})
            .eq("id", workflow_id)
            .execute()
        )
    except Exception as e:
        print(f"[post_golive_health] WARN: falha ao atualizar gate_details para {workflow_id}: {e}")


async def _mark_completed(client_id: str) -> None:
    """
    AC-5.2: Marca todas as fases do onboarding como completed.
    Registra evento onboarding_completed.
    """
    try:
        await asyncio.to_thread(
            lambda: supabase.table("onboarding_workflows")
            .update({"status": "completed"})
            .eq("client_id", client_id)
            .execute()
        )
    except Exception as e:
        print(f"[post_golive_health] WARN: falha ao marcar onboarding completed para {client_id}: {e}")
        return

    # Tenta marcar onboarding_sessions se existir
    try:
        await asyncio.to_thread(
            lambda: supabase.table("onboarding_sessions")
            .update({"status": "completed"})
            .eq("client_id", client_id)
            .execute()
        )
    except Exception as e:
        err = str(e).lower()
        if "does not exist" not in err and "relation" not in err and "42p01" not in err:
            print(f"[post_golive_health] WARN: falha ao atualizar onboarding_sessions: {e}")

    await _log_onboarding_event(
        client_id=client_id,
        event_type="onboarding_completed",
        phase=PHASE,
        payload={"completed_at": _now().isoformat(), "reason": "30_days_no_critical_incidents"},
    )


async def _get_critical_incidents_count(client_id: str, since: datetime) -> int:
    """
    Conta quantos alertas criticos ocorreram desde `since` para este cliente.
    Consulta onboarding_events com event_type=health_alert e severity=critical.
    """
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("onboarding_events")
            .select("id")
            .eq("client_id", client_id)
            .eq("event_type", "health_alert")
            .gte("created_at", since.isoformat())
            .execute()
        )
        rows = result.data or []
        # Filtra criticos pelo payload
        critical_count = 0
        for row in rows:
            payload = row.get("payload") or {}
            if isinstance(payload, dict) and payload.get("severity") == "critical":
                critical_count += 1
        return critical_count
    except Exception as e:
        print(f"[post_golive_health] WARN: falha ao contar incidentes criticos: {e}")
        return 0


async def _get_client_name(client_id: str) -> str:
    """Busca nome do cliente. Retorna 'Cliente' como fallback."""
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("clients")
            .select("name")
            .eq("id", client_id)
            .single()
            .execute()
        )
        return (result.data or {}).get("name", "Cliente")
    except Exception:
        return "Cliente"


async def _process_client(workflow: dict) -> dict:
    """
    Processa health check para um cliente em post_go_live.

    Retorna:
    {
        "client_id": str,
        "alerts_sent": int,
        "completed": bool,
        "status": "healthy" | "warning" | "critical",
    }
    """
    from runtime.onboarding.health_analyzer import collect_health_metrics, evaluate_health
    from runtime.onboarding.report_generator import generate_weekly_report, format_alert_message

    client_id = workflow.get("client_id", "")
    workflow_id = workflow.get("id", "")
    gate_details = workflow.get("gate_details") or {}

    if not client_id:
        print("[post_golive_health] WARN: workflow sem client_id — skip")
        return {"client_id": "", "alerts_sent": 0, "completed": False, "status": "unknown"}

    print(f"[post_golive_health] Processando cliente {client_id}")

    # ── Determina go_live_at ─────────────────────────────────
    go_live_at_str = gate_details.get("go_live_at") or workflow.get("completed_at")
    go_live_at: Optional[datetime] = None
    if go_live_at_str:
        try:
            go_live_at = datetime.fromisoformat(go_live_at_str)
            if go_live_at.tzinfo is None:
                go_live_at = go_live_at.replace(tzinfo=timezone.utc)
        except Exception:
            pass

    if go_live_at is None:
        # Usa updated_at como proxy do inicio da fase
        try:
            go_live_at = datetime.fromisoformat(
                workflow.get("updated_at") or workflow.get("created_at") or _now().isoformat()
            )
            if go_live_at.tzinfo is None:
                go_live_at = go_live_at.replace(tzinfo=timezone.utc)
        except Exception:
            go_live_at = _now()

    now = _now()
    days_elapsed = (now - go_live_at).days
    client_name = await _get_client_name(client_id)

    # ── Coleta metricas ───────────────────────────────────────
    try:
        metrics = await collect_health_metrics(
            client_id=client_id,
            existing_gate_details=gate_details,
        )
    except Exception as e:
        print(f"[post_golive_health] ERRO ao coletar metricas para {client_id}: {e}")
        return {"client_id": client_id, "alerts_sent": 0, "completed": False, "status": "error"}

    # ── Avalia saude ──────────────────────────────────────────
    health = evaluate_health(metrics)
    status = health.get("status", "healthy")
    alerts = health.get("alerts", [])

    # ── Salva metricas no gate_details (AC-2.2) ───────────────
    health_metrics_payload = {
        **metrics,
        "health_status": status,
        "alerts": alerts,
        "last_sentiment_at": metrics.get("sentiment", {}).get("analyzed_at"),
    }
    await _update_gate_details(workflow_id, health_metrics_payload)

    alerts_sent = 0

    # ── Envia alertas Friday (AC-3.x) ─────────────────────────
    if alerts:
        for alert in alerts:
            msg = format_alert_message(client_name, alert)
            await _alert_friday(msg)
            alerts_sent += 1

        # Registra no onboarding_events
        await _log_onboarding_event(
            client_id=client_id,
            event_type="health_alert",
            phase=PHASE,
            payload={
                "severity": status,
                "alerts": alerts,
                "metrics_summary": {
                    "volume_48h": metrics.get("volume_48h"),
                    "escalation_pct": metrics.get("escalation_pct"),
                    "negativo_pct": metrics.get("sentiment", {}).get("negativo_pct"),
                    "data_source": metrics.get("data_source"),
                },
            },
        )

    # ── Relatorio 1a semana (AC-4.x) — apenas no dia 7 ─────────
    weekly_report_sent = gate_details.get("weekly_report_sent", False)
    if days_elapsed >= WEEKLY_REPORT_DAY and not weekly_report_sent:
        report_text = generate_weekly_report(client_name, metrics, health)
        await _alert_friday(report_text)

        # Marca relatorio como enviado no gate_details
        gate_details["weekly_report_sent"] = True
        gate_details["weekly_report_sent_at"] = now.isoformat()

        try:
            await asyncio.to_thread(
                lambda: supabase.table("onboarding_workflows")
                .update({"gate_details": gate_details})
                .eq("id", workflow_id)
                .execute()
            )
        except Exception as e:
            print(f"[post_golive_health] WARN: falha ao marcar weekly_report_sent: {e}")

        # Salva no onboarding_events (AC-4.3)
        await _log_onboarding_event(
            client_id=client_id,
            event_type="weekly_health_report",
            phase=PHASE,
            payload={
                "report_text": report_text,
                "days_elapsed": days_elapsed,
                "health_status": status,
                "metrics": {
                    "volume_7d": metrics.get("volume_7d"),
                    "avg_per_day": round(metrics.get("volume_7d", 0) / 7, 1),
                    "escalation_pct": metrics.get("escalation_pct"),
                    "negativo_pct": metrics.get("sentiment", {}).get("negativo_pct"),
                },
            },
        )

        print(f"[post_golive_health] Relatorio 1a semana enviado para {client_name}")

    # ── Verificacao de completion (AC-5.x) — apenas apos 30 dias ──
    completed = False
    if days_elapsed >= COMPLETION_DAY:
        # Verifica se gate_passed ja esta marcado (idempotencia)
        if not workflow.get("gate_passed"):
            lookback = now - timedelta(days=CRITICAL_LOOKBACK_DAYS)
            critical_count = await _get_critical_incidents_count(client_id, lookback)

            if critical_count == 0:
                # AC-5.2: Sem incidentes criticos — marca completed
                await _mark_completed(client_id)
                await _alert_friday(
                    f"{client_name} completou 30 dias pos-go-live sem incidentes criticos. "
                    f"Onboarding concluido! Cliente em operacao normal."
                )
                completed = True
                print(f"[post_golive_health] {client_name}: onboarding COMPLETED apos 30 dias")
            else:
                # AC-5.4: Houve incidentes — alerta Mauro para decidir
                await _alert_friday(
                    f"ATENCAO: {client_name} atingiu 30 dias pos-go-live MAS teve "
                    f"{critical_count} incidente(s) critico(s) nos ultimos {CRITICAL_LOOKBACK_DAYS} dias. "
                    f"Decida: encerrar onboarding ou estender monitoramento?"
                )
                print(f"[post_golive_health] {client_name}: 30 dias atingidos com {critical_count} incidente(s) critico(s)")

    return {
        "client_id": client_id,
        "client_name": client_name,
        "alerts_sent": alerts_sent,
        "completed": completed,
        "status": status,
        "days_elapsed": days_elapsed,
    }


# ── Handler principal ─────────────────────────────────────────

async def handle_post_golive_health(task: dict) -> dict:
    """
    ONB-1.9: Verifica saude de todos os clientes em fase post_go_live.

    Busca todos os workflows em fase=post_go_live, status=in_progress,
    gate_passed=false e executa health check para cada um.

    Retorna:
    {
        "status": "ok",
        "checked": N,
        "alerts_sent": N,
        "completed": N,
        "results": [...],
    }
    """
    print("[post_golive_health] Iniciando health check pos-go-live")

    # ── Busca clientes em monitoramento ──────────────────────
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("onboarding_workflows")
            .select("id,client_id,status,phase,gate_passed,gate_details,updated_at,created_at,completed_at")
            .eq("phase", PHASE)
            .eq("status", "in_progress")
            .eq("gate_passed", False)
            .execute()
        )
        workflows = result.data or []
    except Exception as e:
        print(f"[post_golive_health] ERRO ao buscar workflows: {e}")
        return {"status": "error", "error": str(e), "checked": 0, "alerts_sent": 0, "completed": 0}

    if not workflows:
        print("[post_golive_health] Nenhum cliente em post_go_live/in_progress — nada a verificar")
        return {"status": "ok", "checked": 0, "alerts_sent": 0, "completed": 0, "results": []}

    print(f"[post_golive_health] {len(workflows)} cliente(s) em monitoramento")

    # ── Processa cada cliente ─────────────────────────────────
    results = []
    total_alerts = 0
    total_completed = 0

    for workflow in workflows:
        try:
            client_result = await _process_client(workflow)
            results.append(client_result)
            total_alerts += client_result.get("alerts_sent", 0)
            if client_result.get("completed"):
                total_completed += 1
        except Exception as e:
            client_id = workflow.get("client_id", "unknown")
            print(f"[post_golive_health] ERRO ao processar cliente {client_id}: {e}")
            results.append({
                "client_id": client_id,
                "alerts_sent": 0,
                "completed": False,
                "status": "error",
                "error": str(e),
            })

    print(
        f"[post_golive_health] Concluido — "
        f"checked={len(workflows)}, alerts={total_alerts}, completed={total_completed}"
    )

    return {
        "status": "ok",
        "task_id": task.get("id"),
        "checked": len(workflows),
        "alerts_sent": total_alerts,
        "completed": total_completed,
        "results": results,
    }
