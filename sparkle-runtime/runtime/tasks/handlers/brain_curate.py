"""
brain_curate handler — Auto-curation of brain_chunks using Haiku.

Scheduled daily at 02:00 UTC. Processes pending chunks in batches of 20,
evaluating each with claude-3-5-haiku-20241022 on a 0-1 quality scale:

  score > 0.7   → curation_status = 'approved'
  score 0.4-0.7 → curation_status = 'review'   (human queue)
  score < 0.4   → curation_status = 'rejected'

Returns summary: {approved, review, rejected, remaining, errors}
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

import anthropic

from runtime.config import settings
from runtime.db import supabase

logger = logging.getLogger(__name__)

BATCH_SIZE = 20

_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

_EVAL_SYSTEM = (
    "You are a knowledge quality evaluator for the Sparkle AIOX Brain — "
    "a knowledge base used by AI agents to answer business questions for "
    "a digital marketing agency operating in Brazil.\n\n"
    "Your job: evaluate a knowledge chunk and return a JSON object with:\n"
    "  - score: float 0.0 to 1.0\n"
    "  - reason: one-line explanation (max 80 chars, in English)\n\n"
    "Scoring rubric:\n"
    "  1.0 — Highly actionable, specific, factual, clearly useful for business decisions\n"
    "  0.8 — Good quality, specific enough, relevant to marketing/AI/clients\n"
    "  0.6 — Somewhat useful but vague, or lacks enough context to be actionable\n"
    "  0.4 — Minimal value: too generic, too short, or hard to interpret out of context\n"
    "  0.2 — Near useless: noise, repeated filler, or incoherent text\n"
    "  0.0 — Completely useless: empty, corrupt, or irrelevant garbage\n\n"
    "Respond ONLY with valid JSON. No markdown. No extra text.\n"
    'Example: {"score": 0.85, "reason": "Specific client MRR data with actionable context"}'
)


async def _evaluate_chunk(content: str) -> tuple[float, str]:
    """Call Haiku to score a single chunk. Returns (score, reason)."""
    preview = content[:2000]  # cap to keep tokens low
    raw_text = ""
    try:
        resp = await _client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=64,
            system=_EVAL_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": f"Evaluate this knowledge chunk:\n\n{preview}",
                }
            ],
        )
        raw_text = resp.content[0].text.strip()
        parsed = json.loads(raw_text)
        score = float(parsed.get("score", 0.0))
        reason = str(parsed.get("reason", ""))[:120]
        score = max(0.0, min(1.0, score))
        return score, reason
    except json.JSONDecodeError as e:
        logger.warning("[brain_curate] JSON parse error: %s | raw=%r", e, raw_text)
        return 0.5, "parse_error — routed to review"
    except Exception as e:
        logger.warning("[brain_curate] Haiku eval failed: %s", e)
        return 0.5, f"eval_error — {str(e)[:60]}"


def _score_to_status(score: float) -> str:
    if score > 0.7:
        return "approved"
    if score >= 0.4:
        return "review"
    return "rejected"


async def handle_brain_curate(task: dict) -> dict:
    """
    Auto-curate pending brain_chunks using Haiku quality evaluation.

    Processes up to BATCH_SIZE=20 chunks per run (oldest first).
    Updates curation_status + confidence_score + curation_note on each chunk.
    Returns summary dict with counts and remaining pending.
    """
    approved = 0
    review = 0
    rejected = 0
    errors = 0

    # Fetch batch of pending chunks (oldest first to drain backlog in order)
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("brain_chunks")
            .select("id,raw_content,canonical_content,insight_narrative,source_title,source_type")
            .eq("curation_status", "pending")
            .order("created_at", desc=False)
            .limit(BATCH_SIZE)
            .execute()
        )
    except Exception as e:
        logger.error("[brain_curate] failed to fetch pending chunks: %s", e)
        return {
            "message": f"brain_curate: failed to fetch chunks — {str(e)[:200]}",
            "approved": 0,
            "review": 0,
            "rejected": 0,
            "errors": 1,
            "remaining": -1,
        }

    chunks = result.data or []
    if not chunks:
        logger.info("[brain_curate] no pending chunks — nothing to curate")
        return {
            "message": "brain_curate: no pending chunks",
            "approved": 0,
            "review": 0,
            "rejected": 0,
            "errors": 0,
            "remaining": 0,
        }

    logger.info("[brain_curate] evaluating %d chunks with Haiku", len(chunks))

    now = datetime.now(timezone.utc).isoformat()

    for chunk in chunks:
        chunk_id = chunk["id"]
        content = (
            chunk.get("canonical_content")
            or chunk.get("raw_content")
            or chunk.get("insight_narrative")
            or ""
        ).strip()

        if not content:
            # Empty chunk — reject immediately without an API call
            new_status = "rejected"
            score = 0.0
            reason = "empty content"
        else:
            score, reason = await _evaluate_chunk(content)
            new_status = _score_to_status(score)

        try:
            await asyncio.to_thread(
                lambda cid=chunk_id, ns=new_status, s=score, r=reason: supabase.table("brain_chunks")
                .update({
                    "curation_status": ns,
                    "confidence_score": round(s, 3),
                    "curation_note": f"[auto] {r}",
                    "curated_at": now,
                })
                .eq("id", cid)
                .execute()
            )

            if new_status == "approved":
                approved += 1
            elif new_status == "review":
                review += 1
            else:
                rejected += 1

            logger.debug(
                "[brain_curate] chunk=%s score=%.2f → %s (%s)",
                chunk_id, score, new_status, reason,
            )

        except Exception as e:
            logger.warning("[brain_curate] failed to update chunk %s: %s", chunk_id, e)
            errors += 1

    # Count remaining pending chunks after this batch
    try:
        remaining_result = await asyncio.to_thread(
            lambda: supabase.table("brain_chunks")
            .select("id", count="exact")
            .eq("curation_status", "pending")
            .limit(1)
            .execute()
        )
        remaining = remaining_result.count if remaining_result.count is not None else -1
    except Exception:
        remaining = -1

    msg = (
        f"brain_curate: {approved} approved, {review} review, {rejected} rejected "
        f"(batch={len(chunks)}, remaining={remaining}, errors={errors})"
    )
    logger.info("[brain_curate] %s", msg)

    return {
        "message": msg,
        "approved": approved,
        "review": review,
        "rejected": rejected,
        "errors": errors,
        "remaining": remaining,
        "batch_size": len(chunks),
    }
