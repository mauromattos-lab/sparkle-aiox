"""
Onboarding SOP automatizado — B3-03.

Pipeline completo de onboarding de novo cliente:
1. Cria registro do cliente (status=draft)
2. Ingere website no Brain (se URL fornecida)
3. Extrai DNA do cliente a partir dos chunks
4. Gera soul_prompt personalizado via Haiku
5. Cria character (Zenya do cliente) em draft
6. Cria character_state inicial

Cada step e idempotente e logado. Tudo nasce em status "draft"
ate aprovacao humana via POST /onboarding/approve/{client_id}.
"""
from __future__ import annotations

import asyncio
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from runtime.config import settings
from runtime.db import supabase
from runtime.onboarding.prompt_generator import generate_zenya_prompt


# ── Step tracking ─────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log_step(steps: list[dict], name: str, status: str, detail: str = "") -> None:
    """Append a step result to the tracking list."""
    steps.append({
        "step": name,
        "status": status,
        "detail": detail,
        "timestamp": _now(),
    })
    print(f"[onboarding] {name}: {status} — {detail}")


# ── Step 1: Create client record ──────────────────────────────

async def _create_client(
    client_id: str,
    business_name: str,
    contact_phone: str,
    website_url: str,
    instagram_handle: str,
) -> str:
    """Create or update client in `clients` table with status=draft. Returns client_id.

    Bug S0.2-3/4 fix: also creates zenya_clients record with testing_mode='off'.
    """
    row = {
        "id": client_id,
        "name": business_name,
        "whatsapp": contact_phone,
        "instagram": instagram_handle or None,
        "website": website_url or None,
        "niche": "geral",
        "status": "draft",
        "mrr": 0,
    }

    await asyncio.to_thread(
        lambda: supabase.table("clients").upsert(row, on_conflict="id").execute()
    )

    # Bug S0.2-3: create zenya_clients record (was missing in original handler)
    # Bug S0.2-4: testing_mode column now exists via migration — set to 'off' initially
    zenya_row = {
        "client_id": client_id,
        "active": False,
        "testing_mode": "off",
    }
    try:
        await asyncio.to_thread(
            lambda: supabase.table("zenya_clients").upsert(zenya_row, on_conflict="client_id").execute()
        )
    except Exception as e:
        print(f"[onboarding] zenya_clients upsert failed (non-fatal): {e}")

    return client_id


# ── Step 2: Ingest website ────────────────────────────────────

async def _ingest_website(client_id: str, website_url: str) -> dict:
    """Ingest client website into Brain via the existing ingest_url logic."""
    if not website_url:
        return {"chunks_inserted": 0, "skipped": True}

    # Normalize URL
    if not website_url.startswith(("http://", "https://")):
        website_url = "https://" + website_url

    # Import the ingest logic directly (avoid circular router import)
    from runtime.brain.ingest_url import IngestUrlRequest, ingest_url

    req = IngestUrlRequest(
        url=website_url,
        title=f"Website — onboarding",
        source_agent="zenya",  # Bug S0.2-1 fix: "zenya" + client_id -> brain_owner=client_id
        client_id=client_id,
        persona="zenya",
    )
    result = await ingest_url(req)
    return result


# ── Step 3: Extract DNA ──────────────────────────────────────

async def _extract_dna(client_id: str) -> dict:
    """Extract client DNA from Brain chunks using existing handler."""
    from runtime.tasks.handlers.extract_client_dna import handle_extract_client_dna

    task = {
        "id": f"onboarding-dna-{client_id}",
        "task_type": "extract_client_dna",
        "payload": {
            "client_id": client_id,
            "regenerate_prompt": False,  # we generate our own prompt in step 4
        },
    }
    result = await handle_extract_client_dna(task)
    return result


# ── Step 4: Generate soul_prompt ──────────────────────────────

async def _generate_soul_prompt(client_id: str) -> str:
    """Fetch DNA from DB and generate soul_prompt."""
    # Fetch DNA rows
    result = await asyncio.to_thread(
        lambda: supabase.table("client_dna")
        .select("dna_type,key,title,content,confidence")
        .eq("client_id", client_id)
        .order("created_at", desc=True)
        .execute()
    )
    rows = result.data or []

    if not rows:
        return ""

    # Group by dna_type
    dna: dict[str, list[dict]] = {}
    for row in rows:
        dt = row.get("dna_type", "unknown")
        dna.setdefault(dt, []).append(row)

    soul_prompt = await generate_zenya_prompt(client_id, dna)
    return soul_prompt


# ── Step 5: Create character ─────────────────────────────────

async def _create_character(
    client_id: str,
    business_name: str,
    soul_prompt: str,
) -> dict:
    """Create Zenya character for client in `characters` table (active=false)."""
    slug = f"zenya-{re.sub(r'[^a-z0-9]+', '-', business_name.lower()).strip('-')}"

    character = {
        "slug": slug,
        "name": "Zenya",
        "tagline": f"Assistente virtual da {business_name}",
        "specialty": "atendimento",
        "soul_prompt": soul_prompt,
        "active": False,  # draft until approved
        "active_channels": ["whatsapp"],
        "lore_status": "draft",
        "client_id": client_id,
    }

    result = await asyncio.to_thread(
        lambda: supabase.table("characters")
        .upsert(character, on_conflict="slug")
        .execute()
    )
    data = result.data[0] if result.data else character
    return data


# ── Step 6: Create character_state ────────────────────────────

async def _create_character_state(slug: str) -> dict:
    """Create initial character_state row for the new character."""
    from runtime.characters.state import get_character_state
    state = await get_character_state(slug)
    return state


# ── Onboarding progress tracking (Supabase) ──────────────────

async def _save_onboarding_progress(
    client_id: str,
    status: str,
    steps: list[dict],
    soul_prompt: str = "",
    character_slug: str = "",
) -> None:
    """Save onboarding progress to `onboarding_sessions` table."""
    row = {
        "client_id": client_id,
        "status": status,
        "steps": steps,
        "soul_prompt": soul_prompt,
        "character_slug": character_slug,
        "updated_at": _now(),
    }
    try:
        await asyncio.to_thread(
            lambda: supabase.table("onboarding_sessions")
            .upsert(row, on_conflict="client_id")
            .execute()
        )
    except Exception as e:
        print(f"[onboarding] save progress failed (non-fatal): {e}")


# ── Main handler ──────────────────────────────────────────────

async def handle_onboarding(task: dict) -> dict:
    """
    Pipeline completo de onboarding automatizado.

    Input payload:
    {
        "client_id": "<uuid opcional>",
        "business_name": "Confeitaria Maria",
        "website_url": "mariaconfeitaria.com.br",
        "instagram_handle": "@mariaconfeitaria",
        "contact_phone": "5511999999999"
    }

    Returns dict with status, steps executed, and summary.
    """
    payload = task.get("payload", {})

    business_name: str = payload.get("business_name", "").strip()
    website_url: str = payload.get("website_url", "").strip()
    instagram_handle: str = payload.get("instagram_handle", "").strip()
    contact_phone: str = payload.get("contact_phone", "").strip()
    client_id: str = payload.get("client_id") or str(uuid.uuid4())

    if not business_name:
        return {
            "status": "error",
            "error": "business_name e obrigatorio",
        }

    steps: list[dict] = []
    soul_prompt = ""
    character_slug = ""

    # ── Step 1: Create client ─────────────────────────────────
    try:
        await _create_client(
            client_id=client_id,
            business_name=business_name,
            contact_phone=contact_phone,
            website_url=website_url,
            instagram_handle=instagram_handle,
        )
        _log_step(steps, "create_client", "ok", f"client_id={client_id[:12]}...")
    except Exception as e:
        _log_step(steps, "create_client", "error", str(e)[:200])
        await _save_onboarding_progress(client_id, "error", steps)
        return {"status": "error", "error": f"Falha ao criar cliente: {e}", "steps": steps}

    # ── Step 2: Ingest website ────────────────────────────────
    ingest_result = {}
    if website_url:
        try:
            ingest_result = await _ingest_website(client_id, website_url)
            chunks = ingest_result.get("chunks_inserted", 0)
            _log_step(steps, "ingest_website", "ok", f"{chunks} chunks inseridos")
        except Exception as e:
            _log_step(steps, "ingest_website", "warning", f"Falha (nao-bloqueante): {str(e)[:200]}")
    else:
        _log_step(steps, "ingest_website", "skipped", "Nenhuma URL fornecida")

    # ── Step 3: Extract DNA ───────────────────────────────────
    dna_result = {}
    chunks_inserted = ingest_result.get("chunks_inserted", 0)
    if chunks_inserted > 0:
        try:
            dna_result = await _extract_dna(client_id)
            items = dna_result.get("items_extracted", dna_result.get("total_items", 0))
            _log_step(steps, "extract_dna", "ok", f"{items} itens de DNA extraidos")
        except Exception as e:
            _log_step(steps, "extract_dna", "warning", f"Falha (nao-bloqueante): {str(e)[:200]}")
    else:
        _log_step(steps, "extract_dna", "skipped", "Sem chunks no Brain para extrair DNA")

    # ── Step 4: Generate soul_prompt ──────────────────────────
    try:
        soul_prompt = await _generate_soul_prompt(client_id)
        if soul_prompt:
            _log_step(steps, "generate_prompt", "ok", f"{len(soul_prompt)} chars")
        else:
            _log_step(steps, "generate_prompt", "skipped", "Sem DNA disponivel para gerar prompt")
    except Exception as e:
        _log_step(steps, "generate_prompt", "warning", f"Falha (nao-bloqueante): {str(e)[:200]}")

    # ── Step 5: Create character ──────────────────────────────
    try:
        char_data = await _create_character(
            client_id=client_id,
            business_name=business_name,
            soul_prompt=soul_prompt or f"Voce e Zenya, assistente virtual da {business_name}. [SOUL_PROMPT_PENDENTE]",
        )
        character_slug = char_data.get("slug", "")
        _log_step(steps, "create_character", "ok", f"slug={character_slug}")
    except Exception as e:
        _log_step(steps, "create_character", "error", str(e)[:200])
        await _save_onboarding_progress(client_id, "error", steps, soul_prompt)
        return {"status": "error", "error": f"Falha ao criar character: {e}", "steps": steps}

    # ── Step 6: Create character_state ────────────────────────
    try:
        await _create_character_state(character_slug)
        _log_step(steps, "create_character_state", "ok", f"Estado inicial criado para {character_slug}")
    except Exception as e:
        _log_step(steps, "create_character_state", "warning", f"Falha (nao-bloqueante): {str(e)[:200]}")

    # ── Save progress ─────────────────────────────────────────
    await _save_onboarding_progress(
        client_id=client_id,
        status="draft",
        steps=steps,
        soul_prompt=soul_prompt,
        character_slug=character_slug,
    )

    # ── Summary ───────────────────────────────────────────────
    ok_steps = [s for s in steps if s["status"] == "ok"]
    warn_steps = [s for s in steps if s["status"] == "warning"]
    err_steps = [s for s in steps if s["status"] == "error"]

    summary = (
        f"Onboarding de '{business_name}' concluido (DRAFT).\n"
        f"  {len(ok_steps)}/{len(steps)} steps OK"
    )
    if warn_steps:
        summary += f", {len(warn_steps)} warnings"
    if err_steps:
        summary += f", {len(err_steps)} errors"
    summary += (
        f"\n  client_id: {client_id}"
        f"\n  character: {character_slug}"
        f"\n  Status: DRAFT — aguardando aprovacao via POST /onboarding/approve/{client_id}"
    )

    return {
        "status": "draft",
        "client_id": client_id,
        "character_slug": character_slug,
        "soul_prompt_length": len(soul_prompt),
        "steps": steps,
        "summary": summary,
        "message": summary,
    }
