"""
generate_contract handler — Story 1.2 (AC-1.x / AC-2.x / AC-5.x)

Gera contrato Zenya via Autentique e envia link de assinatura ao cliente.

Task payload:
{
    "client_id": "<uuid>"
}

Sequência:
1. Busca dados do cliente (clients + zenya_clients + onboarding_workflows)
2. Idempotência: se autentique_document_id já existe em gate_details → skip
3. Preenche template via contract_filler
4. Cria documento na API Autentique (GraphQL)
5. Salva autentique_document_id em gate_details da fase contract
6. Envia link de assinatura por WhatsApp (se phone disponível)
7. Registra evento contract_sent em onboarding_events
8. Alerta Friday
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

import httpx

from runtime.config import settings
from runtime.db import supabase
from runtime.onboarding.contract_filler import fill_contract

logger = logging.getLogger(__name__)

# ── Autentique GraphQL ─────────────────────────────────────────

# TODO: Verificar estrutura exata do GraphQL mutation com docs Autentique
AUTENTIQUE_GRAPHQL_URL = "https://api.autentique.com.br/v2/graphql"

_CREATE_DOCUMENT_MUTATION = """
mutation CreateDocument(
  $name: String!,
  $content: String!,
  $signers: [SignerInput!]!,
  $config: DocumentConfig
) {
  createDocument(
    document: { name: $name, content: $content }
    signers: $signers
    config: $config
  ) {
    id
    name
    created_at
    files {
      original
    }
    signatures {
      public_id
      name
      email
      link {
        short_link
      }
      action {
        name
      }
    }
  }
}
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _get_autentique_token() -> str | None:
    token = os.environ.get("AUTENTIQUE_TOKEN", "")
    if not token:
        logger.warning("[generate_contract] AUTENTIQUE_TOKEN nao configurado no .env")
    return token or None


async def _create_autentique_document(
    token: str,
    title: str,
    content: str,
    signer_name: str,
    signer_email: str,
) -> dict:
    """
    Cria documento no Autentique via GraphQL.

    Retorna o objeto do documento criado (incluindo id e link de assinatura).
    Lança httpx.HTTPError ou ValueError em caso de falha.
    """
    variables = {
        "name": title,
        "content": content,
        "signers": [
            {
                "email": signer_email,
                "action": "SIGN",
                "name": signer_name,
            }
        ],
        "config": {
            "notification_finished": True,
            "notification_signed": True,
        },
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            AUTENTIQUE_GRAPHQL_URL,
            json={"query": _CREATE_DOCUMENT_MUTATION, "variables": variables},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        data = response.json()

    errors = data.get("errors")
    if errors:
        raise ValueError(f"Autentique GraphQL errors: {errors}")

    doc = data.get("data", {}).get("createDocument")
    if not doc:
        raise ValueError(f"Autentique: createDocument retornou vazio — resposta: {data}")

    return doc


async def _update_workflow_gate_details(client_id: str, updates: dict) -> bool:
    """Faz merge de updates em onboarding_workflows.gate_details para a fase 'contract'."""
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("onboarding_workflows")
            .select("id, gate_details")
            .eq("client_id", client_id)
            .eq("phase", "contract")
            .maybe_single()
            .execute()
        )
        if not res.data:
            logger.warning("[generate_contract] onboarding_workflows/contract nao encontrado para client_id=%s", client_id)
            return False

        wf_id = res.data["id"]
        current = res.data.get("gate_details") or {}
        merged = {**current, **updates, "updated_at": _now()}

        await asyncio.to_thread(
            lambda: supabase.table("onboarding_workflows")
            .update({"gate_details": merged, "updated_at": _now()})
            .eq("id", wf_id)
            .execute()
        )
        logger.info("[generate_contract] gate_details atualizado client_id=%s", client_id)
        return True
    except Exception as e:
        logger.error("[generate_contract] falha ao atualizar gate_details client_id=%s: %s", client_id, e)
        return False


async def _log_event(client_id: str, event_type: str, payload: dict) -> None:
    try:
        await asyncio.to_thread(
            lambda: supabase.table("onboarding_events").insert({
                "client_id": client_id,
                "event_type": event_type,
                "phase": "contract",
                "payload": payload,
            }).execute()
        )
    except Exception as e:
        logger.warning("[generate_contract] falha ao registrar evento '%s': %s", event_type, e)


async def _send_whatsapp(phone: str, message: str) -> None:
    try:
        from runtime.integrations.zapi import send_text
        await asyncio.to_thread(send_text, phone, message)
        logger.info("[generate_contract] WhatsApp enviado para %s...", phone[:8])
    except Exception as e:
        logger.warning("[generate_contract] falha ao enviar WhatsApp: %s", e)


async def _alert_friday(message: str) -> None:
    mauro_phone = settings.mauro_whatsapp
    if not mauro_phone:
        logger.warning("[generate_contract] MAURO_WHATSAPP nao configurado — alerta nao enviado: %s", message)
        return
    try:
        from runtime.integrations.zapi import send_text
        await asyncio.to_thread(send_text, mauro_phone, f"[Friday] {message}")
    except Exception as e:
        logger.warning("[generate_contract] falha ao alertar Friday: %s", e)


async def handle_generate_contract(task: dict) -> dict:
    """
    AC-1.2/1.3/1.4 — Gera contrato e envia para assinatura.

    Payload: { "client_id": "<uuid>" }
    """
    payload = task.get("payload", {})
    client_id = (payload.get("client_id") or task.get("client_id") or "").strip()

    if not client_id:
        return {"status": "error", "error": "client_id e obrigatorio"}

    # ── 1. Busca dados do cliente ─────────────────────────────
    try:
        client_res, zenya_res, wf_res = await asyncio.gather(
            asyncio.to_thread(
                lambda: supabase.table("clients")
                .select("id,name,whatsapp,email,mrr,plan,niche")
                .eq("id", client_id)
                .maybe_single()
                .execute()
            ),
            asyncio.to_thread(
                lambda: supabase.table("zenya_clients")
                .select("client_id,business_name,business_type,testing_mode")
                .eq("client_id", client_id)
                .maybe_single()
                .execute()
            ),
            asyncio.to_thread(
                lambda: supabase.table("onboarding_workflows")
                .select("id,phase,gate_details,status")
                .eq("client_id", client_id)
                .eq("phase", "contract")
                .maybe_single()
                .execute()
            ),
        )
    except Exception as e:
        logger.error("[generate_contract] falha ao buscar dados client_id=%s: %s", client_id, e)
        return {"status": "error", "error": f"Falha ao buscar dados do cliente: {e}"}

    client = client_res.data if client_res else None
    if not client:
        return {"status": "error", "error": f"Cliente nao encontrado: client_id={client_id}"}

    wf = wf_res.data if wf_res else None

    # ── 2. Idempotência — AC-5.1 ─────────────────────────────
    if wf:
        gate_details = wf.get("gate_details") or {}
        existing_doc_id = gate_details.get("autentique_document_id")
        if existing_doc_id:
            logger.info(
                "[generate_contract] SKIP — autentique_document_id ja existe para client_id=%s: %s",
                client_id, existing_doc_id,
            )
            return {
                "status": "skipped",
                "reason": "contract_already_sent",
                "client_id": client_id,
                "autentique_document_id": existing_doc_id,
            }

    # AC-5.3: Nao processar clientes em producao fora do onboarding
    zenya = zenya_res.data if zenya_res else None
    if zenya and zenya.get("testing_mode") == "live":
        logger.warning(
            "[generate_contract] BLOCKED — cliente em producao (testing_mode=live): client_id=%s",
            client_id,
        )
        return {
            "status": "error",
            "error": "Cliente ja esta em producao — generate_contract nao aplicavel",
        }

    # ── 3. Monta dados para preencher template ────────────────
    client_data = {
        "empresa":          client.get("name", ""),
        "cnpj_cpf":         "",  # coletado no intake, pode ser vazio na Fase 1
        "valor_mensal":     client.get("mrr") or 0,
        "plano":            client.get("plan") or "essencial",
        "signatario_nome":  client.get("name", ""),
        "signatario_email": client.get("email", ""),
    }
    contract_content = fill_contract(client_data)

    doc_title = f"Contrato Zenya — {client.get('name', client_id)}"

    # ── 4. Chama API Autentique ───────────────────────────────
    token = await _get_autentique_token()
    if not token:
        return {
            "status": "error",
            "error": (
                "AUTENTIQUE_TOKEN nao configurado. "
                "Adicione ao .env e reinicie o Runtime."
            ),
        }

    signer_name = client_data["signatario_nome"] or client.get("name", "")
    signer_email = client_data["signatario_email"]

    if not signer_email:
        logger.warning(
            "[generate_contract] signatario_email vazio para client_id=%s — Autentique pode rejeitar",
            client_id,
        )

    try:
        doc = await _create_autentique_document(
            token=token,
            title=doc_title,
            content=contract_content,
            signer_name=signer_name,
            signer_email=signer_email,
        )
    except Exception as e:
        logger.error("[generate_contract] falha ao criar documento Autentique: %s", e)
        await _alert_friday(
            f"ERRO ao gerar contrato de {client.get('name', client_id)}: {e}"
        )
        return {"status": "error", "error": f"Falha na API Autentique: {e}"}

    document_id = doc.get("id", "")

    # Extrai link de assinatura da primeira assinatura
    signatures = doc.get("signatures") or []
    sign_link = ""
    for sig in signatures:
        link_obj = sig.get("link") or {}
        sign_link = link_obj.get("short_link") or link_obj.get("link") or ""
        if sign_link:
            break

    # ── 5. Salva document_id em gate_details ─────────────────
    await _update_workflow_gate_details(
        client_id,
        {
            "autentique_document_id": document_id,
            "autentique_sign_link": sign_link,
            "contract_sent_at": _now(),
        },
    )

    # ── 6. Envia link por WhatsApp (AC-2.2/2.3) ──────────────
    phone = client.get("whatsapp") or ""
    client_name_short = (client.get("name") or "").split()[0] or "cliente"

    if phone and sign_link:
        wpp_msg = (
            f"Oi {client_name_short}! Aqui esta o contrato da sua Zenya para assinar: "
            f"{sign_link}"
        )
        await _send_whatsapp(phone, wpp_msg)
    elif not phone:
        logger.info(
            "[generate_contract] phone nao disponivel para client_id=%s — envio por email (Autentique)",
            client_id,
        )

    # ── 7. Registra evento contract_sent (AC-3.4) ────────────
    await _log_event(
        client_id=client_id,
        event_type="contract_sent",
        payload={
            "autentique_document_id": document_id,
            "sign_link": sign_link,
            "signer_email": signer_email,
            "sent_via_whatsapp": bool(phone and sign_link),
        },
    )

    # ── 8. Alerta Friday ──────────────────────────────────────
    await _alert_friday(
        f"Contrato de {client.get('name', client_id)} enviado para assinatura. "
        f"Doc ID: {document_id}"
    )

    return {
        "status": "ok",
        "client_id": client_id,
        "autentique_document_id": document_id,
        "sign_link": sign_link,
        "sent_via_whatsapp": bool(phone and sign_link),
        "signer_email": signer_email,
    }
