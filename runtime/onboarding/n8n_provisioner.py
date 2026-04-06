"""
n8n_provisioner.py — ONB-1.5a

Provisiona infraestrutura técnica para novo cliente Zenya:
- Clone de workflows n8n por tier via n8n API
- Configuração Z-API (criação de instância programática)
- Criação de inbox no Chatwoot

Extraído e expandido de onboard_client.py._clone_workflows_n8n
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import httpx

from runtime.db import supabase

# ── Configuração ─────────────────────────────────────────────────────────────

N8N_BASE = os.environ.get("N8N_BASE_URL", "https://n8n.sparkleai.tech/api/v1")

# Workflows master por tier — IDs confirmados no n8n em 2026-04-05
WORKFLOWS_BY_TIER: dict[str, dict[str, str]] = {
    "essencial": {
        "G0ormrjMIPrTEnVH": "00. {name} - Configurações",
        "r3C1FMc6NIi6eCGI": "05. {name} - Escalar humano",
        "ttMFxQ2UsIpW1HKt": "07. {name} - Quebrar e enviar mensagens",
        "4GWd6qHwbJr3qLUP": "01. {name} - Secretária v3",
    },
    "profissional": {
        # Essencial
        "G0ormrjMIPrTEnVH": "00. {name} - Configurações",
        "r3C1FMc6NIi6eCGI": "05. {name} - Escalar humano",
        "ttMFxQ2UsIpW1HKt": "07. {name} - Quebrar e enviar mensagens",
        "4GWd6qHwbJr3qLUP": "01. {name} - Secretária v3",
        # Profissional adicional
        "FVo76xNYRmjevsqu": "04. {name} - Criar evento Calendar",
        "51kVwiW28a6orNRy": "04.1 {name} - Atualizar agendamento",
        "inc8gUNWJXDv3O3i": "06. {name} - Integração Asaas",
        "YlXyQ785worYXwOk": "09. {name} - Desmarcar agendamento",
        "HLRubTvQRsV2GNJc": "11. {name} - Lembretes de Agendamento",
    },
    "premium": {
        # Essencial + Profissional
        "G0ormrjMIPrTEnVH": "00. {name} - Configurações",
        "r3C1FMc6NIi6eCGI": "05. {name} - Escalar humano",
        "ttMFxQ2UsIpW1HKt": "07. {name} - Quebrar e enviar mensagens",
        "4GWd6qHwbJr3qLUP": "01. {name} - Secretária v3",
        "FVo76xNYRmjevsqu": "04. {name} - Criar evento Calendar",
        "51kVwiW28a6orNRy": "04.1 {name} - Atualizar agendamento",
        "inc8gUNWJXDv3O3i": "06. {name} - Integração Asaas",
        "YlXyQ785worYXwOk": "09. {name} - Desmarcar agendamento",
        "HLRubTvQRsV2GNJc": "11. {name} - Lembretes de Agendamento",
        # Premium adicional
        "SJi5jJ6dQgxcq1fX": "08. {name} - Agente Assistente Interno",
        "Be8SBYrcZcydYD1f": "12. {name} - Gestão de Ligações",
    },
}


# ── Dataclasses de resultado ──────────────────────────────────────────────────

@dataclass
class WorkflowResult:
    workflow_id: str
    workflow_name: str
    status: str  # "cloned" | "failed"
    error: Optional[str] = None


@dataclass
class N8NProvisionResult:
    success: bool
    workflows: list[WorkflowResult] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def cloned_count(self) -> int:
        return sum(1 for w in self.workflows if w.status == "cloned")

    @property
    def workflow_ids_map(self) -> dict[str, str]:
        """Retorna {workflow_id: workflow_name} para gravar no banco."""
        return {w.workflow_id: w.workflow_name for w in self.workflows if w.status == "cloned"}


@dataclass
class ZAPIProvisionResult:
    success: bool
    instance_id: Optional[str] = None
    token: Optional[str] = None
    qr_code_url: Optional[str] = None
    manual_required: bool = False
    error: Optional[str] = None


@dataclass
class ChatwootProvisionResult:
    success: bool
    inbox_id: Optional[int] = None
    inbox_name: Optional[str] = None
    manual_required: bool = False
    error: Optional[str] = None


# ── n8n: clone por tier ───────────────────────────────────────────────────────

def provision_n8n(
    client_id: str,
    business_name: str,
    tier: str,
    phone: str,
    system_prompt: str,
) -> N8NProvisionResult:
    """
    Clona workflows n8n para o cliente conforme o tier.
    Síncrono — chamar via asyncio.to_thread.
    """
    api_key = os.environ.get("N8N_API_KEY", "")
    if not api_key:
        return N8NProvisionResult(
            success=False,
            error="N8N_API_KEY não configurada — clone impossível",
        )

    tier_normalized = tier.lower().strip()
    if tier_normalized not in WORKFLOWS_BY_TIER:
        tier_normalized = "essencial"

    workflow_map = WORKFLOWS_BY_TIER[tier_normalized]
    headers = {"X-N8N-API-KEY": api_key, "Content-Type": "application/json"}
    results: list[WorkflowResult] = []

    for master_id, name_template in workflow_map.items():
        new_name = name_template.format(name=business_name)
        try:
            r = httpx.get(f"{N8N_BASE}/workflows/{master_id}", headers=headers, timeout=10)
            r.raise_for_status()
            wf = r.json()

            wf["name"] = new_name
            for key in ("id", "versionId", "createdAt", "updatedAt"):
                wf.pop(key, None)
            wf["tags"] = [{"name": "Compartilhado"}]
            wf["active"] = False

            # Injeta dados no nó de Configurações
            if "Configurações" in new_name:
                for node in wf.get("nodes", []):
                    if node.get("type") == "n8n-nodes-base.set":
                        assignments = (
                            node.get("parameters", {})
                            .get("assignments", {})
                            .get("assignments", [])
                        )
                        for a in assignments:
                            if a.get("name") == "system_prompt":
                                a["value"] = system_prompt
                            elif a.get("name") == "cliente_telefone":
                                a["value"] = phone
                            elif a.get("name") == "cobranca_valor":
                                a["value"] = 0

            res = httpx.post(f"{N8N_BASE}/workflows", headers=headers, json=wf, timeout=15)
            res.raise_for_status()
            new_id = res.json().get("id", "?")
            results.append(WorkflowResult(workflow_id=new_id, workflow_name=new_name, status="cloned"))
            print(f"[n8n_provisioner] clonado: {new_name} → {new_id}")

        except Exception as e:
            results.append(WorkflowResult(
                workflow_id=master_id, workflow_name=new_name,
                status="failed", error=str(e),
            ))
            print(f"[n8n_provisioner] falha {master_id}: {e}")

    return N8NProvisionResult(
        success=any(r.status == "cloned" for r in results),
        workflows=results,
    )


# ── Z-API: criar instância ────────────────────────────────────────────────────

def provision_zapi(client_id: str, business_name: str) -> ZAPIProvisionResult:
    """
    Cria nova instância Z-API para o cliente.
    Síncrono — chamar via asyncio.to_thread.
    """
    client_token = os.environ.get("ZAPI_CLIENT_TOKEN", "")
    zapi_base = os.environ.get("ZAPI_BASE_URL", "https://api.z-api.io")

    if not client_token:
        return ZAPIProvisionResult(
            success=False, manual_required=True,
            error="ZAPI_CLIENT_TOKEN não configurada",
        )

    try:
        r = httpx.post(
            f"{zapi_base}/instances/create",
            headers={"Content-Type": "application/json", "client-token": client_token},
            json={"name": f"zenya-{client_id[:8]}"},
            timeout=15,
        )

        if r.status_code in (200, 201):
            data = r.json()
            instance_id = data.get("id") or data.get("instance", {}).get("id")
            token = data.get("token") or data.get("instance", {}).get("token")
            qr_url = data.get("qrcode") or data.get("qrCode")

            if instance_id:
                return ZAPIProvisionResult(
                    success=True,
                    instance_id=instance_id,
                    token=token,
                    qr_code_url=qr_url,
                )

        return ZAPIProvisionResult(
            success=False, manual_required=True,
            error=f"Z-API {r.status_code} sem instance_id — criar manualmente em z-api.io",
        )

    except Exception as e:
        return ZAPIProvisionResult(
            success=False, manual_required=True,
            error=f"Z-API create falhou ({e}) — criar manualmente em z-api.io",
        )


# ── Chatwoot: criar inbox ─────────────────────────────────────────────────────

def provision_chatwoot(client_id: str, business_name: str) -> ChatwootProvisionResult:
    """
    Cria inbox no Chatwoot para o cliente.
    Requer CHATWOOT_URL, CHATWOOT_API_TOKEN, CHATWOOT_ACCOUNT_ID no .env.
    Síncrono — chamar via asyncio.to_thread.
    """
    chatwoot_url = os.environ.get("CHATWOOT_URL", "")
    api_token = os.environ.get("CHATWOOT_API_TOKEN", "")
    account_id = os.environ.get("CHATWOOT_ACCOUNT_ID", "")

    if not all([chatwoot_url, api_token, account_id]):
        missing = [k for k, v in {
            "CHATWOOT_URL": chatwoot_url,
            "CHATWOOT_API_TOKEN": api_token,
            "CHATWOOT_ACCOUNT_ID": account_id,
        }.items() if not v]
        return ChatwootProvisionResult(
            success=False, manual_required=True,
            error=f"Variáveis ausentes: {', '.join(missing)} — adicionar ao .env",
        )

    inbox_name = f"{business_name} — Zenya"
    headers = {"api_access_token": api_token, "Content-Type": "application/json"}

    try:
        r = httpx.post(
            f"{chatwoot_url}/api/v1/accounts/{account_id}/inboxes",
            headers=headers,
            json={"name": inbox_name, "channel": {"type": "api"}},
            timeout=10,
        )
        r.raise_for_status()
        inbox_id = r.json().get("id")

        # Labels padrão (falha silenciosa se já existem)
        for label in ["novo-lead", "em-atendimento", "resolvido", "escalar-humano"]:
            try:
                httpx.post(
                    f"{chatwoot_url}/api/v1/accounts/{account_id}/labels",
                    headers=headers,
                    json={"title": label, "color": "#1F93FF"},
                    timeout=5,
                )
            except Exception:
                pass

        return ChatwootProvisionResult(success=True, inbox_id=inbox_id, inbox_name=inbox_name)

    except Exception as e:
        return ChatwootProvisionResult(
            success=False, manual_required=True,
            error=f"Chatwoot inbox falhou: {e}",
        )


# ── Orquestrador principal ────────────────────────────────────────────────────

async def provision_technical_infrastructure(
    client_id: str,
    business_name: str,
    tier: str,
    phone: str,
    system_prompt: str,
    session_id: Optional[str] = None,
) -> dict:
    """
    Orquestra n8n + Z-API + Chatwoot em paralelo.
    Atualiza zenya_clients com resultados.
    Retorna resumo com pendências humanas.
    """
    n8n_result, zapi_result, chatwoot_result = await asyncio.gather(
        asyncio.to_thread(provision_n8n, client_id, business_name, tier, phone, system_prompt),
        asyncio.to_thread(provision_zapi, client_id, business_name),
        asyncio.to_thread(provision_chatwoot, client_id, business_name),
    )

    # Atualiza zenya_clients com o que foi provisionado
    update_data: dict = {
        "tier": tier,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if n8n_result.success:
        update_data["n8n_workflow_ids"] = n8n_result.workflow_ids_map
    if zapi_result.success and zapi_result.instance_id:
        update_data["zapi_instance_id"] = zapi_result.instance_id
        if zapi_result.token:
            update_data["zapi_token"] = zapi_result.token
    if chatwoot_result.success and chatwoot_result.inbox_id:
        update_data["chatwoot_inbox_id"] = str(chatwoot_result.inbox_id)
    # testing_mode permanece true até go-live confirmado por QA
    update_data["testing_mode"] = "true"

    try:
        await asyncio.to_thread(
            lambda: supabase.table("zenya_clients")
            .update(update_data)
            .eq("client_id", client_id)
            .execute()
        )
    except Exception as e:
        print(f"[n8n_provisioner] update zenya_clients falhou: {e}")

    # Pendências humanas
    pending = []
    if not zapi_result.success or zapi_result.manual_required:
        pending.append(f"• Z-API: {zapi_result.error or 'criar instância em z-api.io'}")
    else:
        pending.append(
            f"• Z-API: conectar WhatsApp via QR code "
            f"(instância {zapi_result.instance_id} criada, aguardando conexão)"
        )
    if not chatwoot_result.success or chatwoot_result.manual_required:
        pending.append(f"• Chatwoot: {chatwoot_result.error or 'criar inbox manualmente'}")

    return {
        "n8n": {
            "success": n8n_result.success,
            "cloned": n8n_result.cloned_count,
            "total": len(n8n_result.workflows),
            "workflow_ids": n8n_result.workflow_ids_map,
            "failures": [w.workflow_name for w in n8n_result.workflows if w.status == "failed"],
        },
        "zapi": {
            "success": zapi_result.success,
            "instance_id": zapi_result.instance_id,
            "manual_required": zapi_result.manual_required,
        },
        "chatwoot": {
            "success": chatwoot_result.success,
            "inbox_id": chatwoot_result.inbox_id,
            "manual_required": chatwoot_result.manual_required,
        },
        "pending_human": pending,
    }
