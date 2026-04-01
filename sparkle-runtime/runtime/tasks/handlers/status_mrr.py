"""
Status MRR handler — retorna o MRR atual da Sparkle AIOX.

Tenta buscar dados reais do Supabase (tabelas `clients` / `services`).
Se não encontrar dados suficientes, usa fallback hardcoded baseado nos clientes conhecidos.
"""
from __future__ import annotations

from runtime.db import supabase

# Fallback hardcoded — atualizar conforme novos clientes forem adicionados
_HARDCODED_CLIENTS = [
    {"name": "Vitalis Life (João Lúcio)", "service": "Tráfego Pago Google+Meta", "mrr": 1500.00},
    {"name": "Alexsandro Confeitaria",    "service": "Zenya WhatsApp",           "mrr": 500.00},
    {"name": "Ensinaja (Douglas)",         "service": "Zenya Escola",             "mrr": 650.00},
    {"name": "Plaka (Luiza/Roberta)",      "service": "Zenya SAC",                "mrr": 297.00},
    {"name": "Fun Personalize (Julia)",    "service": "Zenya Premium",            "mrr": 897.00},
    {"name": "Gabriela",                   "service": "Meta Ads Consórcio",       "mrr": 750.00},
]
_HARDCODED_MRR = sum(c["mrr"] for c in _HARDCODED_CLIENTS)


async def handle_status_mrr(task: dict) -> dict:
    """
    Retorna o MRR atual. Tenta Supabase primeiro; cai no fallback se necessário.
    """
    clients, source = _fetch_from_supabase()

    if not clients:
        clients = _HARDCODED_CLIENTS
        source = "hardcoded"

    total_mrr = sum(c.get("mrr", 0) for c in clients)

    lines = [f"*MRR Sparkle AIOX* — R$ {total_mrr:,.2f}/mês".replace(",", ".")]
    lines.append(f"({len(clients)} clientes ativos)\n")

    for c in clients:
        name = c.get("name") or c.get("client_name") or "—"
        service = c.get("service") or c.get("service_name") or "—"
        mrr = c.get("mrr", 0)
        lines.append(f"• {name} — {service}: R$ {mrr:,.2f}".replace(",", "."))

    if source == "hardcoded":
        lines.append("\n_(dados de referência — atualize via portal)_")

    message = "\n".join(lines)
    return {
        "message": message,
        "total_mrr": total_mrr,
        "clients": clients,
        "source": source,
    }


def _fetch_from_supabase() -> tuple[list[dict], str]:
    """
    Tenta buscar clientes e serviços do Supabase.
    Retorna (lista, fonte) ou ([], "") se falhar.
    """
    try:
        # Tenta tabela `clients` com coluna `mrr`
        res = supabase.table("clients").select("*").eq("status", "active").execute()
        if res.data:
            return res.data, "supabase_clients"
    except Exception:
        pass

    try:
        # Tenta tabela `services`
        res = supabase.table("services").select("*").eq("active", True).execute()
        if res.data:
            return res.data, "supabase_services"
    except Exception:
        pass

    return [], ""
