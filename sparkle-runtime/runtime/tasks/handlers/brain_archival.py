"""
brain_archival handler — B3-05: Move expired brain chunks to archive.

Scheduled daily. Finds all brain_chunks where expires_at < now(),
moves them to brain_chunks_archive, then deletes the originals.

Runs in batches to avoid long-running transactions.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from runtime.db import supabase

logger = logging.getLogger(__name__)

BATCH_SIZE = 100


async def handle_brain_archival(task: dict) -> dict:
    """
    Archive expired brain chunks.

    1. SELECT expired chunks (expires_at < now()) in batches
    2. INSERT into brain_chunks_archive
    3. DELETE from brain_chunks
    4. Return summary

    Returns:
        {"message": "...", "archived_count": int}
    """
    total_archived = 0
    errors = 0

    try:
        while True:
            # Fetch a batch of expired chunks
            now_iso = datetime.now(timezone.utc).isoformat()

            result = await asyncio.to_thread(
                lambda: supabase.table("brain_chunks")
                .select("*")
                .lt("expires_at", now_iso)
                .not_.is_("expires_at", "null")
                .limit(BATCH_SIZE)
                .execute()
            )

            expired = result.data or []
            if not expired:
                break

            # Insert each into archive and delete original
            for chunk in expired:
                try:
                    chunk_id = chunk["id"]

                    # Build archive row (copy all fields, add archived_at)
                    archive_row = {
                        "id": chunk_id,
                        "raw_content": chunk.get("raw_content"),
                        "source_type": chunk.get("source_type"),
                        "source_title": chunk.get("source_title"),
                        "pipeline_type": chunk.get("pipeline_type"),
                        "brain_owner": chunk.get("brain_owner"),
                        "client_id": chunk.get("client_id"),
                        "chunk_metadata": chunk.get("chunk_metadata"),
                        "curation_status": chunk.get("curation_status"),
                        "confirmation_count": chunk.get("confirmation_count", 0),
                        "namespace": chunk.get("namespace", "general"),
                        "expires_at": chunk.get("expires_at"),
                        "usage_count": chunk.get("usage_count", 0),
                        "last_used_at": chunk.get("last_used_at"),
                        "created_at": chunk.get("created_at"),
                        "archived_at": now_iso,
                    }

                    # Embedding: only copy if present (vector type needs care)
                    if chunk.get("embedding"):
                        archive_row["embedding"] = chunk["embedding"]

                    # Insert into archive (upsert to be idempotent on re-runs)
                    await asyncio.to_thread(
                        lambda row=archive_row: supabase.table("brain_chunks_archive")
                        .upsert(row, on_conflict="id")
                        .execute()
                    )

                    # Delete from brain_chunks
                    await asyncio.to_thread(
                        lambda cid=chunk_id: supabase.table("brain_chunks")
                        .delete()
                        .eq("id", cid)
                        .execute()
                    )

                    total_archived += 1

                except Exception as e:
                    logger.warning(
                        "[brain/archival] failed to archive chunk %s: %s",
                        chunk.get("id"),
                        e,
                    )
                    errors += 1

            logger.info(
                "[brain/archival] batch done — archived %d so far, %d errors",
                total_archived,
                errors,
            )

    except Exception as e:
        logger.error("[brain/archival] fatal error: %s", e)
        return {
            "message": f"Brain archival failed: {str(e)[:200]}",
            "archived_count": total_archived,
            "errors": errors,
        }

    msg = f"Brain archival complete — {total_archived} chunks archived"
    if errors:
        msg += f", {errors} errors"

    logger.info("[brain/archival] %s", msg)
    return {
        "message": msg,
        "archived_count": total_archived,
        "errors": errors,
    }
