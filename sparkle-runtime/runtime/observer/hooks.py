"""
B2-06: Observer Hooks — post-response quality evaluation (non-blocking).

Usage:
    import asyncio
    from runtime.observer.hooks import post_response_hook

    # Fire-and-forget after sending the response to the user
    asyncio.create_task(post_response_hook(agent_slug, user_msg, response, context))
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from runtime.config import settings
from runtime.db import supabase
from runtime.observer.quality import evaluate_response_quality

logger = logging.getLogger(__name__)

_QUALITY_GAP_THRESHOLD = 0.3  # Below this, create a system gap


async def post_response_hook(
    agent_slug: str,
    user_msg: str,
    response: str,
    context: dict | None = None,
) -> None:
    """Run quality evaluation in background after an agent responds.

    - Evaluates with Haiku
    - Saves result to response_quality_log
    - If score < 0.3, creates a gap_report with type 'quality'
    """
    try:
        result = await evaluate_response_quality(
            agent_slug=agent_slug,
            user_message=user_msg,
            agent_response=response,
            context=context,
        )

        # Save to quality log
        await _save_quality_log(agent_slug, user_msg, response, result)

        # If critically bad, create a gap
        if result["score"] < _QUALITY_GAP_THRESHOLD:
            await _create_quality_gap(agent_slug, user_msg, response, result)

        logger.info(
            "[quality] %s score=%.2f issues=%d",
            agent_slug,
            result["score"],
            len(result.get("issues", [])),
        )

    except Exception as e:
        # Never let quality evaluation crash anything
        logger.error("[quality] post_response_hook failed: %s", e)


async def _save_quality_log(
    agent_slug: str,
    user_msg: str,
    response: str,
    result: dict,
) -> None:
    """Insert evaluation into response_quality_log."""
    try:
        await asyncio.to_thread(
            lambda: supabase.table("response_quality_log").insert({
                "agent_slug": agent_slug,
                "user_message_preview": user_msg[:200],
                "response_preview": response[:200],
                "score": result["score"],
                "issues": result.get("issues", []),
                "scores_detail": result.get("scores"),
                "suggestion": result.get("suggestion"),
            }).execute()
        )
    except Exception as e:
        logger.error("[quality] failed to save log: %s", e)


async def _create_quality_gap(
    agent_slug: str,
    user_msg: str,
    response: str,
    result: dict,
) -> None:
    """Create a gap_report when quality is critically low."""
    try:
        issues_text = "; ".join(result.get("issues", ["low score"]))
        await asyncio.to_thread(
            lambda: supabase.table("gap_reports").insert({
                "report_type": "quality",
                "summary": f"Low quality response from {agent_slug} (score={result['score']:.2f})",
                "severity": "high" if result["score"] < 0.2 else "medium",
                "status": "pending",
                "details": {
                    "agent_slug": agent_slug,
                    "score": result["score"],
                    "scores": result.get("scores"),
                    "issues": result.get("issues", []),
                    "suggestion": result.get("suggestion"),
                    "user_message_preview": user_msg[:200],
                    "response_preview": response[:200],
                },
            }).execute()
        )
        logger.warning(
            "[quality] gap created for %s — score=%.2f: %s",
            agent_slug,
            result["score"],
            issues_text[:100],
        )
    except Exception as e:
        logger.error("[quality] failed to create gap: %s", e)
