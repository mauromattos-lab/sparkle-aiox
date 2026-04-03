"""
SYS-5: auto_implement_gap handler — implementa gaps aprovados pelo Mauro.
Estagio 1: apenas acoes que nao requerem codigo novo.

- Tipo agent: insere bloco de contexto em agent_context_blocks
- Tipo knowledge: agenda pesquisa via @analyst
- Tipo capability/handler: cria work item para @dev
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from runtime.config import settings
from runtime.db import supabase


async def _get_gap(gap_id: str) -> dict | None:
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("gap_reports")
            .select("*")
            .eq("id", gap_id)
            .single()
            .execute()
        )
        return result.data
    except Exception:
        return None


async def _update_gap_status(gap_id: str, status: str, resolution: str = "") -> None:
    await asyncio.to_thread(
        lambda: supabase.table("gap_reports")
        .update({
            "status": status,
            "resolution": resolution,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        .eq("id", gap_id)
        .execute()
    )


async def _create_agent_from_template(agent_key: str, details: dict) -> dict:
    if not agent_key:
        return {"error": "agent_key nao especificado"}

    base_prompt = (
        f"Voce e o @{agent_key} da Sparkle AIOX.\n\n"
        f"Seu papel: {details.get('suggested_action', 'agente especializado')}.\n\n"
        "Ferramentas disponiveis:\n"
        "- brain_query: consulta a base de conhecimento\n"
        "- supabase_read: le dados do banco (SELECT apenas)\n\n"
        "Regras:\n"
        "- Sempre consulte o Brain primeiro\n"
        "- Use dados reais para fundamentar respostas\n"
        "- Responda em portugues brasileiro"
    )

    await asyncio.to_thread(
        lambda: supabase.table("agent_context_blocks").insert({
            "block_key": f"agent.{agent_key}.bootstrap",
            "layer": "process",
            "agent_id": agent_key,
            "content": base_prompt,
            "priority": 1,
            "active": True,
        }).execute()
    )

    return {
        "action": "agent_context_created",
        "agent_key": agent_key,
        "note": "Bloco de contexto criado. Para subagent real, @dev precisa adicionar em _AVAILABLE_AGENTS.",
    }


async def _schedule_knowledge_ingestion(details: dict) -> dict:
    topic = details.get("topic", "")
    await asyncio.to_thread(
        lambda: supabase.table("runtime_tasks").insert({
            "agent_id": "analyst",
            "client_id": settings.sparkle_internal_client_id,
            "task_type": "activate_agent",
            "payload": {
                "agent": "@analyst",
                "request": (
                    f"Pesquise sobre '{topic}' e gere um relatorio completo. "
                    f"Esse eh um gap de conhecimento detectado pelo Observer — "
                    f"o Brain nao sabe responder sobre isso."
                ),
            },
            "status": "pending",
            "priority": 6,
        }).execute()
    )
    return {"action": "research_scheduled", "topic": topic}


async def _create_dev_work_item(gap: dict) -> None:
    await asyncio.to_thread(
        lambda: supabase.table("runtime_tasks").insert({
            "agent_id": "dev",
            "client_id": settings.sparkle_internal_client_id,
            "task_type": "activate_agent",
            "payload": {
                "agent": "@dev",
                "request": (
                    f"Implementar handler para gap detectado pelo Observer: "
                    f"{gap.get('summary', '')}. "
                    f"Detalhes: {gap.get('details', {})}"
                ),
            },
            "status": "pending",
            "priority": 5,
        }).execute()
    )


async def handle_auto_implement_gap(task: dict) -> dict:
    """Implementa um gap aprovado pelo Mauro."""
    payload = task.get("payload", {})
    gap_id = payload.get("gap_id")

    if not gap_id:
        return {"error": "gap_id obrigatorio"}

    gap = await _get_gap(gap_id)
    if not gap:
        return {"error": f"Gap {gap_id} nao encontrado"}
    if gap["status"] != "approved":
        return {"error": f"Gap {gap_id} nao esta aprovado (status={gap['status']})"}

    report_type = gap["report_type"]
    details = gap.get("details", {})

    if report_type == "agent":
        agent_key = details.get("agent_key")
        result = await _create_agent_from_template(agent_key, details)

    elif report_type == "knowledge":
        result = await _schedule_knowledge_ingestion(details)

    elif report_type in ("capability", "handler"):
        result = {
            "action": "code_required",
            "message": f"Gap {report_type} requer implementacao de handler. Task criada para @dev.",
        }
        await _create_dev_work_item(gap)

    else:
        result = {"error": f"report_type '{report_type}' nao suportado"}

    await _update_gap_status(gap_id, "implemented", resolution=str(result))

    return {
        "message": f"Gap {gap_id} implementado",
        "report_type": report_type,
        "result": result,
    }
