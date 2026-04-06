"""
Health Score Engine — LIFECYCLE-1.2

Calcula e persiste o Health Score de cada cliente Zenya com base em 5 sinais:

  Sinal         Peso   Fonte de dados
  volume        30%    zenya_events (msgs últimos 7d vs média 4 semanas)
  payment       25%    subscriptions.status (Asaas via billing)
  access        20%    zenya_events (último evento do owner)
  support       15%    placeholder — score 80 até integração Chatwoot
  checkin       10%    placeholder — média dos outros sinais

  Classificação:
    80-100 -> healthy
    60-79  -> attention
    40-59  -> risk
    0-39   -> critical

Funções públicas:
  async calculate_health_score(client_id: str) -> dict
  async calculate_all_health_scores() -> list[dict]
  async get_health_score(client_id: str) -> dict | None
  async get_health_history(client_id: str, limit: int = 20, offset: int = 0) -> list[dict]
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from runtime.db import supabase

logger = logging.getLogger(__name__)

# ── Classification ────────────────────────────────────────


def classify(score: int) -> str:
    """Classifica o score em categoria de saúde."""
    if score >= 80:
        return "healthy"
    elif score >= 60:
        return "attention"
    elif score >= 40:
        return "risk"
    else:
        return "critical"


# ── Signal: Volume (30%) ──────────────────────────────────


async def _signal_volume(client_id: str) -> dict:
    """
    Compara volume de mensagens dos últimos 7 dias contra a média das 4 semanas anteriores.
    Score 100 se volume >= média, caindo proporcionalmente até 0.
    """
    now = datetime.now(timezone.utc)
    seven_days_ago = (now - timedelta(days=7)).isoformat()
    five_weeks_ago = (now - timedelta(days=35)).isoformat()

    try:
        res_recent = await asyncio.to_thread(
            lambda: supabase.table("zenya_events")
            .select("id", count="exact")
            .eq("client_id", client_id)
            .gte("created_at", seven_days_ago)
            .execute()
        )
        recent_count = res_recent.count or 0

        res_prev = await asyncio.to_thread(
            lambda: supabase.table("zenya_events")
            .select("id", count="exact")
            .eq("client_id", client_id)
            .gte("created_at", five_weeks_ago)
            .lt("created_at", seven_days_ago)
            .execute()
        )
        prev_count = res_prev.count or 0

        weekly_avg = prev_count / 4 if prev_count > 0 else 0

        if weekly_avg == 0:
            score = 70 if recent_count > 0 else 50
        else:
            ratio = recent_count / weekly_avg
            score = min(100, int(ratio * 100))

        return {
            "score": score,
            "recent_count": recent_count,
            "weekly_avg": round(weekly_avg, 1),
        }
    except Exception as e:
        logger.warning("[health/volume] client=%s error=%s", client_id, e)
        return {"score": 50, "recent_count": 0, "weekly_avg": 0, "error": str(e)}


# ── Signal: Payment (25%) ─────────────────────────────────


async def _signal_payment(client_id: str) -> dict:
    """
    Verifica status da assinatura Asaas.
    ACTIVE -> 100, OVERDUE -> 20, INACTIVE/ausente -> 50 (default neutro).
    """
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("subscriptions")
            .select("status, next_due_date")
            .eq("client_id", client_id)
            .maybe_single()
            .execute()
        )

        # maybe_single() returns None (not an object) when no row is found
        row = res.data if res is not None and hasattr(res, "data") else res
        if not row:
            return {"score": 50, "status": "no_subscription"}

        status = (row.get("status") or "").upper()

        if status == "ACTIVE":
            score = 100
        elif status in ("OVERDUE", "LATE"):
            score = 20
        elif status in ("INACTIVE", "CANCELLED", "DELETED"):
            score = 0
        else:
            score = 50

        return {"score": score, "status": status, "next_due_date": row.get("next_due_date")}
    except Exception as e:
        logger.warning("[health/payment] client=%s error=%s", client_id, e)
        return {"score": 50, "status": "error", "error": str(e)}


# ── Signal: Access (20%) ──────────────────────────────────


async def _signal_access(client_id: str) -> dict:
    """
    Verifica quando foi o último evento do cliente em zenya_events.
    < 3 dias -> 100, < 7 dias -> 80, < 14 dias -> 60, < 30 dias -> 40, >= 30 dias -> 20.
    """
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("zenya_events")
            .select("created_at")
            .eq("client_id", client_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        if not res.data:
            return {"score": 20, "last_event_at": None, "days_since_last": None}

        last_event_at = res.data[0]["created_at"]
        if isinstance(last_event_at, str):
            last_dt = datetime.fromisoformat(last_event_at.replace("Z", "+00:00"))
        else:
            last_dt = last_event_at

        days_since = (datetime.now(timezone.utc) - last_dt).days

        if days_since < 3:
            score = 100
        elif days_since < 7:
            score = 80
        elif days_since < 14:
            score = 60
        elif days_since < 30:
            score = 40
        else:
            score = 20

        return {"score": score, "last_event_at": last_event_at, "days_since_last": days_since}
    except Exception as e:
        logger.warning("[health/access] client=%s error=%s", client_id, e)
        return {"score": 50, "last_event_at": None, "days_since_last": None, "error": str(e)}


# ── Signal: Support (15%) — placeholder ───────────────────


async def _signal_support(client_id: str) -> dict:
    """
    Placeholder — retorna score 80 até integração Chatwoot/suporte.
    Arquitetura correta: verificar tickets abertos/urgentes por client_id.
    """
    return {"score": 80, "open_tickets": 0, "source": "placeholder"}


# ── Signal: Checkin (10%) — placeholder ───────────────────


async def _signal_checkin(other_signals: dict) -> dict:
    """
    Placeholder — usa média dos outros 4 sinais como proxy de check-in.
    Arquitetura: last_checkin_response_at + score de qualidade da resposta.
    """
    scores = [s.get("score", 80) for s in other_signals.values() if isinstance(s.get("score"), int)]
    avg = int(sum(scores) / len(scores)) if scores else 80
    return {"score": avg, "source": "derived_from_others"}


# ── Composite Score ───────────────────────────────────────

_WEIGHTS = {
    "volume": 0.30,
    "payment": 0.25,
    "access": 0.20,
    "support": 0.15,
    "checkin": 0.10,
}


def _compute_weighted_score(signals: dict) -> int:
    """Calcula score ponderado a partir dos sinais."""
    total = 0.0
    for key, weight in _WEIGHTS.items():
        signal_score = signals.get(key, {}).get("score", 50)
        total += signal_score * weight
    return max(0, min(100, int(round(total))))


# ── Public API ────────────────────────────────────────────


async def calculate_health_score(client_id: str) -> dict:
    """
    Calcula o Health Score de um cliente e persiste no Supabase.

    Args:
        client_id: UUID do cliente (zenya_clients.id)

    Returns:
        dict com score, classification, signals, calculated_at
    """
    client_res = await asyncio.to_thread(
        lambda: supabase.table("zenya_clients")
        .select("id, business_name, active")
        .eq("id", client_id)
        .maybe_single()
        .execute()
    )
    # maybe_single() returns None directly when no row is found
    client_row = client_res.data if client_res is not None and hasattr(client_res, "data") else client_res
    if not client_row:
        raise ValueError(f"Client {client_id} not found in zenya_clients")

    client_name = client_row.get("business_name", "unknown")

    volume_task = asyncio.create_task(_signal_volume(client_id))
    payment_task = asyncio.create_task(_signal_payment(client_id))
    access_task = asyncio.create_task(_signal_access(client_id))
    support_task = asyncio.create_task(_signal_support(client_id))

    volume, payment, access, support = await asyncio.gather(
        volume_task, payment_task, access_task, support_task
    )

    checkin = await _signal_checkin({"volume": volume, "payment": payment, "access": access, "support": support})

    signals = {
        "volume": volume,
        "payment": payment,
        "access": access,
        "support": support,
        "checkin": checkin,
    }

    score = _compute_weighted_score(signals)
    classification = classify(score)
    calculated_at = datetime.now(timezone.utc).isoformat()

    row = {
        "client_id": client_id,
        "score": score,
        "classification": classification,
        "signals": signals,
        "alert_sent": False,
        "calculated_at": calculated_at,
    }
    try:
        await asyncio.to_thread(
            lambda: supabase.table("client_health").insert(row).execute()
        )
    except Exception as e:
        logger.error("[health/calculator] failed to persist score for %s: %s", client_id, e)

    logger.info(
        "[health/calculator] client=%s name=%s score=%d classification=%s",
        client_id, client_name, score, classification,
    )

    return {
        "client_id": client_id,
        "client_name": client_name,
        "score": score,
        "classification": classification,
        "signals": signals,
        "calculated_at": calculated_at,
    }


async def calculate_all_health_scores() -> list[dict]:
    """
    Calcula o Health Score de todos os clientes Zenya ativos.

    Returns:
        Lista de dicts com score, classification e signals por cliente.
    """
    clients_res = await asyncio.to_thread(
        lambda: supabase.table("zenya_clients")
        .select("id, business_name, active")
        .eq("active", True)
        .execute()
    )
    clients = clients_res.data or []

    if not clients:
        logger.info("[health/calculator] no active clients found")
        return []

    logger.info("[health/calculator] calculating scores for %d active clients", len(clients))

    results = []
    for client in clients:
        try:
            result = await calculate_health_score(client["id"])
            results.append(result)
        except Exception as e:
            logger.error("[health/calculator] failed for client %s: %s", client.get("id"), e)
            results.append({
                "client_id": client["id"],
                "client_name": client.get("business_name", "unknown"),
                "score": 0,
                "classification": "critical",
                "signals": {},
                "calculated_at": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
            })

    return results


async def get_health_score(client_id: str) -> dict | None:
    """
    Retorna o Health Score mais recente de um cliente do banco.

    Returns:
        dict com score, classification, signals, calculated_at ou None se não encontrado.
    """
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("client_health")
            .select("*")
            .eq("client_id", client_id)
            .order("calculated_at", desc=True)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error("[health/calculator] get_health_score failed for %s: %s", client_id, e)
        return None


async def get_health_history(client_id: str, limit: int = 20, offset: int = 0) -> list[dict]:
    """
    Retorna o histórico de Health Score de um cliente.

    Args:
        client_id: UUID do cliente
        limit: máximo de registros retornados (default 20)
        offset: paginação

    Returns:
        Lista de dicts ordenados por calculated_at DESC.
    """
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("client_health")
            .select("id, score, classification, signals, alert_sent, calculated_at")
            .eq("client_id", client_id)
            .order("calculated_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        return res.data or []
    except Exception as e:
        logger.error("[health/calculator] get_health_history failed for %s: %s", client_id, e)
        return []
