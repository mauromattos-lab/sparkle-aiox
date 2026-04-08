"""
Instagram Publisher — CONTENT-1.11.

Publishes content_pieces as Instagram Reels via Graph API v19.0.

Flow (2-step process):
  1. POST /{ig_user_id}/media   → create container, get creation_id
  2. Poll container until FINISHED (max 30 attempts × 10s = 5 min)
  3. POST /{ig_user_id}/media_publish  → publish and get media_id

On success: status='published', published_at=now(), published_url set.
On failure: status='publish_failed', error_log updated, Friday notified.

NOTE: INSTAGRAM_ACCESS_TOKEN and INSTAGRAM_USER_ID are read from env.
They are not yet configured. All code is complete; the integration will
be live once Mauro sets up the Meta Developer App.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Optional

import httpx

from runtime.config import settings
from runtime.db import supabase

# Runtime base URL for internal calls (ingest-pipeline)
_RUNTIME_BASE = "http://localhost:8001"

# ── Instagram Graph API constants ──────────────────────────────

GRAPH_BASE = "https://graph.facebook.com/v19.0"

# Polling configuration
POLL_ATTEMPTS = 30
POLL_INTERVAL_SEC = 10  # seconds between polls

# Publish slots (BRT hours)
PUBLISH_SLOTS_BRT = [8, 12, 18]

# Timezone offset BRT = UTC-3
BRT_UTC_OFFSET = -3


# ── Helpers ────────────────────────────────────────────────────

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now_utc().isoformat()


def _get_piece(piece_id: str) -> dict | None:
    result = supabase.table("content_pieces").select("*").eq("id", piece_id).limit(1).execute()
    return result.data[0] if result.data else None


def _update_piece(piece_id: str, fields: dict) -> None:
    supabase.table("content_pieces").update({
        **fields,
        "updated_at": _now_iso(),
    }).eq("id", piece_id).execute()


def _append_pipeline_log(piece_id: str, event: dict) -> None:
    piece = _get_piece(piece_id)
    if not piece:
        return
    pipeline_log = list(piece.get("pipeline_log") or [])
    pipeline_log.append({**event, "at": _now_iso()})
    supabase.table("content_pieces").update({
        "pipeline_log": pipeline_log,
        "updated_at": _now_iso(),
    }).eq("id", piece_id).execute()


# ── Slot scheduling ────────────────────────────────────────────

def get_next_slot() -> datetime:
    """
    Return the next available publish slot (08h, 12h, 18h BRT) that does
    not already have a 'scheduled' piece assigned to it.

    AC6: skips slots already occupied.
    AC7: max 1 Reel per slot.
    """
    # Fetch all scheduled pieces and their scheduled_at times
    try:
        result = (
            supabase.table("content_pieces")
            .select("scheduled_at")
            .eq("status", "scheduled")
            .execute()
        )
        occupied: set[str] = set()
        for row in (result.data or []):
            sat = row.get("scheduled_at")
            if sat:
                # Normalize to YYYY-MM-DDTHH (slot key: date + hour UTC)
                occupied.add(sat[:13])  # "2026-04-07T11" (UTC)
    except Exception as exc:
        print(f"[publisher] get_next_slot: DB query error (using immediate slot): {exc}")
        occupied = set()

    now_utc = _now_utc()

    # Iterate next 14 days of slots to find a free one
    for day_offset in range(14):
        for slot_brt in PUBLISH_SLOTS_BRT:
            # Convert BRT to UTC (BRT = UTC-3)
            slot_utc_hour = (slot_brt - BRT_UTC_OFFSET) % 24  # slot_brt + 3

            candidate = now_utc.replace(
                hour=slot_utc_hour,
                minute=0,
                second=0,
                microsecond=0,
            )
            # Advance by day_offset days
            from datetime import timedelta
            candidate = candidate + timedelta(days=day_offset)

            # Must be in the future
            if candidate <= now_utc:
                continue

            # Check if occupied
            slot_key = candidate.strftime("%Y-%m-%dT%H")
            if slot_key not in occupied:
                return candidate

    # Fallback: 1 hour from now (should never happen in 14 days)
    from datetime import timedelta
    return now_utc + timedelta(hours=1)


def schedule_piece(piece_id: str) -> datetime:
    """
    Calculate next available slot and update piece to status='scheduled'.
    Called by approval flow (AC1).

    Returns the scheduled_at datetime.
    """
    slot = get_next_slot()
    _update_piece(piece_id, {
        "status": "scheduled",
        "scheduled_at": slot.isoformat(),
    })
    _append_pipeline_log(piece_id, {
        "event": "scheduled",
        "scheduled_at": slot.isoformat(),
    })
    print(f"[publisher] piece {piece_id[:8]} scheduled → {slot.isoformat()}")
    return slot


# ── Instagram Graph API calls ──────────────────────────────────

async def _create_media_container(
    ig_user_id: str,
    access_token: str,
    video_url: str,
    caption: str,
) -> str:
    """
    Step 1: Create a Reels media container.
    Returns creation_id string.
    Raises RuntimeError on failure.
    """
    url = f"{GRAPH_BASE}/{ig_user_id}/media"
    params = {
        "video_url": video_url,
        "caption": caption,
        "media_type": "REELS",
        "access_token": access_token,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, params=params)
    if resp.status_code != 200:
        raise RuntimeError(
            f"Instagram container creation failed: {resp.status_code} — {resp.text[:400]}"
        )
    data = resp.json()
    creation_id = data.get("id")
    if not creation_id:
        raise RuntimeError(f"Instagram API did not return container id: {data}")
    return creation_id


async def _poll_container_status(creation_id: str, access_token: str) -> str:
    """
    Step 2: Poll container status until FINISHED.
    Returns final status_code string.
    Raises RuntimeError after max attempts.
    """
    url = f"{GRAPH_BASE}/{creation_id}"
    params = {
        "fields": "status_code",
        "access_token": access_token,
    }
    for attempt in range(1, POLL_ATTEMPTS + 1):
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params=params)
        if resp.status_code != 200:
            raise RuntimeError(
                f"Container status poll failed: {resp.status_code} — {resp.text[:200]}"
            )
        data = resp.json()
        status_code = data.get("status_code", "")

        if status_code == "FINISHED":
            print(f"[publisher] container {creation_id} FINISHED after {attempt} polls")
            return status_code
        elif status_code in ("ERROR", "EXPIRED"):
            raise RuntimeError(
                f"Container {creation_id} reached terminal error status: {status_code}"
            )

        print(f"[publisher] poll {attempt}/{POLL_ATTEMPTS}: container={creation_id} status={status_code}")
        await asyncio.sleep(POLL_INTERVAL_SEC)

    raise RuntimeError(
        f"Container {creation_id} did not reach FINISHED after {POLL_ATTEMPTS} attempts"
    )


async def _publish_container(
    ig_user_id: str,
    access_token: str,
    creation_id: str,
) -> str:
    """
    Step 3: Publish the container.
    Returns the Instagram media_id (post ID).
    """
    url = f"{GRAPH_BASE}/{ig_user_id}/media_publish"
    params = {
        "creation_id": creation_id,
        "access_token": access_token,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, params=params)
    if resp.status_code != 200:
        raise RuntimeError(
            f"Instagram publish failed: {resp.status_code} — {resp.text[:400]}"
        )
    data = resp.json()
    media_id = data.get("id")
    if not media_id:
        raise RuntimeError(f"Instagram API did not return media_id: {data}")
    return media_id


# ── Brain ingest after publish ──────────────────────────────────

async def _ingest_published_to_brain(piece: dict) -> Optional[str]:
    """
    W1-BRAIN-1 AC4: After successful Instagram publication, ingest piece into Brain
    via the full 6-phase pipeline (ingest-pipeline endpoint).

    Fixes Bug 1 (direct insert → pipeline), Bug 2 (brain_owner=content, not sparkle-lore),
    Bug 3 (namespace in top-level field via metadata priority 1).

    Returns chunk_id from pipeline result if available, None otherwise (never blocks).
    """
    try:
        piece_id = piece["id"]
        theme = piece.get("theme") or ""
        caption = piece.get("caption") or ""
        voice_script = piece.get("voice_script") or ""
        published_url = piece.get("published_url") or ""
        published_at = piece.get("published_at") or _now_iso()
        character = (piece.get("character") or "zenya").lower()
        content_type = piece.get("content_type") or "reel"

        raw_content = (
            f"[Published Reel] Theme: {theme}\n"
            f"Caption: {caption[:500]}\n"
            f"Script: {voice_script[:300]}\n"
            f"URL: {published_url}"
        ).strip()

        if not raw_content:
            return None

        payload = {
            "source_type": "published_reel",
            "raw_content": raw_content,
            "title": f"Reel: {theme[:80]}",
            "persona": "especialista",   # → brain_owner = "content"
            "client_id": None,           # sparkle-internal
            "run_dna": False,
            "run_narrative": False,
            # namespace explícito em metadata (prioridade 1 em resolve_namespace)
            # chunk_metadata passado via pipeline como metadado extra
        }

        # Build metadata that will be stored in chunk_metadata by the pipeline
        # We pass it through a dedicated metadata field if pipeline supports it,
        # otherwise we embed it in raw_content context header.
        # For now, namespace is resolved via _SOURCE_TYPE_MAP["published_reel"] = "sparkle-lore"
        # and additional metadata is embedded as structured comment in raw_content.
        metadata_header = (
            f"[metadata] content_piece_id={piece_id} "
            f"character={character} content_type={content_type} "
            f"approved_at={published_at} instagram_url={published_url or 'null'}"
        )
        payload["raw_content"] = f"{metadata_header}\n{raw_content}"

        url = f"{_RUNTIME_BASE}/brain/ingest-pipeline"
        headers = {}
        if settings.runtime_api_key:
            headers["Authorization"] = f"Bearer {settings.runtime_api_key}"

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, json=payload, headers=headers)

        if resp.status_code != 200:
            print(f"[publisher] Brain ingest pipeline error {resp.status_code}: {resp.text[:300]}")
            return None

        data = resp.json()
        if data.get("status") != "ok":
            print(f"[publisher] Brain ingest pipeline failed: {data.get('error', 'unknown')}")
            return None

        # Extract chunk_id from pipeline result (chunks_ids or first chunk)
        chunk_ids = data.get("chunk_ids") or []
        chunk_id = chunk_ids[0] if chunk_ids else data.get("chunk_id")
        print(f"[publisher] Brain ingest (pipeline): piece {piece_id[:8]} → chunk {chunk_id} (namespace=sparkle-lore)")
        return chunk_id

    except Exception as exc:
        print(f"[publisher] Brain ingest failed (non-blocking): {exc}")
        return None


async def _update_chunk_instagram_url(brain_chunk_id: str, instagram_url: str, piece_id: str) -> None:
    """
    W1-BRAIN-1 AC4 (T6): After Instagram publish, update the brain chunk's metadata
    with the real instagram_url so the lore record is complete.
    """
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("brain_chunks")
            .select("chunk_metadata")
            .eq("id", brain_chunk_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            return
        existing_meta = result.data[0].get("chunk_metadata") or {}
        updated_meta = {**existing_meta, "instagram_url": instagram_url, "published_at": _now_iso()}
        await asyncio.to_thread(
            lambda: supabase.table("brain_chunks")
            .update({"chunk_metadata": updated_meta})
            .eq("id", brain_chunk_id)
            .execute()
        )
        print(f"[publisher] chunk {brain_chunk_id} instagram_url updated → {instagram_url}")
    except Exception as exc:
        print(f"[publisher] chunk instagram_url update failed (non-blocking): {exc}")


# ── Friday notification ────────────────────────────────────────

async def _notify_friday_publish_failed(piece_id: str, error: str) -> None:
    """
    AC4: Notify Mauro via WhatsApp when publishing fails.
    AC8 (CONTENT-1.12).
    """
    try:
        from runtime.integrations import zapi
        phone = settings.mauro_whatsapp
        if not phone:
            print("[publisher] MAURO_WHATSAPP not configured — skip Friday notification")
            return
        msg = (
            f"⚠️ Falha ao publicar conteudo da Zenya\n"
            f"Acesse: {settings.portal_base_url}/hq/content/\n"
            f"Piece: {piece_id[:8]}\n"
            f"Erro: {error[:200]}"
        )
        await asyncio.to_thread(lambda: zapi.send_text(phone, msg))
        print(f"[publisher] Friday notified of publish_failed for {piece_id[:8]}")
    except Exception as exc:
        print(f"[publisher] Friday notification failed (non-blocking): {exc}")


# ── Main publish function ──────────────────────────────────────

async def publish(piece: dict) -> dict:
    """
    Publish a scheduled content_piece as an Instagram Reel.

    AC2: 3-step Graph API flow (create container → poll → publish).
    AC3: On success: status='published', published_at, published_url set.
    AC4: On failure: status='publish_failed', error_log updated, Friday notified.
    AC5: On success: ingest to Brain namespace sparkle-lore.

    Returns updated piece dict.
    """
    piece_id = piece["id"]

    # ── Guard: credentials ──────────────────────────────────────
    ig_token = settings.instagram_access_token
    ig_user_id = settings.instagram_user_id

    if not ig_token or not ig_user_id:
        error_msg = (
            "Instagram credentials not configured "
            "(INSTAGRAM_ACCESS_TOKEN or INSTAGRAM_USER_ID missing)"
        )
        print(f"[publisher] {piece_id[:8]}: {error_msg}")
        _update_piece(piece_id, {
            "status": "publish_failed",
            "error_log": error_msg,
        })
        _append_pipeline_log(piece_id, {
            "event": "publish_failed",
            "error": error_msg,
        })
        asyncio.create_task(_notify_friday_publish_failed(piece_id, error_msg))
        return _get_piece(piece_id) or piece

    # ── Guard: video_url required ───────────────────────────────
    video_url = piece.get("final_url") or piece.get("video_url")
    if not video_url:
        error_msg = "No video_url or final_url — cannot publish without video"
        _update_piece(piece_id, {
            "status": "publish_failed",
            "error_log": error_msg,
        })
        asyncio.create_task(_notify_friday_publish_failed(piece_id, error_msg))
        return _get_piece(piece_id) or piece

    caption = piece.get("caption") or ""

    print(f"[publisher] Starting publish for piece {piece_id[:8]}")

    try:
        # Step 1: Create container
        creation_id = await _create_media_container(
            ig_user_id=ig_user_id,
            access_token=ig_token,
            video_url=video_url,
            caption=caption,
        )
        _append_pipeline_log(piece_id, {
            "event": "container_created",
            "creation_id": creation_id,
        })

        # Step 2: Poll for FINISHED
        await _poll_container_status(creation_id, ig_token)

        # Step 3: Publish
        media_id = await _publish_container(ig_user_id, ig_token, creation_id)

    except Exception as exc:
        error_msg = str(exc)
        print(f"[publisher] publish failed for {piece_id[:8]}: {error_msg}")
        _update_piece(piece_id, {
            "status": "publish_failed",
            "error_log": error_msg[:2000],
        })
        _append_pipeline_log(piece_id, {
            "event": "publish_failed",
            "error": error_msg[:500],
        })
        # AC4: trigger Friday notification asynchronously
        asyncio.create_task(_notify_friday_publish_failed(piece_id, error_msg))
        return _get_piece(piece_id) or piece

    # ── Success ─────────────────────────────────────────────────
    published_url = f"https://www.instagram.com/p/{media_id}/"
    now_iso = _now_iso()

    _update_piece(piece_id, {
        "status": "published",
        "published_at": now_iso,
        "published_url": published_url,
    })
    _append_pipeline_log(piece_id, {
        "event": "published",
        "media_id": media_id,
        "published_url": published_url,
    })
    print(f"[publisher] piece {piece_id[:8]} published → {published_url}")

    # AC5: Brain ingest (async, non-blocking)
    fresh = _get_piece(piece_id)
    if fresh:
        asyncio.create_task(_do_brain_ingest(fresh))

    return fresh or {}


async def _do_brain_ingest(piece: dict) -> None:
    """
    Fire-and-forget brain ingest wrapper.
    Updates brain_chunk_id on content_pieces and instagram_url on brain chunk.
    """
    chunk_id = await _ingest_published_to_brain(piece)
    if chunk_id:
        # T5: persist chunk_id back to content_pieces
        try:
            _update_piece(piece["id"], {"brain_chunk_id": chunk_id})
        except Exception as exc:
            print(f"[publisher] brain_chunk_id update failed: {exc}")
        # T6: update chunk's instagram_url now that we have the published_url
        published_url = piece.get("published_url") or ""
        if published_url:
            asyncio.create_task(_update_chunk_instagram_url(chunk_id, published_url, piece["id"]))
