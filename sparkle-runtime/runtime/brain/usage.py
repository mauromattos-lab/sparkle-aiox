"""
Brain Usage Tracking — B3-05.

Increments usage_count and updates last_used_at on brain_chunks
whenever they are returned in a query result.

Designed to be called fire-and-forget so it does not block query responses.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from runtime.db import supabase

logger = logging.getLogger(__name__)


async def track_chunk_usage(chunk_ids: list[str]) -> None:
    """Increment usage_count and set last_used_at for a list of chunk IDs.

    Runs updates in parallel for all chunks. Errors are logged but not raised
    so that query responses are never blocked by tracking failures.
    """
    if not chunk_ids:
        return

    now_iso = datetime.now(timezone.utc).isoformat()

    async def _update_one(chunk_id: str) -> None:
        try:
            # Fetch current usage_count
            current = await asyncio.to_thread(
                lambda: supabase.table("brain_chunks")
                .select("usage_count")
                .eq("id", chunk_id)
                .single()
                .execute()
            )
            count = (current.data.get("usage_count") or 0) + 1

            await asyncio.to_thread(
                lambda c=count: supabase.table("brain_chunks")
                .update({"usage_count": c, "last_used_at": now_iso})
                .eq("id", chunk_id)
                .execute()
            )
        except Exception as e:
            logger.debug("[brain/usage] failed to track chunk %s: %s", chunk_id, e)

    # Run all updates concurrently
    await asyncio.gather(*[_update_one(cid) for cid in chunk_ids], return_exceptions=True)
