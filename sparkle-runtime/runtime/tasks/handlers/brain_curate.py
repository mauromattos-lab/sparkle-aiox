"""
brain_curate handler — Auto-curation of brain_chunks using Haiku.

Scheduled 3x/day at 02:00, 10:00, 18:00 UTC. Processes pending chunks in
batches of 50, evaluating each with claude-haiku-4-5-20251001 on a 0-1
quality scale:

  score > 0.7   → curation_status = 'approved'
  score 0.4-0.7 → curation_status = 'review'   (human queue)
  score < 0.4   → curation_status = 'rejected'

Chunks without an embedding receive one before curation (never approved
without embedding). Up to 5 chunks are evaluated in parallel per batch via
asyncio.Semaphore(5).

Returns summary: {approved, review, rejected, remaining, errors}
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

import anthropic

from runtime.brain.embedding import get_embedding
from runtime.config import settings
from runtime.db import supabase

logger = logging.getLogger(__name__)

BATCH_SIZE = 50
_SEMAPHORE = asyncio.Semaphore(5)

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
            model="claude-haiku-4-5-20251001",
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

    Processes up to BATCH_SIZE=50 chunks per run (oldest first), with up to
    5 chunks evaluated in parallel via asyncio.Semaphore(5).
    Chunks missing an embedding receive one before evaluation; chunks that
    score 'approved' but have no embedding are demoted to 'review'.
    Updates curation_status + confidence_score + curation_note on each chunk.
    Returns summary dict with counts and remaining pending.
    """

    # Fetch batch of pending chunks (oldest first to drain backlog in order)
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("brain_chunks")
            .select("id,raw_content,canonical_content,insight_narrative,source_title,source_type,embedding")
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

    logger.info("[brain_curate] evaluating %d chunks with Haiku (parallel=5)", len(chunks))

    now = datetime.now(timezone.utc).isoformat()

    # Counters shared across coroutines — use a mutable container
    counters = {"approved": 0, "review": 0, "rejected": 0, "errors": 0}

    async def _process_chunk(chunk: dict) -> None:
        async with _SEMAPHORE:
            chunk_id = chunk["id"]
            content = (
                chunk.get("canonical_content")
                or chunk.get("raw_content")
                or chunk.get("insight_narrative")
                or ""
            ).strip()

            if not content:
                # Empty chunk — reject immediately without any API call
                new_status = "rejected"
                score = 0.0
                reason = "empty content"
                embedding = None
            else:
                # Generate embedding if chunk doesn't have one yet
                has_embedding = bool(chunk.get("embedding"))
                if not has_embedding:
                    embedding = await get_embedding(content)
                    if embedding:
                        logger.debug("[brain_curate] chunk=%s — embedding generated", chunk_id)
                    else:
                        logger.debug("[brain_curate] chunk=%s — embedding unavailable (no OPENAI_API_KEY or error)", chunk_id)
                else:
                    embedding = None  # already present — don't overwrite

                score, reason = await _evaluate_chunk(content)
                new_status = _score_to_status(score)

                # Ensure approved chunks always have an embedding; demote to review if missing
                if new_status == "approved" and not has_embedding and embedding is None:
                    new_status = "review"
                    reason = f"{reason} | demoted: no embedding"
                    logger.debug("[brain_curate] chunk=%s demoted approved→review (no embedding)", chunk_id)

            try:
                update_payload: dict = {
                    "curation_status": new_status,
                    "confidence_score": round(score, 3),
                    "curation_note": f"[auto] {reason}",
                    "curated_at": now,
                }
                if embedding is not None:
                    update_payload["embedding"] = embedding

                await asyncio.to_thread(
                    lambda cid=chunk_id, p=update_payload: supabase.table("brain_chunks")
                    .update(p)
                    .eq("id", cid)
                    .execute()
                )

                counters[new_status] = counters.get(new_status, 0) + 1

                logger.debug(
                    "[brain_curate] chunk=%s score=%.2f → %s (%s)",
                    chunk_id, score, new_status, reason,
                )

            except Exception as e:
                logger.warning("[brain_curate] failed to update chunk %s: %s", chunk_id, e)
                counters["errors"] += 1

    results = await asyncio.gather(*[_process_chunk(c) for c in chunks], return_exceptions=True)
    for r in results:
        if isinstance(r, Exception):
            counters["errors"] += 1
            logger.warning("[brain_curate] chunk error: %s", r)

    approved = counters["approved"]
    review = counters["review"]
    rejected = counters["rejected"]
    errors = counters["errors"]

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
