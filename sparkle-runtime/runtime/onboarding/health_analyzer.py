"""
ONB-1.9: Health analyzer para monitoramento pos-go-live.

Coleta metricas de saude da Zenya nos primeiros 30 dias apos o go-live:
- Volume de conversas (ultimas 48h e semanal)
- Taxa de escalacao (se dados disponiveis)
- Sentiment analysis via Claude Haiku (ultimas 20 mensagens do usuario)

REGRAS:
- Fallback graceful: se tabelas nao existem, nao crasha — log warning
- Sentiment analysis max 1x/dia por cliente (idempotencia)
- Isola por client_id: nunca cruza dados entre clientes
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from runtime.db import supabase
from runtime.utils.llm import call_claude

# ── Limiares de alerta ────────────────────────────────────────

THRESHOLD_VOLUME_ZERO_HOURS = 48        # 0 conversas em 48h → warning
THRESHOLD_ESCALATION_PCT = 30.0         # > 30% escalacao → warning
THRESHOLD_NEGATIVE_SENTIMENT_PCT = 40.0 # > 40% negativo → warning
THRESHOLD_VOLUME_DROP_PCT = 50.0        # > 50% queda semanal → warning
CRITICAL_MIN_WARNINGS = 2              # 2+ warnings → critical

# ── Prompt sentiment ─────────────────────────────────────────

_SENTIMENT_SYSTEM = """Voce e um analisador de sentiment de mensagens de clientes.
Classifique cada mensagem como POSITIVO, NEUTRO ou NEGATIVO.

Criterios:
- POSITIVO: elogio, satisfacao, agradecimento, mensagem amigavel
- NEGATIVO: reclamacao, frustracao, critica, confusao, insatisfacao
- NEUTRO: pergunta simples, informacao neutra, cumprimento

Retorne APENAS JSON valido:
{"positivo": N, "neutro": N, "negativo": N, "total": N}

Onde N e o numero de mensagens em cada categoria."""


async def _fetch_conversations_zenya(client_id: str, since: datetime) -> list[dict]:
    """Tenta buscar conversas de zenya_conversations (fonte primaria)."""
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("zenya_conversations")
            .select("id,role,content,escalated,created_at")
            .eq("client_id", client_id)
            .gte("created_at", since.isoformat())
            .order("created_at", desc=True)
            .limit(500)
            .execute()
        )
        return result.data or []
    except Exception as e:
        err = str(e).lower()
        if "does not exist" in err or "relation" in err or "42p01" in err:
            return []  # Tabela nao existe — fallback gracioso
        raise


async def _fetch_conversations_brain(client_id: str, since: datetime) -> list[dict]:
    """Fallback: busca de brain_raw_ingestions com source_type=whatsapp."""
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("brain_raw_ingestions")
            .select("id,content,source_type,created_at")
            .eq("client_id", client_id)
            .eq("source_type", "whatsapp")
            .gte("created_at", since.isoformat())
            .order("created_at", desc=True)
            .limit(500)
            .execute()
        )
        return result.data or []
    except Exception as e:
        err = str(e).lower()
        if "does not exist" in err or "relation" in err or "42p01" in err:
            return []
        raise


async def _fetch_user_messages(client_id: str, limit: int = 20) -> list[str]:
    """
    Busca as ultimas N mensagens do usuario (role=user) para sentiment analysis.
    Tenta zenya_conversations primeiro, fallback para conversation_history.
    """
    messages: list[str] = []

    # Tenta zenya_conversations
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("zenya_conversations")
            .select("content,role")
            .eq("client_id", client_id)
            .eq("role", "user")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        rows = result.data or []
        messages = [r["content"] for r in rows if r.get("content")]
        if messages:
            return messages
    except Exception as e:
        err = str(e).lower()
        if "does not exist" not in err and "relation" not in err and "42p01" not in err:
            raise

    # Fallback: conversation_history
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("conversation_history")
            .select("content,role")
            .eq("client_id", client_id)
            .eq("role", "user")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        rows = result.data or []
        messages = [r["content"] for r in rows if r.get("content")]
    except Exception as e:
        err = str(e).lower()
        if "does not exist" not in err and "relation" not in err and "42p01" not in err:
            raise

    return messages


async def analyze_sentiment(
    messages: list[str],
    client_id: str,
    task_id: Optional[str] = None,
) -> dict:
    """
    AC-2.1: Analisa sentiment das mensagens via Claude Haiku.

    Retorna:
    {
        "positivo": N, "neutro": N, "negativo": N, "total": N,
        "negativo_pct": float,  # percentual negativo
        "analyzed_at": iso_str
    }
    """
    if not messages:
        return {
            "positivo": 0, "neutro": 0, "negativo": 0, "total": 0,
            "negativo_pct": 0.0,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "source": "no_messages",
        }

    # Limita e formata
    sample = messages[:20]
    numbered = "\n".join(f"{i+1}. {m}" for i, m in enumerate(sample))
    prompt = f"Analise as seguintes mensagens de clientes:\n\n{numbered}"

    try:
        raw = await call_claude(
            prompt,
            system=_SENTIMENT_SYSTEM,
            model="claude-haiku-4-5-20251001",
            client_id=client_id,
            task_id=task_id,
            agent_id="health-analyzer",
            purpose="post_golive_sentiment",
            max_tokens=256,
        )

        # Parse JSON da resposta
        data = json.loads(raw.strip())
        total = max(data.get("total", 1), 1)
        negativo = data.get("negativo", 0)
        negativo_pct = round((negativo / total) * 100, 1)

        return {
            "positivo": data.get("positivo", 0),
            "neutro": data.get("neutro", 0),
            "negativo": negativo,
            "total": total,
            "negativo_pct": negativo_pct,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "source": "haiku_analysis",
        }
    except json.JSONDecodeError as e:
        print(f"[health_analyzer] sentiment JSON parse error for {client_id}: {e} — raw: {raw[:200]}")
        # Fallback seguro: retorna neutral
        total = len(sample)
        return {
            "positivo": total, "neutro": 0, "negativo": 0, "total": total,
            "negativo_pct": 0.0,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "source": "parse_error_fallback",
        }
    except Exception as e:
        print(f"[health_analyzer] sentiment analysis error for {client_id}: {e}")
        raise


async def collect_health_metrics(
    client_id: str,
    task_id: Optional[str] = None,
    existing_gate_details: Optional[dict] = None,
) -> dict:
    """
    AC-1.3: Coleta metricas de saude da Zenya para um cliente.

    Retorna:
    {
        "volume_48h": int,
        "volume_7d": int,
        "volume_prev_7d": int,        # semana anterior para comparacao
        "escalation_count": int | None,
        "escalation_total": int | None,
        "escalation_pct": float | None,  # None = dados indisponiveis
        "sentiment": { ... },         # resultado de analyze_sentiment
        "data_source": "zenya_conversations" | "brain_raw_ingestions" | "unavailable",
        "collected_at": iso_str,
    }
    """
    now = datetime.now(timezone.utc)
    since_48h = now - timedelta(hours=48)
    since_7d = now - timedelta(days=7)
    since_14d = now - timedelta(days=14)

    data_source = "unavailable"
    volume_48h = 0
    volume_7d = 0
    volume_prev_7d = 0
    escalation_count: Optional[int] = None
    escalation_total: Optional[int] = None

    # ── Tenta zenya_conversations ─────────────────────────────
    convs_7d = await _fetch_conversations_zenya(client_id, since_7d)

    if convs_7d:
        data_source = "zenya_conversations"
        convs_48h = [c for c in convs_7d if c.get("created_at", "") >= since_48h.isoformat()]
        volume_48h = len(convs_48h)
        volume_7d = len(convs_7d)

        # Busca semana anterior para calcular queda
        try:
            prev_result = await asyncio.to_thread(
                lambda: supabase.table("zenya_conversations")
                .select("id")
                .eq("client_id", client_id)
                .gte("created_at", since_14d.isoformat())
                .lt("created_at", since_7d.isoformat())
                .execute()
            )
            volume_prev_7d = len(prev_result.data or [])
        except Exception:
            volume_prev_7d = 0

        # Calcula taxa de escalacao se campo disponivel
        escalation_rows = [c for c in convs_7d if c.get("escalated") is True]
        if convs_7d:
            escalation_count = len(escalation_rows)
            escalation_total = len(convs_7d)
    else:
        # ── Fallback: brain_raw_ingestions ────────────────────
        brain_7d = await _fetch_conversations_brain(client_id, since_7d)

        if brain_7d:
            data_source = "brain_raw_ingestions"
            brain_48h = [b for b in brain_7d if b.get("created_at", "") >= since_48h.isoformat()]
            volume_48h = len(brain_48h)
            volume_7d = len(brain_7d)

            # Busca semana anterior
            try:
                prev_result = await asyncio.to_thread(
                    lambda: supabase.table("brain_raw_ingestions")
                    .select("id")
                    .eq("client_id", client_id)
                    .eq("source_type", "whatsapp")
                    .gte("created_at", since_14d.isoformat())
                    .lt("created_at", since_7d.isoformat())
                    .execute()
                )
                volume_prev_7d = len(prev_result.data or [])
            except Exception:
                volume_prev_7d = 0
            # Escalacao indisponivel nesta fonte
        # else: data_source permanece "unavailable"

    # ── Sentiment analysis (max 1x/dia — idempotencia via gate_details) ─────
    gate = existing_gate_details or {}
    health_metrics_existing = gate.get("health_metrics", {})
    last_sentiment_at_str = health_metrics_existing.get("last_sentiment_at")

    should_run_sentiment = True
    if last_sentiment_at_str:
        try:
            last_dt = datetime.fromisoformat(last_sentiment_at_str)
            if (now - last_dt).total_seconds() < 86400:  # menos de 24h
                should_run_sentiment = False
                print(f"[health_analyzer] {client_id}: sentiment ja analisado hoje — skip")
        except Exception:
            pass

    if should_run_sentiment and data_source != "unavailable":
        user_messages = await _fetch_user_messages(client_id, limit=20)
        sentiment = await analyze_sentiment(user_messages, client_id, task_id)
    elif data_source == "unavailable":
        sentiment = {
            "positivo": 0, "neutro": 0, "negativo": 0, "total": 0,
            "negativo_pct": 0.0,
            "analyzed_at": now.isoformat(),
            "source": "data_unavailable",
        }
    else:
        # Reaproveitamos o sentiment existente
        sentiment = health_metrics_existing.get("sentiment", {
            "positivo": 0, "neutro": 0, "negativo": 0, "total": 0,
            "negativo_pct": 0.0,
            "source": "reused_from_cache",
        })

    escalation_pct: Optional[float] = None
    if escalation_count is not None and escalation_total and escalation_total > 0:
        escalation_pct = round((escalation_count / escalation_total) * 100, 1)

    return {
        "volume_48h": volume_48h,
        "volume_7d": volume_7d,
        "volume_prev_7d": volume_prev_7d,
        "escalation_count": escalation_count,
        "escalation_total": escalation_total,
        "escalation_pct": escalation_pct,
        "sentiment": sentiment,
        "data_source": data_source,
        "collected_at": now.isoformat(),
    }


def evaluate_health(metrics: dict) -> dict:
    """
    AC-3.x: Aplica limiares e retorna status + lista de alertas.

    Retorna:
    {
        "status": "healthy" | "warning" | "critical",
        "alerts": [
            {"type": "volume_zero", "severity": "warning", "message": "..."},
            ...
        ],
        "warning_count": int,
    }
    """
    alerts: list[dict] = []

    volume_48h = metrics.get("volume_48h", 0)
    escalation_pct = metrics.get("escalation_pct")
    sentiment = metrics.get("sentiment", {})
    volume_7d = metrics.get("volume_7d", 0)
    volume_prev_7d = metrics.get("volume_prev_7d", 0)
    data_source = metrics.get("data_source", "unavailable")

    # AC-6.2: Sem dados
    if data_source == "unavailable":
        alerts.append({
            "type": "no_data",
            "severity": "warning",
            "message": "Sem dados de conversas disponiveis para health check. Verificar configuracao.",
        })

    # AC-3.1: Volume zero em 48h
    if data_source != "unavailable" and volume_48h == 0:
        alerts.append({
            "type": "volume_zero",
            "severity": "warning",
            "message": f"Nenhuma conversa com a Zenya nas ultimas 48h. Verificar se WhatsApp esta funcionando.",
        })

    # AC-3.2: Escalacao excessiva
    if escalation_pct is not None and escalation_pct > THRESHOLD_ESCALATION_PCT:
        alerts.append({
            "type": "high_escalation",
            "severity": "warning",
            "message": f"{escalation_pct:.0f}% das conversas estao sendo escaladas para humano. Zenya pode estar com lacuna de conhecimento.",
        })

    # AC-3.3: Sentiment negativo
    negativo_pct = sentiment.get("negativo_pct", 0.0)
    if negativo_pct > THRESHOLD_NEGATIVE_SENTIMENT_PCT:
        alerts.append({
            "type": "negative_sentiment",
            "severity": "warning",
            "message": f"{negativo_pct:.0f}% das mensagens recentes tem sentiment negativo. Revisar respostas da Zenya.",
        })

    # AC-3.4: Queda de volume semanal
    if volume_prev_7d > 0 and volume_7d < volume_prev_7d:
        drop_pct = round(((volume_prev_7d - volume_7d) / volume_prev_7d) * 100, 1)
        if drop_pct > THRESHOLD_VOLUME_DROP_PCT:
            alerts.append({
                "type": "volume_drop",
                "severity": "warning",
                "message": f"Volume de conversas caiu {drop_pct:.0f}% essa semana vs semana passada. Possivel risco de churn.",
            })

    # AC-3.5: Severidade
    warning_count = len(alerts)
    if warning_count >= CRITICAL_MIN_WARNINGS:
        status = "critical"
        for a in alerts:
            a["severity"] = "critical"
    elif warning_count == 1:
        status = "warning"
    else:
        status = "healthy"

    return {
        "status": status,
        "alerts": alerts,
        "warning_count": warning_count,
    }
