"""
Agents router — S3-03.

POST /agent/invoke
  Stateless endpoint for invoking any registered Sparkle agent by agent_id.
  Intended for programmatic callers: n8n, portal, other agents.
  NOT a replacement for /friday — that router handles Mauro's personal interface.

GET /agent/list
  Returns all active agents from the database.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from runtime.agents.handler import invoke_agent
from runtime.agents.loader import list_active_agents
from runtime.agents.routing import get_taxonomy_summary, resolve_agent, get_agent_capabilities

router = APIRouter()


# ── Request / Response models ──────────────────────────────

class AgentInvokeRequest(BaseModel):
    agent_id: str
    message: str
    context: dict = {}


class AgentInvokeResponse(BaseModel):
    response: str
    agent_id: str
    model: str


# ── Endpoint ───────────────────────────────────────────────

@router.post("/invoke", response_model=AgentInvokeResponse)
async def invoke(req: AgentInvokeRequest) -> AgentInvokeResponse:
    """
    Invoke a Sparkle agent by agent_id.

    - **agent_id**: PK in the `agents` table (e.g. "zenya-ensinaja").
    - **message**: The user message to process.
    - **context**: Optional metadata dict (from_number, client_id, …).

    Returns the agent's response plus the agent_id and model used.
    Raises 404 if agent_id is not found or inactive.
    Raises 500 on invocation failure.
    """
    result = await invoke_agent(
        agent_id=req.agent_id,
        message=req.message,
        context=req.context,
    )
    return AgentInvokeResponse(**result)


@router.get("/list")
async def list_agents() -> dict[str, Any]:
    """
    List all active agents from the database.

    Returns a dict with:
    - **agents**: list of active agent records (slug, display_name, agent_type, model, skills, etc.)
    - **count**: total number of active agents
    """
    agents = await list_active_agents()
    return {
        "agents": agents,
        "count": len(agents),
    }


# ── Taxonomy endpoints (B2-01) ───────────────────────────────

@router.get("/types")
async def agent_types() -> dict[str, Any]:
    """
    Return the agent taxonomy summary.

    Returns:
    - **types**: list of agent type strings
    - **counts**: dict mapping type -> count
    - **agents_by_type**: dict mapping type -> list of agents
    - **total**: total active agents
    """
    return await get_taxonomy_summary()


class ResolveRequest(BaseModel):
    intent: str
    context: dict = {}


@router.post("/resolve")
async def resolve(req: ResolveRequest) -> dict[str, Any]:
    """
    Resolve the best agent for a given intent and context.

    - **intent**: The intent to resolve (e.g. "deploy", "customer_chat").
    - **context**: Optional dict with channel, agent_type filter, etc.

    Returns the matched agent record, or 404 if none found.
    """
    agent = await resolve_agent(intent=req.intent, context=req.context)
    if not agent:
        raise HTTPException(status_code=404, detail=f"No agent found for intent '{req.intent}'")
    return {"agent": agent}


@router.get("/capabilities/{slug}")
async def capabilities(slug: str) -> dict[str, Any]:
    """
    Get the capabilities list for an agent by slug.

    Returns:
    - **slug**: the agent slug
    - **capabilities**: list of capability strings
    """
    caps = await get_agent_capabilities(slug)
    return {"slug": slug, "capabilities": caps}
