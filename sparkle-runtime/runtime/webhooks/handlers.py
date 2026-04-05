"""
Webhook handlers — ONB-4 + Story 1.2.

Processa eventos de webhooks externos e atualiza gate_details no onboarding.

handle_asaas_onboarding_event  — processa eventos Asaas e atualiza flags de onboarding
handle_autentique_event        — processa evento document_signed do Autentique
                                 Story 1.2: identifica client via autentique_document_id em gate_details,
                                 marca contract_signed=true, registra evento, alerta Friday.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from runtime.config import settings
from runtime.db import supabase

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _get_client_id_from_asaas_customer(asaas_customer_id: str) -> str | None:
    """Resolve client_id a partir do asaas_customer_id na tabela subscriptions."""
    if not asaas_customer_id:
        return None
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("subscriptions")
            .select("client_id")
            .eq("asaas_customer_id", asaas_customer_id)
            .maybe_single()
            .execute()
        )
        if res.data:
            return res.data.get("client_id")
    except Exception as e:
        logger.warning("[webhooks] falha ao resolver client_id para asaas_customer=%s: %s", asaas_customer_id, e)
    return None


async def _get_client_id_from_asaas_subscription(asaas_subscription_id: str) -> str | None:
    """Resolve client_id a partir do asaas_subscription_id na tabela subscriptions."""
    if not asaas_subscription_id:
        return None
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("subscriptions")
            .select("client_id")
            .eq("asaas_subscription_id", asaas_subscription_id)
            .maybe_single()
            .execute()
        )
        if res.data:
            return res.data.get("client_id")
    except Exception as e:
        logger.warning("[webhooks] falha ao resolver client_id para asaas_sub=%s: %s", asaas_subscription_id, e)
    return None


async def _update_gate_details(client_id: str, updates: dict) -> bool:
    """
    Faz merge de `updates` em onboarding_sessions.gate_details para o client_id.
    Retorna True se encontrou e atualizou, False se sessão não encontrada.
    """
    try:
        # Busca gate_details atual
        res = await asyncio.to_thread(
            lambda: supabase.table("onboarding_sessions")
            .select("id, gate_details")
            .eq("client_id", client_id)
            .maybe_single()
            .execute()
        )
        if not res.data:
            logger.warning("[webhooks] onboarding_sessions não encontrado para client_id=%s", client_id)
            return False

        session_id = res.data["id"]
        current_gate = res.data.get("gate_details") or {}
        merged = {**current_gate, **updates, "updated_at": _now()}

        await asyncio.to_thread(
            lambda: supabase.table("onboarding_sessions")
            .update({
                "gate_details": merged,
                "updated_at": _now(),
            })
            .eq("id", session_id)
            .execute()
        )
        logger.info("[webhooks] gate_details atualizado client_id=%s updates=%s", client_id, updates)
        return True
    except Exception as e:
        logger.error("[webhooks] falha ao atualizar gate_details client_id=%s: %s", client_id, e)
        return False


async def handle_asaas_onboarding_event(event: str, payment_data: dict, subscription_data: dict) -> dict:
    """
    Processa eventos Asaas relevantes para onboarding e atualiza gate_details.

    Eventos tratados:
    - PAYMENT_RECEIVED / PAYMENT_CONFIRMED: marca payment_confirmed=True
    - PAYMENT_OVERDUE: marca payment_overdue=True
    - SUBSCRIPTION_CREATED: registra subscription_active=True
    - SUBSCRIPTION_CANCELLED: marca subscription_cancelled=True

    Retorna dict com status e client_id resolvido (se encontrado).
    """
    asaas_customer_id = (
        payment_data.get("customer")
        or subscription_data.get("customer")
    )
    asaas_subscription_id = (
        payment_data.get("subscription")
        or subscription_data.get("id")
    )

    # Resolver client_id — tenta por customer primeiro, depois por subscription
    client_id = await _get_client_id_from_asaas_customer(asaas_customer_id)
    if not client_id and asaas_subscription_id:
        client_id = await _get_client_id_from_asaas_subscription(asaas_subscription_id)

    if not client_id:
        logger.info(
            "[webhooks/asaas] client_id não encontrado para customer=%s sub=%s — evento=%s ignorado para onboarding",
            asaas_customer_id, asaas_subscription_id, event,
        )
        return {"status": "no_client_found", "event": event}

    gate_updates: dict = {}

    if event in ("PAYMENT_RECEIVED", "PAYMENT_CONFIRMED"):
        gate_updates["payment_confirmed"] = True
        gate_updates["payment_confirmed_at"] = _now()
        gate_updates["payment_event"] = event

    elif event == "PAYMENT_OVERDUE":
        gate_updates["payment_overdue"] = True
        gate_updates["payment_overdue_at"] = _now()

    elif event == "SUBSCRIPTION_CREATED":
        gate_updates["subscription_active"] = True
        gate_updates["subscription_created_at"] = _now()

    elif event == "SUBSCRIPTION_CANCELLED":
        gate_updates["subscription_cancelled"] = True
        gate_updates["subscription_cancelled_at"] = _now()

    if gate_updates:
        updated = await _update_gate_details(client_id, gate_updates)
        return {
            "status": "updated" if updated else "session_not_found",
            "client_id": client_id,
            "event": event,
            "gate_updates": gate_updates,
        }

    return {"status": "event_not_mapped", "event": event, "client_id": client_id}


async def _get_client_id_from_autentique_document(document_id: str) -> str | None:
    """
    Story 1.2 AC-3.2: Resolve client_id via autentique_document_id em onboarding_workflows.gate_details.

    Busca todos os workflows da fase 'contract' onde gate_details contém o document_id.
    Mais confiável do que depender de metadata do Autentique.
    """
    if not document_id:
        return None
    try:
        # Filtra workflows da fase contract que têm autentique_document_id no gate_details
        res = await asyncio.to_thread(
            lambda: supabase.table("onboarding_workflows")
            .select("client_id, gate_details")
            .eq("phase", "contract")
            .execute()
        )
        if not res.data:
            return None
        for row in res.data:
            gd = row.get("gate_details") or {}
            if gd.get("autentique_document_id") == document_id:
                return row.get("client_id")
    except Exception as e:
        logger.warning("[webhooks/autentique] falha ao buscar client por document_id=%s: %s", document_id, e)
    return None


async def _log_onboarding_event(
    client_id: str,
    event_type: str,
    phase: str = "contract",
    payload: dict | None = None,
) -> None:
    """Insere evento em onboarding_events."""
    try:
        await asyncio.to_thread(
            lambda: supabase.table("onboarding_events").insert({
                "client_id": client_id,
                "event_type": event_type,
                "phase": phase,
                "payload": payload or {},
            }).execute()
        )
    except Exception as e:
        logger.warning("[webhooks] falha ao registrar evento '%s' para client_id=%s: %s", event_type, client_id, e)


async def _alert_friday(message: str) -> None:
    """Envia alerta para Friday (Mauro via WhatsApp)."""
    mauro_phone = settings.mauro_whatsapp
    if not mauro_phone:
        logger.warning("[webhooks] MAURO_WHATSAPP nao configurado — alerta Friday nao enviado: %s", message)
        return
    try:
        from runtime.integrations.zapi import send_text
        await asyncio.to_thread(send_text, mauro_phone, f"[Friday] {message}")
    except Exception as e:
        logger.warning("[webhooks] falha ao alertar Friday: %s", e)


async def handle_autentique_event(event: str, document_data: dict) -> dict:
    """
    Processa evento document_signed do Autentique e marca contract_signed=True.

    Story 1.2 AC-3.1/3.2/3.3/3.4/3.5:
    Resolução de client_id em ordem de prioridade:
    1. autentique_document_id em onboarding_workflows.gate_details (mais confiável)
    2. externalId / referer / client_id no payload do documento
    3. Fallback: email do signatário na tabela clients

    Retorna dict com status e client_id.
    """
    document_id = document_data.get("id") or ""

    # ── 1. Busca por document_id em gate_details (AC-3.2) ────
    client_id = None
    if document_id:
        client_id = await _get_client_id_from_autentique_document(document_id)

    # ── 2. Metadata do documento ──────────────────────────────
    if not client_id:
        client_id = (
            document_data.get("externalId")
            or document_data.get("referer")
            or document_data.get("client_id")
        )

    # ── 3. Fallback: buscar por email do signatário ───────────
    if not client_id:
        signers = document_data.get("signatures") or document_data.get("signers") or []
        for signer in signers:
            email = signer.get("email") or signer.get("action", {}).get("email")
            if email:
                try:
                    res = await asyncio.to_thread(
                        lambda: supabase.table("clients")
                        .select("id")
                        .eq("email", email)
                        .maybe_single()
                        .execute()
                    )
                    if res.data:
                        client_id = res.data["id"]
                        break
                except Exception as e:
                    logger.warning("[webhooks/autentique] falha ao buscar client por email=%s: %s", email, e)

    if not client_id:
        logger.warning("[webhooks/autentique] não foi possível resolver client_id — event=%s", event)
        return {"status": "no_client_found", "event": event}

    if event == "document_signed":
        # AC-3.3: Atualiza gate_details com contract_signed=True
        gate_updates = {
            "contract_signed": True,
            "contract_signed_at": _now(),
            "autentique_document_id": document_id or document_data.get("id"),
        }
        updated = await _update_gate_details(client_id, gate_updates)

        # AC-3.4: Registra evento em onboarding_events
        await _log_onboarding_event(
            client_id=client_id,
            event_type="contract_signed",
            phase="contract",
            payload={
                "autentique_document_id": document_id,
                "event": event,
                "source": "autentique_webhook",
            },
        )

        # AC-3.5: Busca nome do cliente para alerta Friday
        client_name = client_id
        try:
            c_res = await asyncio.to_thread(
                lambda: supabase.table("clients")
                .select("name")
                .eq("id", client_id)
                .maybe_single()
                .execute()
            )
            if c_res and c_res.data:
                client_name = c_res.data.get("name", client_id)
        except Exception:
            pass

        await _alert_friday(
            f"Contrato de {client_name} assinado. Aguardando pagamento para Gate 1."
        )

        return {
            "status": "updated" if updated else "session_not_found",
            "client_id": client_id,
            "event": event,
            "gate_updates": gate_updates,
        }

    return {"status": "event_not_mapped", "event": event, "client_id": client_id}
