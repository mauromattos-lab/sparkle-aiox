"""
LLM wrapper — the ONLY place in the codebase that calls Claude API.
Every call logs estimated cost to Supabase.
Nothing calls anthropic.Client directly outside this module.
"""
from __future__ import annotations

import time
from typing import Optional

import anthropic

from runtime.config import settings
from runtime.db import supabase

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

# Pricing per 1M tokens (USD) — update when Anthropic changes pricing
_PRICING: dict[str, dict[str, float]] = {
    "claude-haiku-4-5-20251001":       {"input": 0.25,  "output": 1.25},
    "claude-3-5-haiku-20241022":   {"input": 0.80,  "output": 4.00},
    "claude-sonnet-4-5":           {"input": 3.00,  "output": 15.00},
    "claude-sonnet-4-6":           {"input": 3.00,  "output": 15.00},
    "claude-opus-4-5":             {"input": 15.00, "output": 75.00},
}

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = _PRICING.get(model, {"input": 3.00, "output": 15.00})
    return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000


def call_claude(
    prompt: str,
    *,
    system: str = "",
    model: str = _DEFAULT_MODEL,
    client_id: str = "sparkle-internal",
    task_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    purpose: Optional[str] = None,
    max_tokens: int = 1024,
) -> str:
    """
    Call Claude and log cost to llm_cost_log.

    Returns the text content of the first message block.
    Raises on API error (let the caller handle / mark task as failed).
    """
    messages = [{"role": "user", "content": prompt}]
    kwargs: dict = {"model": model, "max_tokens": max_tokens, "messages": messages}
    if system:
        kwargs["system"] = system

    response = _client.messages.create(**kwargs)

    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    cost = _estimate_cost(model, input_tokens, output_tokens)

    _log_cost(
        client_id=client_id,
        task_id=task_id,
        agent_id=agent_id,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost,
        purpose=purpose,
    )

    return response.content[0].text


def _log_cost(
    client_id: str,
    task_id: Optional[str],
    agent_id: Optional[str],
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    purpose: Optional[str],
) -> None:
    try:
        supabase.table("llm_cost_log").insert({
            "client_id": client_id,
            "task_id": task_id,
            "agent_id": agent_id,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": float(cost_usd),
            "purpose": purpose,
        }).execute()
    except Exception as e:
        # Never let cost logging crash the main flow
        print(f"[llm] cost log failed: {e}")
