"""
Brain Metrics Router — B3-05: Usage metrics and namespace stats.

Endpoints:
  GET /brain/metrics?sort=most_used&limit=20  — top chunks by usage
  GET /brain/metrics?sort=least_used&limit=20 — least used chunks
  GET /brain/metrics?sort=recent              — recently used chunks
  GET /brain/metrics/namespaces               — namespace summary stats
"""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Query

from runtime.db import supabase

router = APIRouter()


@router.get("/metrics")
async def brain_metrics(
    sort: Optional[str] = Query(
        default="most_used",
        description="Sort order: most_used, least_used, recent, oldest",
    ),
    limit: int = Query(default=20, ge=1, le=100),
    namespace: Optional[str] = Query(default=None, description="Filter by namespace"),
    brain_owner: Optional[str] = Query(default=None, description="Filter by brain_owner"),
):
    """
    Return brain chunk usage metrics.

    Sort options:
      - most_used   : highest usage_count first
      - least_used  : lowest usage_count first (only chunks used at least once)
      - recent      : most recently used first
      - oldest      : oldest last_used_at first
      - never_used  : chunks never queried (usage_count = 0)
    """
    try:
        # Build base query
        q = supabase.table("brain_chunks").select(
            "id, source_title, source_type, namespace, brain_owner, "
            "usage_count, last_used_at, created_at, curation_status, "
            "confirmation_count, expires_at"
        )

        # Apply filters
        if namespace:
            q = q.eq("namespace", namespace)
        if brain_owner:
            q = q.eq("brain_owner", brain_owner)

        # Apply sort
        if sort == "most_used":
            q = q.order("usage_count", desc=True).order("last_used_at", desc=True)
        elif sort == "least_used":
            q = q.gt("usage_count", 0).order("usage_count").order("last_used_at")
        elif sort == "recent":
            q = q.not_.is_("last_used_at", "null").order("last_used_at", desc=True)
        elif sort == "oldest":
            q = q.not_.is_("last_used_at", "null").order("last_used_at")
        elif sort == "never_used":
            q = q.eq("usage_count", 0).order("created_at", desc=True)
        else:
            q = q.order("usage_count", desc=True)

        q = q.limit(limit)

        result = await asyncio.to_thread(lambda: q.execute())

        chunks = result.data or []

        return {
            "status": "ok",
            "sort": sort,
            "count": len(chunks),
            "chunks": chunks,
        }

    except Exception as e:
        return {"status": "error", "message": f"Failed to fetch metrics: {str(e)[:200]}"}


@router.get("/metrics/namespaces")
async def brain_namespace_stats():
    """
    Return aggregated stats per namespace:
      - chunk count
      - total usage
      - average usage
    """
    try:
        # P1-4: Use server-side RPC for aggregation (avoids full table scan)
        try:
            result = await asyncio.to_thread(
                lambda: supabase.rpc("brain_namespace_stats").execute()
            )
            rows = result.data or []
            namespace_list = [
                {
                    "namespace": r["namespace"],
                    "chunk_count": r["chunk_count"],
                    "total_usage": r["total_usage"],
                    "avg_usage": round(float(r["avg_usage"]), 2),
                }
                for r in rows
            ]
            return {
                "status": "ok",
                "total_namespaces": len(namespace_list),
                "namespaces": namespace_list,
            }
        except Exception as rpc_err:
            print(f"[brain/metrics] RPC brain_namespace_stats failed, using Python fallback: {rpc_err}")

        # Fallback: fetch all and aggregate in Python (if RPC not deployed yet)
        result = await asyncio.to_thread(
            lambda: supabase.table("brain_chunks")
            .select("namespace, usage_count")
            .execute()
        )

        rows = result.data or []

        stats: dict[str, dict] = {}
        for row in rows:
            ns = row.get("namespace") or "general"
            if ns not in stats:
                stats[ns] = {"namespace": ns, "chunk_count": 0, "total_usage": 0}
            stats[ns]["chunk_count"] += 1
            stats[ns]["total_usage"] += row.get("usage_count", 0)

        namespace_list = list(stats.values())
        for ns in namespace_list:
            ns["avg_usage"] = round(
                ns["total_usage"] / ns["chunk_count"], 2
            ) if ns["chunk_count"] > 0 else 0

        namespace_list.sort(key=lambda x: x["chunk_count"], reverse=True)

        return {
            "status": "ok",
            "total_namespaces": len(namespace_list),
            "namespaces": namespace_list,
        }

    except Exception as e:
        return {"status": "error", "message": f"Failed to fetch namespace stats: {str(e)[:200]}"}
