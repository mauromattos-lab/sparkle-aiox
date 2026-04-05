"""
Webhooks router — ONB-4.

POST /webhooks/asaas       — recebe eventos do Asaas e atualiza gate_details de onboarding
POST /webhooks/autentique  — recebe evento document_signed do Autentique

Ambos os endpoints são graceful: retornam 200 mesmo com payload inesperado.
A validação de autenticidade do Asaas usa o header asaas-access-token (mesmo
mecanismo do /billing/webhook/asaas existente).

O /webhooks/autentique é preparatório (Fase 1): aceita qualquer payload e
não exige token configurado — retorna 200 sempre.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from runtime.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# ── POST /webhooks/asaas ─────────────────────────────────────


@router.post("/asaas")
async def asaas_onboarding_webhook(request: Request):
    """
    Recebe eventos do Asaas e atualiza gate_details de onboarding.

    Eventos processados para onboarding:
    - PAYMENT_RECEIVED / PAYMENT_CONFIRMED → payment_confirmed=True
    - PAYMENT_OVERDUE → payment_overdue=True
    - SUBSCRIPTION_CREATED → subscription_active=True
    - SUBSCRIPTION_CANCELLED → subscription_cancelled=True

    Validação: header asaas-access-token deve corresponder a ASAAS_WEBHOOK_TOKEN.
    Se ASAAS_WEBHOOK_TOKEN não estiver configurado, aceita qualquer token
    (modo permissivo para facilitar testes iniciais — logar warning).

    Sempre retorna 200 para o Asaas não retentar.
    """
    # Validar token do Asaas
    expected_token = settings.asaas_webhook_token
    provided_token = request.headers.get("asaas-access-token", "")

    if expected_token:
        if provided_token != expected_token:
            logger.warning(
                "[webhooks/asaas] token inválido de %s",
                request.client.host if request.client else "unknown",
            )
            # Retornar 200 mas não processar — Asaas não deve saber que rejeitamos
            return {"status": "ok", "processed": False, "reason": "invalid_token"}
    else:
        logger.warning("[webhooks/asaas] ASAAS_WEBHOOK_TOKEN não configurado — modo permissivo")

    # Parse payload graciosamente
    try:
        body = await request.json()
    except Exception as e:
        logger.warning("[webhooks/asaas] payload inválido: %s", e)
        return {"status": "ok", "processed": False, "reason": "invalid_json"}

    event = body.get("event", "")
    payment_data = body.get("payment", {})
    subscription_data = body.get("subscription", {})

    logger.info("[webhooks/asaas] event=%s", event)

    if not event:
        return {"status": "ok", "processed": False, "reason": "no_event"}

    # Delegar ao handler de onboarding
    try:
        from runtime.webhooks.handlers import handle_asaas_onboarding_event
        result = await handle_asaas_onboarding_event(
            event=event,
            payment_data=payment_data if isinstance(payment_data, dict) else {},
            subscription_data=subscription_data if isinstance(subscription_data, dict) else {},
        )
        return {"status": "ok", "event": event, "result": result}
    except Exception as e:
        # Graceful: logar erro mas sempre retornar 200 para o Asaas
        logger.error("[webhooks/asaas] handler error: %s", e)
        return {"status": "ok", "processed": False, "reason": "handler_error", "error": str(e)}


# ── POST /webhooks/autentique ─────────────────────────────────


@router.post("/autentique")
async def autentique_webhook(request: Request):
    """
    Recebe eventos do Autentique.

    Fase 1: endpoint preparatório.
    - Aceita qualquer payload (graceful)
    - Processa evento 'document_signed' se payload válido
    - Não exige token configurado nesta fase
    - Retorna 200 sempre

    Quando Autentique estiver integrado ao Runtime (Fase 2), este endpoint
    já estará pronto para receber os eventos reais.
    """
    # Parse payload graciosamente — sem token de validação na Fase 1
    try:
        body = await request.json()
    except Exception as e:
        logger.warning("[webhooks/autentique] payload inválido: %s", e)
        return {"status": "ok", "processed": False, "reason": "invalid_json"}

    # Autentique pode enviar event no campo 'event' ou 'type'
    event = body.get("event") or body.get("type") or ""
    document_data = body.get("document") or body.get("data") or body

    logger.info("[webhooks/autentique] event=%s", event)

    if not event:
        # Payload sem event — aceitar e ignorar (pode ser ping/verificação)
        return {"status": "ok", "processed": False, "reason": "no_event"}

    # Processar evento document_signed
    try:
        from runtime.webhooks.handlers import handle_autentique_event
        result = await handle_autentique_event(
            event=event,
            document_data=document_data if isinstance(document_data, dict) else {},
        )
        return {"status": "ok", "event": event, "result": result}
    except Exception as e:
        # Graceful: logar erro mas sempre retornar 200
        logger.error("[webhooks/autentique] handler error: %s", e)
        return {"status": "ok", "processed": False, "reason": "handler_error", "error": str(e)}
