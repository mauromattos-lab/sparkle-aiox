"""
Onboarding — ONB-2: Consolidador de intake.

Consolida dados de scrape (site + Instagram) e formulário WhatsApp
em um intake_summary JSONB, calcula completeness_score e persiste
no campo intake_data da fase 'intake' em onboarding_workflows.

Regras de completude (AC-4.2, AC-4.3):
- site_scraped:   +40 pontos
- instagram:      +30 pontos
- form_complete:  +30 pontos  (partial = +15)
- >= 30 pontos → intake_complete = true
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

from runtime.db import supabase


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compute_score(
    site_ok: bool,
    instagram_ok: bool,
    form_complete: bool,
    form_partial: bool,
) -> int:
    """Calcula completeness_score 0-100."""
    score = 0
    if site_ok:
        score += 40
    if instagram_ok:
        score += 30
    if form_complete:
        score += 30
    elif form_partial:
        score += 15
    return min(score, 100)


async def consolidate_intake(
    client_id: str,
    site_data: Optional[dict] = None,
    instagram_data: Optional[dict] = None,
    form_answers: Optional[list] = None,
    form_complete: bool = False,
    form_partial: bool = False,
) -> dict:
    """
    Consolida todas as fontes de intake e persiste em onboarding_workflows.

    Returns intake_summary dict with completeness_score and intake_complete flag.
    """
    site_ok = bool(site_data and site_data.get("chunks_inserted", 0) > 0)
    instagram_ok = bool(instagram_data and instagram_data.get("chunks_inserted", 0) > 0)

    score = _compute_score(site_ok, instagram_ok, form_complete, form_partial)
    intake_complete = score >= 30

    summary = {
        "site": {
            "scraped": site_ok,
            "chunks_inserted": (site_data or {}).get("chunks_inserted", 0),
            "title": (site_data or {}).get("title", ""),
        },
        "instagram": {
            "scraped": instagram_ok,
            "chunks_inserted": (instagram_data or {}).get("chunks_inserted", 0),
        },
        "form": {
            "complete": form_complete,
            "partial": form_partial,
            "answers": form_answers or [],
            "answers_count": len(form_answers or []),
        },
        "completeness_score": score,
        "intake_complete": intake_complete,
        "consolidated_at": _now(),
    }

    # Persist to onboarding_workflows intake phase
    now_ts = _now()
    try:
        await asyncio.to_thread(
            lambda: supabase.table("onboarding_workflows")
            .update({
                "intake_data": summary,
                "intake_complete": intake_complete,
                "updated_at": now_ts,
            })
            .eq("client_id", client_id)
            .eq("phase", "intake")
            .execute()
        )
        print(
            f"[consolidator] client_id={client_id[:12]}... "
            f"score={score}% intake_complete={intake_complete}"
        )
    except Exception as e:
        print(f"[consolidator] WARN: falha ao salvar intake_data: {e}")

    # If intake_complete, update gate_details so gate check can pass
    if intake_complete:
        try:
            # Read current gate_details
            result = await asyncio.to_thread(
                lambda: supabase.table("onboarding_workflows")
                .select("gate_details")
                .eq("client_id", client_id)
                .eq("phase", "intake")
                .maybe_single()
                .execute()
            )
            gate_details = {}
            if result and result.data:
                gate_details = result.data.get("gate_details") or {}

            gate_details["intake_complete"] = True

            await asyncio.to_thread(
                lambda: supabase.table("onboarding_workflows")
                .update({
                    "gate_details": gate_details,
                    "updated_at": now_ts,
                })
                .eq("client_id", client_id)
                .eq("phase", "intake")
                .execute()
            )
        except Exception as e:
            print(f"[consolidator] WARN: falha ao atualizar gate_details: {e}")

    return summary
