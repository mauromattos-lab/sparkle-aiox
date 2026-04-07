"""
Agent invocation handler — S3-03 + S5-02.

Fetches agent configuration from Supabase `agents` table and calls Claude
via call_claude(). Never calls anthropic.Client directly.

Flow:
  1. SELECT agent from Supabase WHERE agent_id=? AND active=true
  2. Extract system_prompt, model, max_tokens, client_id
  3. Optionally enrich system_prompt with context:
     - S5-01: context["system_prompt_override"] replaces the DB system_prompt entirely
     - S5-02: context["phone"] triggers Member State Engine lookup and injects member
              context block at the end of system_prompt
     - from_number: append user phone number to system_prompt
  4. Call call_claude() with purpose="agent_invoke" for cost attribution
  5. Return dict with response, agent_id, model
"""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import HTTPException

from runtime.config import settings
from runtime.db import supabase
from runtime.utils.llm import call_claude


async def invoke_agent(
    agent_id: str,
    message: str,
    context: dict[str, Any],
) -> dict[str, str]:
    """
    Invoke a Sparkle agent by agent_id.

    Args:
        agent_id: PK of the `agents` table (e.g. "zenya-ensinaja").
        message: The user message to process.
        context: Optional dict with extra metadata (from_number, client_id, …).

    Returns:
        dict with keys: response (str), agent_id (str), model (str).

    Raises:
        HTTPException 404 if agent not found or inactive.
        HTTPException 500 on invocation failure.
    """
    # 1. Fetch agent record from Supabase (async-safe via asyncio.to_thread)
    try:
        result = await asyncio.to_thread(
            lambda: supabase
            .table("agents")
            .select("*")
            .eq("agent_id", agent_id)
            .eq("active", True)
            .maybe_single()
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Agent invocation failed: {exc}",
        ) from exc

    agent_record: dict[str, Any] | None = result.data if result else None

    if not agent_record:
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{agent_id}' not found or inactive.",
        )

    # 2. Extract configuration fields with safe defaults
    system_prompt: str = agent_record.get("system_prompt") or ""
    model: str = agent_record.get("model") or "claude-haiku-4-5-20251001"
    max_tokens: int = agent_record.get("max_tokens") or 1024
    client_id: str = (
        agent_record.get("client_id")
        or context.get("client_id")
        or settings.sparkle_internal_client_id
    )

    # 2b. system_prompt_override — used by character_handler to inject soul_prompt.
    # When provided, replaces the agent's DB system_prompt entirely.
    # This allows a generic "character-runner" agent to be reused by any character
    # without modifying the agents table.
    if context.get("system_prompt_override"):
        system_prompt = context["system_prompt_override"]

    # 3a. S5-02 — inject Member State Engine context if phone is in context
    phone: str = context.get("phone", "")
    if phone:
        try:
            from runtime.members.handler import get_member_context_for_agent
            member_context = await get_member_context_for_agent(phone)
            if member_context:
                system_prompt = f"{system_prompt}\n\n{member_context}" if system_prompt else member_context
        except Exception as _member_exc:
            # Member context is best-effort — never block agent invocation
            print(f"[agent/handler] member context fetch failed for {phone}: {_member_exc}")

    # 3b. Enrich system_prompt with context if from_number is present
    from_number: str = context.get("from_number", "")
    if from_number and system_prompt:
        system_prompt = f"{system_prompt}\n\nNúmero do usuário: {from_number}"
    elif from_number:
        system_prompt = f"Número do usuário: {from_number}"

    # 4. Call Claude via the shared LLM wrapper — never call anthropic directly
    try:
        response_text = await call_claude(
            prompt=message,
            system=system_prompt,
            model=model,
            max_tokens=max_tokens,
            client_id=client_id,
            agent_id=agent_id,
            purpose="agent_invoke",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Agent invocation failed: {exc}",
        ) from exc

    # 5. Return structured response
    return {
        "response": response_text,
        "agent_id": agent_id,
        "model": model,
    }
