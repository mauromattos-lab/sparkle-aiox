"""
Expansion router — /expansion/* endpoints (LIFECYCLE-2.1).

GET  /expansion/opportunities       — list detected opportunities
POST /expansion/{client_id}/approach — mark approached + return script
POST /expansion/detect              — force detection (testing)
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from runtime.db import supabase
from runtime.expansion.detector import detect_all_opportunities
from runtime.expansion.scripts import get_script
from runtime.expansion.proposals import generate_proposal, approve_proposal, send_proposal, list_proposals
from runtime.expansion.referral import propose_referral, register_referred_lead, mark_referral_converted, propose_to_all_promoters
from runtime.expansion.case_generator import generate_case, generate_all_eligible_cases
from runtime.expansion.script_renderer import render_script_for_client, deliver_script_to_friday


logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/opportunities")
async def list_opportunities(
    status: Optional[str] = Query(None, description="Filter: detected|approached|converted|dismissed"),
    client_id: Optional[str] = Query(None),
    opportunity_type: Optional[str] = Query(None),
):
    """List upsell/cross-sell opportunities with optional filters."""
    try:
        q = supabase.table("upsell_opportunities").select("*").order("detected_at", desc=True)
        if status:
            q = q.eq("status", status)
        if client_id:
            q = q.eq("client_id", client_id)
        if opportunity_type:
            q = q.eq("opportunity_type", opportunity_type)

        res = await asyncio.to_thread(lambda: q.limit(100).execute())
        rows = res.data or []

        # Enrich with client names
        for row in rows:
            try:
                cr = await asyncio.to_thread(
                    lambda cid=row["client_id"]: supabase.table("zenya_clients")
                    .select("business_name")
                    .eq("id", cid)
                    .maybe_single()
                    .execute()
                )
                client_data = cr.data if cr and hasattr(cr, "data") else cr
                row["client_name"] = client_data.get("business_name") if client_data else None
            except Exception:
                row["client_name"] = None

        return {"opportunities": rows, "count": len(rows)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{client_id}/approach")
async def mark_approached(client_id: str):
    """Mark opportunity as approached and return the appropriate script."""
    try:
        # Find latest detected opportunity for this client
        res = await asyncio.to_thread(
            lambda: supabase.table("upsell_opportunities")
            .select("*")
            .eq("client_id", client_id)
            .eq("status", "detected")
            .order("detected_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            raise HTTPException(status_code=404, detail="No detected opportunity for this client")

        opp = rows[0]

        # Get client context for script
        client_res = await asyncio.to_thread(
            lambda: supabase.table("zenya_clients")
            .select("business_name, created_at")
            .eq("id", client_id)
            .maybe_single()
            .execute()
        )
        client = client_res.data if client_res and hasattr(client_res, "data") else client_res
        
        from datetime import datetime, timezone
        months = 0
        if client and client.get("created_at"):
            dt = datetime.fromisoformat(client["created_at"].replace("Z", "+00:00"))
            months = max(1, (datetime.now(timezone.utc) - dt).days // 30)

        context = {
            "client_name": client.get("business_name", "") if client else "",
            "business_name": client.get("business_name", "") if client else "",
            "months_active": months,
            "health_score": opp.get("score", ""),
            "volume": opp.get("signal", "").split("volume=")[-1].split("/")[0] if "volume=" in (opp.get("signal") or "") else "N/A",
        }

        script = get_script(opp["opportunity_type"], context)

        # Update status to approached
        from datetime import datetime, timezone
        await asyncio.to_thread(
            lambda: supabase.table("upsell_opportunities")
            .update({"status": "approached", "approached_at": datetime.now(timezone.utc).isoformat()})
            .eq("id", opp["id"])
            .execute()
        )

        return {
            "opportunity": opp,
            "script": script,
            "status": "approached",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/detect")
async def force_detection():
    """Force run upsell detection for all clients (testing/manual trigger)."""
    try:
        result = await detect_all_opportunities()
        return {"status": "ok", **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Story 3.1: Proposals

@router.post("/proposals/generate/{lead_id}")
async def api_generate_proposal(lead_id: str):
    try:
        result = await generate_proposal(lead_id)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/proposals/{proposal_id}/approve")
async def api_approve_proposal(proposal_id: str, edited_content: str = None):
    try:
        return await approve_proposal(proposal_id, edited_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/proposals/{proposal_id}/send")
async def api_send_proposal(proposal_id: str, via: str = "whatsapp"):
    try:
        result = await send_proposal(proposal_id, via)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/proposals")
async def api_list_proposals(status: Optional[str] = None, niche: Optional[str] = None):
    try:
        rows = await list_proposals(status=status, niche=niche)
        return {"proposals": rows, "count": len(rows)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Story 3.3: Script Renderer

@router.get("/scripts/{client_id}/{opportunity_type}")
async def api_render_script(client_id: str, opportunity_type: str):
    try:
        result = await render_script_for_client(client_id, opportunity_type)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scripts/{client_id}/{opportunity_type}/deliver")
async def api_deliver_script(client_id: str, opportunity_type: str, opportunity_id: str = None):
    try:
        result = await deliver_script_to_friday(client_id, opportunity_type, opportunity_id)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Story 3.4: Referral

@router.post("/referral/{client_id}/propose")
async def api_propose_referral(client_id: str):
    try:
        result = await propose_referral(client_id)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/referral/{referral_id}/register-lead")
async def api_register_referred(referral_id: str, name: str = "", phone: str = ""):
    try:
        return await register_referred_lead(referral_id, name, phone)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/referral/{referral_id}/converted")
async def api_mark_converted(referral_id: str):
    try:
        return await mark_referral_converted(referral_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/referral/propose-all")
async def api_propose_all_promoters():
    try:
        result = await propose_to_all_promoters()
        return {"status": "ok", **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Story 3.4: Cases

@router.post("/cases/generate/{client_id}")
async def api_generate_case(client_id: str):
    try:
        result = await generate_case(client_id)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cases/generate-all")
async def api_generate_all_cases():
    try:
        result = await generate_all_eligible_cases()
        return {"status": "ok", **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cases")
async def api_list_cases(niche: Optional[str] = None, status: Optional[str] = None):
    try:
        q = supabase.table("auto_cases").select("*").order("generated_at", desc=True)
        if niche:
            q = q.eq("niche", niche)
        if status:
            q = q.eq("status", status)
        res = await asyncio.to_thread(lambda: q.limit(50).execute())
        rows = res.data or []
        return {"cases": rows, "count": len(rows)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
