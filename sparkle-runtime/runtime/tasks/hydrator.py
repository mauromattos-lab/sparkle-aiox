"""
Context Hydrator — enriquece o payload da task antes da execução.
O agente recebe um snapshot completo e não precisa fazer queries adicionais.

Fase entre classify_and_dispatch() e execute_task():
  raw task → hydrate_context() → enriched task → handler executa
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

_TZ_BRASILIA = ZoneInfo("America/Sao_Paulo")


def hydrate_context(task: dict) -> dict:
    """
    Enriquece o payload da task com contexto relevante.
    Retorna task com payload atualizado — não modifica o Supabase.
    """
    task_type = task.get("task_type", "")
    payload = task.get("payload", {})
    from_number = payload.get("from_number", "")

    enriched = dict(task)          # cópia rasa do task
    enriched_payload = dict(payload)  # cópia rasa do payload

    # 1. Para qualquer task: injetar datetime atual de Brasília
    enriched_payload["current_datetime"] = _get_brasilia_datetime()

    # 2. Para tasks de chat/conversa: injetar histórico recente
    if task_type in ("chat", "task_free") and from_number:
        enriched_payload["conversation_history"] = _get_recent_history(from_number, limit=5)

    # 3. Para tasks de status/briefing: injetar snapshot de clientes
    if task_type in ("status_report", "status_mrr", "weekly_briefing", "daily_briefing"):
        enriched_payload["clients_snapshot"] = _get_clients_snapshot()

    enriched["payload"] = enriched_payload
    return enriched


# ── Private helpers ────────────────────────────────────────────────────────────

def _get_brasilia_datetime() -> str:
    """Retorna data e hora atual no fuso de Brasília (ISO 8601)."""
    now = datetime.now(_TZ_BRASILIA)
    dias_semana = {
        0: "segunda-feira", 1: "terça-feira", 2: "quarta-feira",
        3: "quinta-feira",  4: "sexta-feira",  5: "sábado",  6: "domingo",
    }
    meses = {
        1: "janeiro",  2: "fevereiro", 3: "março",     4: "abril",
        5: "maio",     6: "junho",     7: "julho",      8: "agosto",
        9: "setembro", 10: "outubro",  11: "novembro",  12: "dezembro",
    }
    dia_semana = dias_semana[now.weekday()]
    mes = meses[now.month]
    return (
        f"{dia_semana}, {now.day:02d} de {mes} de {now.year} "
        f"às {now.hour:02d}:{now.minute:02d} (Brasília)"
    )


def _get_recent_history(from_number: str, limit: int = 5) -> list[dict]:
    """
    Busca as últimas `limit` mensagens do número em conversation_history.
    Retorna lista em ordem cronológica (mais antigas primeiro).
    """
    try:
        from runtime.db import supabase
        res = (
            supabase.table("conversation_history")
            .select("role,content,created_at")
            .eq("phone", from_number)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        # Inverte para ordem cronológica
        return list(reversed(res.data or []))
    except Exception as e:
        print(f"[hydrator] history fetch failed for {from_number}: {e}")
        return []


def _get_clients_snapshot() -> list[dict]:
    """
    Busca snapshot dos clientes ativos do Supabase.
    Fallback para lista hardcoded se a tabela não existir ou estiver vazia.
    """
    try:
        from runtime.db import supabase
        res = supabase.table("clients").select("*").eq("status", "active").execute()
        if res.data:
            return res.data
    except Exception as e:
        print(f"[hydrator] clients snapshot fetch failed: {e}")

    # Fallback hardcoded — espelha status_mrr.py
    return [
        {"name": "Vitalis Life (João Lúcio)", "service": "Tráfego Pago Google+Meta", "mrr": 1500.00},
        {"name": "Alexsandro Confeitaria",    "service": "Zenya WhatsApp",           "mrr": 500.00},
        {"name": "Ensinaja (Douglas)",         "service": "Zenya Escola",             "mrr": 650.00},
        {"name": "Plaka (Luiza/Roberta)",      "service": "Zenya SAC",                "mrr": 297.00},
        {"name": "Fun Personalize (Julia)",    "service": "Zenya Premium",            "mrr": 897.00},
        {"name": "Gabriela",                   "service": "Meta Ads Consórcio",       "mrr": 750.00},
    ]
