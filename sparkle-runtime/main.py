"""
Sparkle Runtime — FastAPI entry point.
The /health endpoint is the first thing that must work in any environment.
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from runtime.config import settings
from runtime.db import supabase
from runtime.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    start_scheduler()
    yield
    # Shutdown
    stop_scheduler()


app = FastAPI(
    title="Sparkle Runtime",
    version=settings.runtime_version,
    docs_url="/docs",
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────
from runtime.friday.router import router as friday_router
from runtime.tasks.worker import router as tasks_router
from runtime.agents.router import router as agents_router
from runtime.zenya.router import router as zenya_router
from runtime.characters.router import router as characters_router
from runtime.members.router import router as members_router
from runtime.system_router import router as system_router
from runtime.brain.ingest_url import router as brain_ingest_url_router
from runtime.brain.pipeline_router import router as brain_pipeline_router
from runtime.context.router import router as context_router
from runtime.workflow.router import router as workflow_router
from runtime.gaps.router import router as gaps_router

app.include_router(friday_router, prefix="/friday", tags=["friday"])
app.include_router(tasks_router, prefix="/tasks", tags=["tasks"])
app.include_router(agents_router, prefix="/agent", tags=["agents"])
app.include_router(zenya_router, prefix="/zenya", tags=["zenya"])
app.include_router(characters_router, prefix="/character", tags=["characters"])
app.include_router(members_router, prefix="/member", tags=["members"])
app.include_router(system_router)
app.include_router(brain_ingest_url_router, prefix="/brain", tags=["brain"])
app.include_router(brain_pipeline_router, prefix="/brain", tags=["brain"])
app.include_router(context_router, prefix="/context", tags=["context"])
app.include_router(workflow_router, prefix="/workflow", tags=["workflow"])
app.include_router(gaps_router, prefix="/system/gaps", tags=["gaps"])


# ── Health ─────────────────────────────────────────────────
@app.get("/health")
async def health():
    from runtime.integrations.zapi import get_status as zapi_status
    checks: dict = {
        "supabase": _check_supabase(),
        "zapi_connected": zapi_status() if settings.zapi_base_url else False,
        "zapi_configured": bool(settings.zapi_base_url and settings.zapi_instance_id),
        "groq_configured": bool(settings.groq_api_key),
        "anthropic_configured": bool(settings.anthropic_api_key),
    }
    overall = "ok" if checks["supabase"] and checks["anthropic_configured"] else "degraded"
    return {
        "status": overall,
        "version": settings.runtime_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }


@app.post("/debug/webhook")
async def debug_webhook(request: Request):
    """Mostra exatamente o que o Z-API está enviando."""
    body = await request.body()
    try:
        parsed = json.loads(body)
    except Exception:
        parsed = body.decode()
    print(f"DEBUG WEBHOOK: {json.dumps(parsed, indent=2, ensure_ascii=False)}")
    return {"received": parsed}


def _check_supabase() -> bool:
    try:
        supabase.table("agents").select("agent_id").limit(1).execute()
        return True
    except Exception:
        return False
