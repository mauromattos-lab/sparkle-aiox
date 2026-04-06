"""
LIFECYCLE-3.1 — Proposta Automatica Personalizada.

Generates proposals from BANT data + niche templates.
Friday previews for Mauro before sending.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from runtime.db import supabase
from runtime.config import settings

logger = logging.getLogger(__name__)

NICHE_MAP = {
    "confeitaria": "confeitaria",
    "bakery": "confeitaria",
    "escola": "escola",
    "school": "escola",
    "educacao": "escola",
    "otica": "otica",
    "optica": "otica",
    "eyewear": "otica",
    "ecommerce": "ecommerce",
    "loja": "ecommerce",
    "store": "ecommerce",
    "clinica": "clinica",
    "clinic": "clinica",
    "consultorio": "clinica",
    "varejo": "generic",
    "retail": "generic",
}


def _resolve_niche(business_type: str) -> str:
    if not business_type:
        return "generic"
    bt = business_type.lower().strip()
    return NICHE_MAP.get(bt, "generic")


def _load_template(niche: str) -> str:
    templates = {
        "confeitaria": (
            "Oi {name}!\n\n"
            "Vi que a *{business}* trabalha com confeitaria - um nicho que a gente ama!\n\n"
            "A Zenya pode transformar seu atendimento no WhatsApp:\n"
            "- Responde clientes 24/7 com cardapio, precos e disponibilidade\n"
            "- Agenda encomendas automaticamente\n"
            "- Confirma pedidos e envia lembretes de retirada\n\n"
            "{case_section}"
            "Investimento: {price}\n"
            "Timeline: Zenya ativa em {timeline}\n\n"
            "Quer ver uma demo personalizada pro seu negocio?"
        ),
        "escola": (
            "Oi {name}!\n\n"
            "Trabalhar com educacao e incrivel - e a *{business}* pode atender ainda melhor!\n\n"
            "A Zenya automatiza o atendimento da sua escola:\n"
            "- Responde duvidas de pais 24/7 (horarios, valores, vagas)\n"
            "- Agenda visitas e matriculas\n"
            "- Envia lembretes de reunioes e eventos\n\n"
            "{case_section}"
            "Investimento: {price}\n"
            "Timeline: Zenya ativa em {timeline}\n\n"
            "Posso montar uma demo com o perfil da {business}?"
        ),
        "otica": (
            "Oi {name}!\n\n"
            "Vi que a *{business}* e do ramo optico - temos resultados incriveis nesse nicho!\n\n"
            "A Zenya pode revolucionar seu atendimento:\n"
            "- Responde sobre lentes, armacoes e precos 24/7\n"
            "- Agenda consultas e exames automaticamente\n"
            "- Confirma consultas e reduz faltas\n\n"
            "{case_section}"
            "Investimento: {price}\n"
            "Timeline: Zenya ativa em {timeline}\n\n"
            "Bora agendar uma demo rapida?"
        ),
        "ecommerce": (
            "Oi {name}!\n\n"
            "E-commerce precisa de atendimento rapido - e a *{business}* pode ter isso 24/7!\n\n"
            "A Zenya integra com sua loja:\n"
            "- Responde sobre produtos, estoque e frete em tempo real\n"
            "- Acompanha pedidos e envia atualizacoes\n"
            "- Recupera carrinhos abandonados via WhatsApp\n\n"
            "{case_section}"
            "Investimento: {price}\n"
            "Timeline: Zenya ativa em {timeline}\n\n"
            "Quer ver como ficaria pro seu e-commerce?"
        ),
        "clinica": (
            "Oi {name}!\n\n"
            "Clinicas e consultorios precisam de atendimento humanizado - a Zenya faz isso pela *{business}*!\n\n"
            "- Agenda consultas 24/7 sem secretaria\n"
            "- Confirma e lembra pacientes automaticamente\n"
            "- Responde duvidas frequentes com a voz do seu consultorio\n\n"
            "{case_section}"
            "Investimento: {price}\n"
            "Timeline: Zenya ativa em {timeline}\n\n"
            "Posso preparar uma demo personalizada?"
        ),
        "generic": (
            "Oi {name}!\n\n"
            "A *{business}* pode ter atendimento inteligente 24/7 no WhatsApp!\n\n"
            "A Zenya e uma assistente de IA que:\n"
            "- Atende seus clientes com a voz da sua marca\n"
            "- Agenda, tira duvidas e qualifica leads automaticamente\n"
            "- Funciona 24/7 sem pausas\n\n"
            "{case_section}"
            "Investimento: {price}\n"
            "Timeline: Zenya ativa em {timeline}\n\n"
            "Quer ver como ficaria pro seu negocio?"
        ),
    }
    return templates.get(niche, templates["generic"])


def _estimate_price(bant: dict) -> str:
    budget = bant.get("budget", "")
    if isinstance(budget, (int, float)):
        if budget >= 800:
            return "R$897/mes (Premium)"
        elif budget >= 400:
            return "R$500/mes (Standard)"
        else:
            return "A partir de R$297/mes"
    return "A partir de R$297/mes"


def _estimate_timeline(bant: dict) -> str:
    timeline = bant.get("timeline", "")
    if isinstance(timeline, str) and "urg" in timeline.lower():
        return "48 horas"
    return "5-7 dias uteis"


async def _find_similar_case(niche: str) -> Optional[dict]:
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("auto_cases")
            .select("title, content, metrics, quote")
            .eq("niche", niche)
            .eq("status", "approved")
            .order("generated_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return rows[0] if rows else None
    except Exception:
        return None


async def generate_proposal(lead_id: str) -> dict:
    lead_res = await asyncio.to_thread(
        lambda: supabase.table("leads")
        .select("*")
        .eq("id", lead_id)
        .maybe_single()
        .execute()
    )
    lead = lead_res.data if lead_res and hasattr(lead_res, "data") else lead_res
    if not lead:
        return {"error": "Lead not found"}

    name = lead.get("name", "")
    business = lead.get("business_name", "")
    business_type = lead.get("business_type", "")
    bant = lead.get("bant_summary") or {}

    niche = _resolve_niche(business_type)
    template = _load_template(niche)

    case = await _find_similar_case(niche)
    case_section = ""
    if case:
        case_section = f"Case de sucesso: {case.get('title', '')}\n{case.get('quote', '')}\n\n"

    price = _estimate_price(bant)
    timeline = _estimate_timeline(bant)

    proposal_text = template.format(
        name=name, business=business,
        case_section=case_section, price=price, timeline=timeline,
    )

    record = {
        "lead_id": lead_id, "client_name": name, "niche": niche,
        "bant_data": bant, "proposal_content": proposal_text,
        "template_used": niche, "status": "generated",
    }
    ins_res = await asyncio.to_thread(
        lambda: supabase.table("proposal_history").insert(record).execute()
    )
    proposal_id = (ins_res.data or [{}])[0].get("id")

    await _notify_friday_preview(proposal_id, name, niche, proposal_text)

    return {
        "proposal_id": proposal_id, "lead_id": lead_id, "niche": niche,
        "content": proposal_text, "status": "generated",
        "message": "Proposta gerada. Friday notificou Mauro para aprovacao.",
    }


async def approve_proposal(proposal_id: str, edited_content: str = None) -> dict:
    # BUG-6 fix: check proposal exists before updating
    check = await asyncio.to_thread(
        lambda: supabase.table("proposal_history").select("id").eq("id", proposal_id).maybe_single().execute()
    )
    if not (check.data if check and hasattr(check, "data") else check):
        return {"error": "Proposal not found"}

    update = {"status": "approved", "approved_at": datetime.now(timezone.utc).isoformat()}
    if edited_content:
        update["edited_content"] = edited_content
        update["status"] = "edited"
    await asyncio.to_thread(
        lambda: supabase.table("proposal_history").update(update).eq("id", proposal_id).execute()
    )
    return {"proposal_id": proposal_id, "status": update["status"]}


async def send_proposal(proposal_id: str, via: str = "whatsapp") -> dict:
    res = await asyncio.to_thread(
        lambda: supabase.table("proposal_history")
        .select("*")
        .eq("id", proposal_id)
        .maybe_single()
        .execute()
    )
    proposal = res.data if res and hasattr(res, "data") else res
    if not proposal:
        return {"error": "Proposal not found"}

    if proposal.get("status") not in ("approved", "edited"):
        return {"error": "Proposal must be approved before sending"}

    content = proposal.get("edited_content") or proposal.get("proposal_content", "")

    # Get lead phone
    lead_id = proposal.get("lead_id")
    phone = None
    if lead_id:
        lr = await asyncio.to_thread(
            lambda: supabase.table("leads").select("phone").eq("id", lead_id).maybe_single().execute()
        )
        ld = lr.data if lr and hasattr(lr, "data") else lr
        phone = ld.get("phone") if ld else None

    if via == "whatsapp" and phone:
        try:
            from runtime.integrations.zapi import send_text
            await asyncio.to_thread(send_text, phone, content)
        except Exception as e:
            logger.error("[proposals] Z-API send failed: %s", e)
            return {"error": f"Send failed: {e}"}

    await asyncio.to_thread(
        lambda: supabase.table("proposal_history")
        .update({"status": "sent", "sent_via": via, "sent_at": datetime.now(timezone.utc).isoformat()})
        .eq("id", proposal_id).execute()
    )
    return {"proposal_id": proposal_id, "status": "sent", "via": via}


async def _notify_friday_preview(proposal_id, client_name, niche, content):
    try:
        preview = content[:300] + "..." if len(content) > 300 else content
        await asyncio.to_thread(
            lambda: supabase.table("runtime_tasks").insert({
                "agent_id": "friday",
                "client_id": getattr(settings, "sparkle_internal_client_id", None),
                "task_type": "friday_alert",
                "payload": {
                    "alert": "proposal_preview", "proposal_id": proposal_id,
                    "client_name": client_name, "niche": niche, "preview": preview,
                    "message": f"Proposta gerada para {client_name} (nicho: {niche}). Aprovar, editar ou rejeitar?",
                },
                "status": "pending", "priority": 7,
            }).execute()
        )
    except Exception as e:
        logger.error("[proposals] friday notify failed: %s", e)


async def list_proposals(status: str = None, niche: str = None, limit: int = 50) -> list[dict]:
    q = supabase.table("proposal_history").select("*").order("created_at", desc=True)
    if status:
        q = q.eq("status", status)
    if niche:
        q = q.eq("niche", niche)
    res = await asyncio.to_thread(lambda: q.limit(limit).execute())
    return res.data or []
