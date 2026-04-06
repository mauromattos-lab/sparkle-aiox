"""
Handler: pipeline_query

Friday responde perguntas de Mauro sobre o pipeline comercial.
Detecta intent de consulta, chama GET /cockpit/pipeline e formata
a resposta para WhatsApp.

Perguntas reconhecidas:
  - leads aguardando proposta     → status in (proposta_enviada, demo_feita)
  - follow-up para hoje           → followups_vencidos
  - quantos leads qualificados    → status = qualificado
  - quem fechou recentemente      → closed_at últimos 30 dias
  - pipeline completo / visão     → todos os estágios
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from runtime.config import settings
from runtime.db import supabase

logger = logging.getLogger(__name__)

# Stage display labels
_STAGE_LABELS: dict[str, str] = {
    "novo": "Novo",
    "qualificado": "Qualificado",
    "demo_agendada": "Demo Agendada",
    "demo_feita": "Demo Feita",
    "proposta_enviada": "Proposta Enviada",
    "fechado": "Fechado",
    "perdido": "Perdido",
    "respondeu": "Respondeu",
}


async def _fetch_pipeline() -> dict:
    """Busca dados do pipeline: view agrupada + followups vencidos."""
    today = datetime.now(timezone.utc).date().isoformat()

    pipeline_res, overdue_res = await asyncio.gather(
        asyncio.to_thread(
            lambda: supabase.table("pipeline_view")
            .select("*")
            .execute()
        ),
        asyncio.to_thread(
            lambda: supabase.table("leads")
            .select("name, phone, business_type, next_followup_at, status")
            .lte("next_followup_at", today)
            .not_.in_("status", ["fechado", "perdido"])
            .execute()
        ),
    )
    return {
        "pipeline": pipeline_res.data or [],
        "followups_vencidos": overdue_res.data or [],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _stage_block(stage_data: dict) -> str:
    """Formata um bloco de estágio para WhatsApp."""
    stage = stage_data.get("stage", "?")
    total = stage_data.get("total", 0)
    leads = stage_data.get("leads") or []
    label = _STAGE_LABELS.get(stage, stage.replace("_", " ").title())

    lines = [f"*{label}* ({total})"]
    for lead in leads[:5]:  # max 5 por estágio para não lotar o chat
        name = lead.get("name") or "Sem nome"
        btype = lead.get("business_type") or ""
        days = lead.get("days_in_stage")
        val = lead.get("proposal_value")
        followup = lead.get("next_followup_at")

        detail_parts = []
        if btype:
            detail_parts.append(btype)
        if days is not None:
            detail_parts.append(f"{days}d no estágio")
        if val:
            detail_parts.append(f"R${val:.0f}/mês" if isinstance(val, (int, float)) else f"R${val}")
        if followup:
            followup_date = followup[:10] if isinstance(followup, str) else str(followup)
            detail_parts.append(f"followup {followup_date}")

        detail = " · ".join(detail_parts)
        lines.append(f"  • {name}" + (f" ({detail})" if detail else ""))

    if len(leads) > 5:
        lines.append(f"  … e mais {len(leads) - 5}")
    return "\n".join(lines)


def _format_full_pipeline(data: dict) -> str:
    """Formata visão completa do pipeline."""
    pipeline = data.get("pipeline") or []
    overdue = data.get("followups_vencidos") or []

    if not pipeline:
        return "Nenhum lead no pipeline ainda."

    # Ordenar por estágio lógico
    stage_order = ["novo", "qualificado", "demo_agendada", "demo_feita",
                   "proposta_enviada", "respondeu", "fechado", "perdido"]
    pipeline_sorted = sorted(
        pipeline,
        key=lambda s: stage_order.index(s.get("stage", "")) if s.get("stage", "") in stage_order else 99
    )

    blocks = [_stage_block(s) for s in pipeline_sorted]
    msg = "Pipeline Comercial\n\n" + "\n\n".join(blocks)

    if overdue:
        names = [l.get("name") or "Sem nome" for l in overdue[:5]]
        msg += f"\n\n*Follow-ups vencidos hoje ({len(overdue)}):*\n"
        msg += "\n".join(f"  • {n}" for n in names)
        if len(overdue) > 5:
            msg += f"\n  … e mais {len(overdue) - 5}"

    return msg


def _format_proposals(pipeline: list[dict]) -> str:
    """Leads aguardando proposta: proposta_enviada e demo_feita."""
    target_stages = {"proposta_enviada", "demo_feita"}
    leads = []
    for s in pipeline:
        if s.get("stage") in target_stages:
            leads.extend(s.get("leads") or [])

    if not leads:
        return "Nenhum lead aguardando proposta no momento."

    label = _STAGE_LABELS
    lines = [f"*Leads aguardando proposta ({len(leads)}):*"]
    for lead in leads[:10]:
        name = lead.get("name") or "Sem nome"
        stage = lead.get("stage", "")
        days = lead.get("days_in_stage")
        val = lead.get("proposal_value")
        parts = []
        if days is not None:
            parts.append(f"{days}d aguardando")
        if val:
            parts.append(f"R${val:.0f}/mês" if isinstance(val, (int, float)) else f"R${val}")
        detail = " · ".join(parts)
        lines.append(f"  • {name}" + (f" ({detail})" if detail else ""))
    return "\n".join(lines)


def _format_followups(overdue: list[dict]) -> str:
    """Follow-ups vencidos hoje."""
    if not overdue:
        return "Nenhum follow-up vencido hoje. Tá em dia!"

    lines = [f"*Follow-ups para fazer hoje ({len(overdue)}):*"]
    for lead in overdue[:10]:
        name = lead.get("name") or "Sem nome"
        btype = lead.get("business_type") or ""
        status = lead.get("status") or ""
        followup = (lead.get("next_followup_at") or "")[:10]
        detail_parts = []
        if btype:
            detail_parts.append(btype)
        if status:
            detail_parts.append(_STAGE_LABELS.get(status, status))
        if followup:
            detail_parts.append(f"venceu {followup}")
        detail = " · ".join(detail_parts)
        lines.append(f"  • {name}" + (f" ({detail})" if detail else ""))
    if len(overdue) > 10:
        lines.append(f"  … e mais {len(overdue) - 10}")
    return "\n".join(lines)


def _format_qualified(pipeline: list[dict]) -> str:
    """Leads qualificados."""
    for s in pipeline:
        if s.get("stage") == "qualificado":
            total = s.get("total", 0)
            leads = s.get("leads") or []
            if total == 0:
                return "Nenhum lead qualificado no momento."
            lines = [f"*Leads qualificados ({total}):*"]
            for lead in leads[:8]:
                name = lead.get("name") or "Sem nome"
                btype = lead.get("business_type") or ""
                days = lead.get("days_in_stage")
                parts = []
                if btype:
                    parts.append(btype)
                if days is not None:
                    parts.append(f"{days}d no estágio")
                detail = " · ".join(parts)
                lines.append(f"  • {name}" + (f" ({detail})" if detail else ""))
            if len(leads) > 8:
                lines.append(f"  … e mais {len(leads) - 8}")
            return "\n".join(lines)
    return "Nenhum lead qualificado no momento."


async def _format_closed_recently(days: int = 30) -> str:
    """Quem fechou nos últimos N dias."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    try:
        res = await asyncio.to_thread(
            lambda: supabase.table("leads")
            .select("name, phone, business_type, proposal_value, closed_at")
            .eq("status", "fechado")
            .gte("closed_at", cutoff)
            .order("closed_at", desc=True)
            .execute()
        )
        leads = res.data or []
    except Exception as e:
        logger.error("[pipeline_query] _format_closed_recently error: %s", e)
        leads = []

    if not leads:
        return f"Nenhum lead fechado nos últimos {days} dias."

    lines = [f"*Fechamentos nos últimos {days} dias ({len(leads)}):*"]
    for lead in leads:
        name = lead.get("name") or "Sem nome"
        val = lead.get("proposal_value")
        closed = (lead.get("closed_at") or "")[:10]
        parts = []
        if val:
            parts.append(f"R${val:.0f}/mês" if isinstance(val, (int, float)) else f"R${val}")
        if closed:
            parts.append(f"fechou {closed}")
        detail = " · ".join(parts)
        lines.append(f"  • {name}" + (f" ({detail})" if detail else ""))
    return "\n".join(lines)


def _detect_pipeline_query_type(text: str) -> str | None:
    """
    Detecta o tipo de consulta de pipeline no texto.
    Retorna chave do tipo ou None se não for query de pipeline.
    """
    t = text.lower().strip()

    # Visão completa
    if any(kw in t for kw in [
        "pipeline completo", "visão do pipeline", "visao do pipeline",
        "todo o pipeline", "pipeline inteiro", "me mostra o pipeline",
        "como está o pipeline", "como ta o pipeline", "pipeline atual",
        "status do pipeline", "overview do pipeline",
    ]):
        return "full"

    # Propostas aguardando
    if any(kw in t for kw in [
        "aguardando proposta", "leads com proposta", "proposta enviada",
        "quem recebeu proposta", "demo feita", "aguardam proposta",
        "esperando proposta", "mandei proposta",
    ]):
        return "proposals"

    # Follow-ups de hoje
    if any(kw in t for kw in [
        "follow-up", "followup", "follow up",
        "acompanhamento", "ligar hoje", "contato hoje",
        "quem contactar", "quem ligar", "to-do comercial",
        "todo comercial", "pra contatar", "pra ligar",
    ]):
        return "followups"

    # Qualificados
    if any(kw in t for kw in [
        "leads qualificados", "quantos qualificados", "quem está qualificado",
        "quem ta qualificado", "qualificados no pipeline",
    ]):
        return "qualified"

    # Fechamentos
    if any(kw in t for kw in [
        "fechou recentemente", "fechamentos recentes", "quem fechou",
        "novos clientes", "conversões recentes", "deals fechados",
    ]):
        return "closed"

    return None


async def handle_pipeline_query(task: dict) -> dict:
    """
    Handler principal: classifica a query e retorna resposta formatada.
    """
    payload = task.get("payload") or {}
    text = payload.get("original_text") or payload.get("query") or ""
    query_type = payload.get("pipeline_query_type") or _detect_pipeline_query_type(text)

    if not query_type:
        query_type = "full"

    try:
        data = await _fetch_pipeline()
        pipeline = data["pipeline"]
        overdue = data["followups_vencidos"]

        if query_type == "full":
            message = _format_full_pipeline(data)
        elif query_type == "proposals":
            message = _format_proposals(pipeline)
        elif query_type == "followups":
            message = _format_followups(overdue)
        elif query_type == "qualified":
            message = _format_qualified(pipeline)
        elif query_type == "closed":
            message = await _format_closed_recently(days=30)
        else:
            message = _format_full_pipeline(data)

    except Exception as e:
        logger.error("[pipeline_query] handler error: %s", e)
        message = f"Erro ao consultar o pipeline: {e}"

    return {"message": message, "query_type": query_type}
