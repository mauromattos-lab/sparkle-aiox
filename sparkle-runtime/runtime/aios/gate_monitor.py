"""
Gate Monitor — AIOS-E-02.

Detecta gates do pipeline AIOS marcados como 'skipped' nas últimas 24h
e notifica Mauro via Friday (WhatsApp).

Padrão de notificação: mesmo padrão de content/pipeline.py —
importa zapi e settings inline, usa mauro_whatsapp como destino.

Registro no scheduler via register_aios_jobs() — mesmo padrão de
register_content_jobs() em runtime/crons/content.py.
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from runtime.cron_logger import log_cron
from runtime.db import supabase

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)


async def check_skipped_gates() -> None:
    """Detecta gates pulados nas últimas 24h e notifica Friday."""
    from datetime import datetime, timezone, timedelta

    threshold = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("story_gates")
            .select("story_id, gate, agent, completed_at")
            .eq("status", "skipped")
            .gte("completed_at", threshold)
            .execute()
        )
    except Exception as exc:
        logger.error(f"[gate_monitor] DB query failed: {exc}")
        return

    if not result.data:
        logger.info("[gate_monitor] Nenhum gate pulado nas últimas 24h")
        return

    lines = ["\u26a0\ufe0f Gates AIOS pulados nas últimas 24h:"]
    for row in result.data:
        lines.append(
            f"\u2022 {row['story_id']} \u2192 gate '{row['gate']}' pulado por {row['agent']}"
        )

    message = "\n".join(lines)

    try:
        from runtime.config import settings
        from runtime.integrations import zapi

        phone = settings.mauro_whatsapp
        if not phone:
            logger.warning("[gate_monitor] MAURO_WHATSAPP not configured -- skip notify")
            return

        await asyncio.to_thread(lambda: zapi.send_text(phone, message))
        logger.info(f"[gate_monitor] Friday notificada: {len(result.data)} gate(s) pulado(s)")
    except Exception as exc:
        logger.error(f"[gate_monitor] Falha ao notificar Friday (non-blocking): {exc}")


# ── Wrapper decorado para o scheduler ──────────────────────────

@log_cron("aios_gate_monitor")
async def _run_aios_gate_monitor() -> None:
    await check_skipped_gates()


def register_aios_jobs(scheduler: "AsyncIOScheduler") -> None:
    """
    Registra jobs AIOS no APScheduler.
    Chamado em start_scheduler() em runtime/scheduler.py.
    """
    from zoneinfo import ZoneInfo
    from apscheduler.triggers.cron import CronTrigger

    _TZ = ZoneInfo("America/Sao_Paulo")

    scheduler.add_job(
        _run_aios_gate_monitor,
        trigger=CronTrigger(hour=9, minute=0, timezone=_TZ),
        id="aios_gate_monitor",
        replace_existing=True,
    )
