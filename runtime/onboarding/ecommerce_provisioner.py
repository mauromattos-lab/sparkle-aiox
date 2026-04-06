"""
ecommerce_provisioner.py — ONB-1.5b

Provisiona integrações e-commerce para clientes Zenya:
- Loja Integrada: valida API key + armazena
- Nuvemshop: valida credenciais + armazena
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx

from runtime.db import supabase


@dataclass
class EcommerceResult:
    success: bool
    platform: str
    validated: bool = False
    manual_required: bool = False
    error: Optional[str] = None


def provision_loja_integrada(client_id: str, api_key: str) -> EcommerceResult:
    """
    Valida API key da Loja Integrada e armazena em zenya_clients.
    Síncrono — chamar via asyncio.to_thread.
    """
    if not api_key or not api_key.strip():
        return EcommerceResult(
            success=False,
            platform="loja_integrada",
            error="API key não fornecida",
        )

    try:
        r = httpx.get(
            "https://api.lojaintegrada.com.br/v1/orders",
            params={"limit": 1},
            headers={"Authorization": f"chave={api_key}"},
            timeout=10,
        )

        if r.status_code == 401:
            return EcommerceResult(
                success=False,
                platform="loja_integrada",
                validated=False,
                error="API key inválida (401 Unauthorized)",
            )

        if r.status_code in (200, 404):
            # 404 = loja sem pedidos ainda, key válida
            supabase.table("zenya_clients").update({
                "loja_integrada_api_key": api_key,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("client_id", client_id).execute()

            print(f"[ecommerce_provisioner] Loja Integrada configurada para {client_id}")
            return EcommerceResult(success=True, platform="loja_integrada", validated=True)

        return EcommerceResult(
            success=False,
            platform="loja_integrada",
            error=f"Loja Integrada respondeu {r.status_code} — verificar API key",
        )

    except Exception as e:
        return EcommerceResult(
            success=False,
            platform="loja_integrada",
            error=f"Validação falhou: {e}",
        )


def provision_nuvemshop(client_id: str, store_id: str, access_token: str) -> EcommerceResult:
    """
    Valida credenciais da Nuvemshop e armazena em zenya_clients.
    Síncrono — chamar via asyncio.to_thread.
    """
    if not store_id or not access_token:
        return EcommerceResult(
            success=False,
            platform="nuvemshop",
            error="store_id ou access_token não fornecidos",
        )

    try:
        r = httpx.get(
            f"https://api.nuvemshop.com.br/v1/{store_id}/orders",
            params={"per_page": 1},
            headers={
                "Authentication": f"bearer {access_token}",
                "User-Agent": "Sparkle Zenya (suporte@sparkleai.tech)",
            },
            timeout=10,
        )

        if r.status_code == 401:
            return EcommerceResult(
                success=False,
                platform="nuvemshop",
                validated=False,
                error="Credenciais inválidas (401 Unauthorized)",
            )

        if r.status_code in (200, 404):
            supabase.table("zenya_clients").update({
                "nuvemshop_store_id": store_id,
                "nuvemshop_token": access_token,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("client_id", client_id).execute()

            print(f"[ecommerce_provisioner] Nuvemshop configurada para {client_id}")
            return EcommerceResult(success=True, platform="nuvemshop", validated=True)

        return EcommerceResult(
            success=False,
            platform="nuvemshop",
            error=f"Nuvemshop respondeu {r.status_code} — verificar credenciais",
        )

    except Exception as e:
        return EcommerceResult(
            success=False,
            platform="nuvemshop",
            error=f"Validação falhou: {e}",
        )


async def provision_ecommerce(
    client_id: str,
    business_type: str,
    loja_integrada_key: Optional[str] = None,
    nuvemshop_store_id: Optional[str] = None,
    nuvemshop_token: Optional[str] = None,
) -> dict:
    """
    Provisiona e-commerce baseado no tipo de negócio.
    Se perfil não é e-commerce → retorna skipped.
    """
    if business_type.lower() not in ("ecommerce", "loja", "loja_online", "e-commerce"):
        return {"skipped": True, "reason": f"business_type={business_type} não requer e-commerce"}

    results = {}

    if loja_integrada_key:
        result = await asyncio.to_thread(
            provision_loja_integrada, client_id, loja_integrada_key
        )
        results["loja_integrada"] = {
            "success": result.success,
            "validated": result.validated,
            "error": result.error,
        }

    if nuvemshop_store_id and nuvemshop_token:
        result = await asyncio.to_thread(
            provision_nuvemshop, client_id, nuvemshop_store_id, nuvemshop_token
        )
        results["nuvemshop"] = {
            "success": result.success,
            "validated": result.validated,
            "error": result.error,
        }

    if not results:
        results["status"] = "no_credentials_provided"

    return results
