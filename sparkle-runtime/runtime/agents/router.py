"""
Agents router — S3-03.

POST /agent/invoke
  Stateless endpoint for invoking any registered Sparkle agent by agent_id.
  Intended for programmatic callers: n8n, portal, other agents.
  NOT a replacement for /friday — that router handles Mauro's personal interface.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from runtime.agents.handler import invoke_agent

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
