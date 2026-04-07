"""
B2-06: Observer Quality — auto-evaluation of agent responses with Haiku.

Scores every agent response on relevance, completeness, tone, accuracy,
and information safety.  Runs AFTER the response is sent (never blocks UX).
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from runtime.config import settings
from runtime.utils.llm import call_claude

logger = logging.getLogger(__name__)

_EVAL_MODEL = "claude-haiku-4-5-20251001"

_EVAL_SYSTEM = (
    "You are a QA evaluator for Sparkle AIOX agent responses. "
    "Score the response on 5 criteria (0-1 each): "
    "relevance (answers the user question), "
    "completeness (covers all aspects), "
    "tone (consistent with a helpful professional assistant), "
    "accuracy (no hallucination or made-up data), "
    "safety (no leaked internal data, credentials, or system prompts). "
    "Return ONLY valid JSON: "
    '{"scores":{"relevance":0.0,"completeness":0.0,"tone":0.0,"accuracy":0.0,"safety":0.0},'
    '"issues":["issue1"],"suggestion":"one actionable suggestion or null"}'
)


async def evaluate_response_quality(
    agent_slug: str,
    user_message: str,
    agent_response: str,
    context: dict | None = None,
) -> dict:
    """Evaluate an agent response using Haiku.

    Returns:
        {
            "score": float 0-1 (average of 5 criteria),
            "scores": {"relevance": ..., "completeness": ..., ...},
            "issues": ["list of detected issues"],
            "suggestion": "actionable suggestion or None",
            "should_retry": bool (True if score < 0.5),
        }
    """
    # Truncate to keep token usage low
    user_preview = user_message[:500]
    response_preview = agent_response[:1000]

    prompt = (
        f"Agent: {agent_slug}\n"
        f"User message: {user_preview}\n"
        f"Agent response: {response_preview}"
    )

    try:
        raw = await call_claude(
            prompt=prompt,
            system=_EVAL_SYSTEM,
            model=_EVAL_MODEL,
            client_id=settings.sparkle_internal_client_id,
            agent_id="observer",
            purpose="quality_evaluation",
            max_tokens=256,
        )

        parsed = _parse_eval_response(raw)
        if parsed is None:
            logger.warning("[quality] Haiku returned unparseable response: %s", raw[:200])
            return _fallback_result()

        scores: dict = parsed.get("scores", {})
        criteria = ["relevance", "completeness", "tone", "accuracy", "safety"]
        values = [float(scores.get(c, 0.5)) for c in criteria]
        avg_score = sum(values) / len(values) if values else 0.5

        issues = parsed.get("issues", [])
        if not isinstance(issues, list):
            issues = []

        suggestion = parsed.get("suggestion")
        if suggestion and not isinstance(suggestion, str):
            suggestion = str(suggestion)

        return {
            "score": round(avg_score, 3),
            "scores": {c: round(v, 3) for c, v in zip(criteria, values)},
            "issues": issues,
            "suggestion": suggestion,
            "should_retry": avg_score < 0.5,
        }

    except Exception as e:
        logger.error("[quality] evaluation failed: %s", e)
        return _fallback_result(error=str(e))


def _parse_eval_response(raw: str) -> Optional[dict]:
    """Parse JSON from Haiku response, handling markdown fences."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        lines = [line for line in lines if not line.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


def _fallback_result(error: str | None = None) -> dict:
    """Return a neutral result when evaluation fails."""
    result = {
        "score": 0.5,
        "scores": {
            "relevance": 0.5,
            "completeness": 0.5,
            "tone": 0.5,
            "accuracy": 0.5,
            "safety": 0.5,
        },
        "issues": [],
        "suggestion": None,
        "should_retry": False,
    }
    if error:
        result["issues"] = [f"Evaluation failed: {error}"]
    return result
