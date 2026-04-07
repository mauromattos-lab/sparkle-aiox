"""
Loja Integrada — Query de pedidos por CPF, e-mail ou ID do pedido.

Usado pela Zenya da Fun Personalize para consultar status de pedidos
diretamente na Loja Integrada via API REST.

Autenticação: header Authorization com chave de API da loja.
A chave é lida de LOJA_INTEGRADA_API_KEY (variável de ambiente).

API base: https://api.lojaintegrada.com.br
Docs: https://developers.lojaintegrada.com.br/docs/api-reference

Design: stateless — recebe cpf/email/pedido_id, consulta, retorna.
Não persiste nada em Supabase. Apenas consulta a API externa.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import Optional

import httpx

# ── Constantes ─────────────────────────────────────────────

_LI_BASE_URL = "https://api.lojaintegrada.com.br"
_MAX_PEDIDOS = 3  # retornar apenas os últimos N pedidos
_TIMEOUT_SECONDS = 15

# Mapeamento de status da Loja Integrada para texto legível
_STATUS_LABELS: dict[str, str] = {
    "aprovado":            "Aprovado",
    "cancelado":           "Cancelado",
    "em_aberto":           "Em aberto",
    "entregue":            "Entregue",
    "enviado":             "Enviado",
    "nao_autorizado":      "Não autorizado",
    "nao_finalizado":      "Não finalizado",
    "pagamento_em_analise":"Pagamento em análise",
    "recuperado":          "Recuperado",
    "reembolsado":         "Reembolsado",
    "troca_devolvido":     "Troca/Devolvido",
}


# ── Helpers ────────────────────────────────────────────────

def _get_api_key() -> str:
    key = os.environ.get("LOJA_INTEGRADA_API_KEY", "").strip()
    return key


def _format_date(date_str: Optional[str]) -> str:
    """Formata data ISO para DD/MM/YYYY. Retorna string original se falhar."""
    if not date_str:
        return "—"
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return date_str[:10] if len(date_str) >= 10 else date_str


def _format_currency(value) -> str:
    """Formata número como R$ X.XXX,XX."""
    try:
        return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(value)


def _status_label(status: str) -> str:
    return _STATUS_LABELS.get(status.lower(), status)


def _build_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"chave_api {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _format_pedido(pedido: dict) -> str:
    """Formata um pedido em texto legível para WhatsApp."""
    numero = pedido.get("numero") or pedido.get("id") or "—"
    status = _status_label(pedido.get("situacao", {}).get("enum", "") if isinstance(pedido.get("situacao"), dict) else pedido.get("situacao", "—"))
    data = _format_date(pedido.get("data_criacao") or pedido.get("criado_em") or pedido.get("date_time"))
    total = _format_currency(pedido.get("valor_total") or pedido.get("total_com_desconto") or 0)

    # Itens do pedido
    itens = pedido.get("itens", []) or pedido.get("produtos", [])
    linhas_itens = []
    for item in itens[:5]:  # limitar a 5 itens por pedido
        nome = item.get("nome") or item.get("product_name") or item.get("descricao") or "Item"
        qtd = item.get("quantidade") or item.get("quantity") or 1
        linhas_itens.append(f"    • {nome} (x{qtd})")

    itens_str = "\n".join(linhas_itens) if linhas_itens else "    • (sem itens detalhados)"

    return (
        f"*Pedido #{numero}*\n"
        f"  Data: {data}\n"
        f"  Status: {status}\n"
        f"  Total: {total}\n"
        f"  Itens:\n{itens_str}"
    )


# ── Chamadas à API Loja Integrada ──────────────────────────

def _fetch_orders_by_cpf(api_key: str, cpf: str) -> list[dict]:
    """Busca pedidos por CPF do cliente."""
    # Remove formatação (pontos e traço)
    cpf_clean = cpf.replace(".", "").replace("-", "").strip()
    headers = _build_headers(api_key)

    with httpx.Client(timeout=_TIMEOUT_SECONDS) as client:
        # Buscar por CPF do cliente
        r = client.get(
            f"{_LI_BASE_URL}/api/v1/pedido/",
            headers=headers,
            params={"cliente_cpf": cpf_clean, "limit": _MAX_PEDIDOS},
        )
        r.raise_for_status()
        data = r.json()
        return data.get("objects", []) if isinstance(data, dict) else []


def _fetch_orders_by_email(api_key: str, email: str) -> list[dict]:
    """Busca pedidos por e-mail do cliente."""
    headers = _build_headers(api_key)

    with httpx.Client(timeout=_TIMEOUT_SECONDS) as client:
        r = client.get(
            f"{_LI_BASE_URL}/api/v1/pedido/",
            headers=headers,
            params={"cliente_email": email.strip(), "limit": _MAX_PEDIDOS},
        )
        r.raise_for_status()
        data = r.json()
        return data.get("objects", []) if isinstance(data, dict) else []


def _fetch_order_by_id(api_key: str, pedido_id: str) -> Optional[dict]:
    """Busca um pedido específico pelo número/ID."""
    headers = _build_headers(api_key)

    with httpx.Client(timeout=_TIMEOUT_SECONDS) as client:
        r = client.get(
            f"{_LI_BASE_URL}/api/v1/pedido/{pedido_id}/",
            headers=headers,
        )
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()


# ── Handler principal ──────────────────────────────────────

async def handle_loja_integrada_query(task: dict) -> dict:
    """
    Consulta pedidos na Loja Integrada por CPF, e-mail ou ID do pedido.

    Payload esperado (ao menos um identificador):
    {
        "cpf":      "123.456.789-00",   # CPF do cliente
        "email":    "cliente@email.com", # E-mail do cliente
        "pedido_id": "12345",            # Número/ID do pedido
        "client_id": "fun-personalize",  # ID do cliente Sparkle (para contexto)
    }

    Retorna:
    {
        "message": "texto formatado para WhatsApp",
        "pedidos": [...],       # lista de pedidos brutos
        "total_encontrado": N,
        "lookup_type": "cpf"|"email"|"pedido_id"
    }
    """
    payload = task.get("payload", {})

    cpf: str = payload.get("cpf", "").strip()
    email: str = payload.get("email", "").strip()
    pedido_id: str = payload.get("pedido_id", "").strip()

    # Validação: ao menos um identificador
    if not any([cpf, email, pedido_id]):
        return {
            "message": (
                "Para consultar pedidos, preciso de um desses dados:\n"
                "• CPF do cliente\n"
                "• E-mail do cliente\n"
                "• Número do pedido"
            ),
            "pedidos": [],
            "total_encontrado": 0,
            "lookup_type": None,
        }

    # Verificar API key
    api_key = _get_api_key()
    if not api_key:
        return {
            "message": (
                "A integração com a Loja Integrada ainda não está configurada. "
                "Por favor, entre em contato com a equipe para verificar as configurações."
            ),
            "pedidos": [],
            "total_encontrado": 0,
            "lookup_type": None,
            "error": "LOJA_INTEGRADA_API_KEY não configurada",
        }

    pedidos: list[dict] = []
    lookup_type: str = ""
    error_msg: Optional[str] = None

    try:
        if pedido_id:
            lookup_type = "pedido_id"
            pedido = await asyncio.to_thread(_fetch_order_by_id, api_key, pedido_id)
            pedidos = [pedido] if pedido else []

        elif cpf:
            lookup_type = "cpf"
            pedidos = await asyncio.to_thread(_fetch_orders_by_cpf, api_key, cpf)
            # Limitar aos últimos N pedidos (API pode retornar mais)
            pedidos = pedidos[:_MAX_PEDIDOS]

        elif email:
            lookup_type = "email"
            pedidos = await asyncio.to_thread(_fetch_orders_by_email, api_key, email)
            pedidos = pedidos[:_MAX_PEDIDOS]

    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        if status_code == 401:
            error_msg = "Credencial da Loja Integrada inválida ou expirada."
        elif status_code == 403:
            error_msg = "Sem permissão para acessar os pedidos."
        elif status_code == 429:
            error_msg = "Muitas requisições. Tente novamente em instantes."
        else:
            error_msg = f"Erro na API da Loja Integrada (HTTP {status_code})."
        print(f"[loja_integrada] HTTP error: {e}")

    except httpx.TimeoutException:
        error_msg = "A Loja Integrada demorou muito para responder. Tente novamente."
        print("[loja_integrada] Timeout na consulta")

    except Exception as e:
        error_msg = "Ocorreu um erro inesperado ao consultar os pedidos."
        print(f"[loja_integrada] Erro inesperado: {e}")

    # Erro de API
    if error_msg:
        return {
            "message": f"Não consegui consultar os pedidos agora. {error_msg}",
            "pedidos": [],
            "total_encontrado": 0,
            "lookup_type": lookup_type,
            "error": error_msg,
        }

    # Nenhum pedido encontrado
    if not pedidos:
        identificador = pedido_id or cpf or email
        return {
            "message": (
                f"Não encontrei pedidos para esse {'número de pedido' if pedido_id else 'CPF' if cpf else 'e-mail'}. "
                f"Verifique se o dado está correto ou entre em contato com nossa equipe."
            ),
            "pedidos": [],
            "total_encontrado": 0,
            "lookup_type": lookup_type,
        }

    # Formatar resposta
    blocos = [_format_pedido(p) for p in pedidos]
    total = len(pedidos)

    header = (
        f"Encontrei *{total} pedido{'s' if total > 1 else ''}* para você:"
        if total > 1 else
        "Aqui estão as informações do seu pedido:"
    )

    message = header + "\n\n" + "\n\n".join(blocos)

    if total >= _MAX_PEDIDOS:
        message += f"\n\n_(mostrando os {_MAX_PEDIDOS} pedidos mais recentes)_"

    return {
        "message": message,
        "pedidos": pedidos,
        "total_encontrado": total,
        "lookup_type": lookup_type,
    }
