"""
Content Manager router v2 — endpoints for listing, scheduling, and managing generated content.

v1 endpoints (preserved):
  GET  /content/list              — lista conteudos gerados recentes
  GET  /content/calendar          — conteudo organizado por data (calendar view)
  POST /content/schedule          — agenda geracao de conteudo para data futura
  POST /content/{id}/approve      — aprova conteudo (status -> approved)
  POST /content/{id}/reject       — rejeita conteudo (status -> rejected)

v2 endpoints (new):
  GET  /content/templates         — lista templates disponiveis por formato/plataforma
  GET  /content/{id}/preview      — preview estruturado do conteudo para plataforma-alvo
  POST /content/generate-batch    — geracao em lote (plano semanal multi-plataforma)
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from runtime.config import settings
from runtime.content.models import (
    BatchGenerateRequest,
    ContentFormat,
    ContentPreview,
    Platform,
    PLATFORM_METADATA,
    ScheduleRequest,
    get_platform_constraints,
    validate_format_for_platform,
)
from runtime.content.templates import get_template, list_templates, get_prompt_instructions
from runtime.db import supabase

router = APIRouter()


# ── v1 Pydantic models (kept for backward compat) ────────────

class ScheduleRequestV1(BaseModel):
    """v1 schedule request — still accepted, maps to v2 internally."""
    topic: str
    persona: str = "zenya"
    format: str = "instagram_post"
    scheduled_for: datetime


class GenerateRequest(BaseModel):
    """Direct (synchronous) content generation request."""
    topic: str
    persona: str = "zenya"
    format: str = "instagram_post"
    platform: str = "instagram"
    client_id: Optional[str] = None
    source_type: str = "manual"


# ── POST /content/generate ────────────────────────────────────

@router.post("/generate")
async def generate_content_direct(req: GenerateRequest):
    """
    Generate content immediately and return the result synchronously.
    Persists to generated_content with status=draft.
    Supports personas: zenya, finch, mauro, juno.
    """
    from runtime.tasks.handlers.generate_content import handle_generate_content

    # Build a minimal task dict that matches what the handler expects
    task = {
        "id": None,
        "client_id": req.client_id or settings.sparkle_internal_client_id,
        "payload": {
            "topic": req.topic,
            "format": req.format,
            "platform": req.platform,
            "persona": req.persona,
            "source_type": req.source_type,
            "triggered_by": "generate_endpoint",
        },
    }

    try:
        result = await handle_generate_content(task)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return result


# ── GET /content/list ─────────────────────────────────────────

@router.get("/list")
async def list_content(
    limit: int = 20,
    status: Optional[str] = None,
    client_id: Optional[str] = None,
    platform: Optional[str] = None,
):
    """Return recent generated content, newest first."""
    query = (
        supabase
        .table("generated_content")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
    )

    if status:
        query = query.eq("status", status)
    if client_id:
        query = query.eq("client_id", client_id)
    if platform:
        query = query.eq("platform", platform)

    try:
        result = query.execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {"items": result.data, "count": len(result.data)}


# ── POST /content/{id}/approve ────────────────────────────────

@router.post("/{content_id}/approve")
async def approve_content(content_id: str):
    """Set content status to approved."""
    try:
        result = (
            supabase
            .table("generated_content")
            .update({
                "status": "approved",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            .eq("id", content_id)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if not result.data:
        raise HTTPException(status_code=404, detail="Content not found")

    return {"status": "approved", "id": content_id}


# ── POST /content/{id}/reject ─────────────────────────────────

@router.post("/{content_id}/reject")
async def reject_content(content_id: str):
    """Set content status to rejected."""
    try:
        result = (
            supabase
            .table("generated_content")
            .update({
                "status": "rejected",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            .eq("id", content_id)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if not result.data:
        raise HTTPException(status_code=404, detail="Content not found")

    return {"status": "rejected", "id": content_id}


# ── POST /content/schedule ────────────────────────────────────

@router.post("/schedule")
async def schedule_content(req: ScheduleRequest):
    """
    Queue content generation for a future date.
    Creates a runtime_task with task_type=generate_content and scheduled_for.
    Accepts v2 fields (platform, ContentFormat enum) natively.
    """
    # Validate format is supported on the target platform
    if not validate_format_for_platform(req.format, req.platform):
        raise HTTPException(
            status_code=400,
            detail=f"Format '{req.format.value}' is not supported on platform '{req.platform.value}'",
        )

    try:
        scheduled_iso = req.scheduled_for.isoformat()
        result = (
            supabase
            .table("runtime_tasks")
            .insert({
                "agent_id": "content-engine",
                "client_id": req.client_id or settings.sparkle_internal_client_id,
                "task_type": "generate_content",
                "payload": {
                    "triggered_by": "schedule_endpoint",
                    "topic": req.topic,
                    "format": req.format.value,
                    "platform": req.platform.value,
                    "persona": req.persona,
                    "source_type": "scheduled",
                    "scheduled_for": scheduled_iso,
                },
                "status": "pending",
                "priority": 4,
                "scheduled_for": scheduled_iso,
            })
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create scheduled task")

    task = result.data[0]
    return {
        "message": "Content generation scheduled",
        "task_id": task["id"],
        "scheduled_for": scheduled_iso,
        "topic": req.topic,
        "format": req.format.value,
        "platform": req.platform.value,
        "persona": req.persona,
    }


# ── GET /content/calendar ────────────────────────────────────

@router.get("/calendar")
async def content_calendar(
    days: int = 30,
    client_id: Optional[str] = None,
):
    """
    Return content organized by date for a calendar/timeline view.
    Groups generated_content by created_at date and includes
    pending scheduled tasks from runtime_tasks.
    """
    now = datetime.now(timezone.utc)
    since = (now - timedelta(days=days)).isoformat()

    # 1. Fetch generated content from the period
    try:
        query = (
            supabase
            .table("generated_content")
            .select("id, client_id, persona, format, platform, topic, status, source_type, created_at")
            .gte("created_at", since)
            .order("created_at", desc=True)
            .limit(200)
        )
        if client_id:
            query = query.eq("client_id", client_id)
        content_res = query.execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # 2. Fetch pending scheduled tasks (generate_content with scheduled_for)
    try:
        sched_query = (
            supabase
            .table("runtime_tasks")
            .select("id, payload, status, scheduled_for, created_at")
            .eq("task_type", "generate_content")
            .eq("status", "pending")
            .order("created_at", desc=True)
            .limit(50)
        )
        sched_res = sched_query.execute()
    except Exception:
        sched_res = type("R", (), {"data": []})()

    # 3. Group content by date
    by_date: dict[str, dict] = {}

    for item in (content_res.data or []):
        date_key = (item.get("created_at") or "")[:10]  # YYYY-MM-DD
        if not date_key:
            continue
        if date_key not in by_date:
            by_date[date_key] = {"date": date_key, "content": [], "scheduled": []}
        by_date[date_key]["content"].append(item)

    # Add scheduled tasks
    for task in (sched_res.data or []):
        payload = task.get("payload") or {}
        sched_for = payload.get("scheduled_for") or task.get("scheduled_for") or ""
        date_key = sched_for[:10] if sched_for else (task.get("created_at") or "")[:10]
        if not date_key:
            continue
        if date_key not in by_date:
            by_date[date_key] = {"date": date_key, "content": [], "scheduled": []}
        by_date[date_key]["scheduled"].append({
            "task_id": task["id"],
            "topic": payload.get("topic", ""),
            "format": payload.get("format", "post"),
            "platform": payload.get("platform", "instagram"),
            "persona": payload.get("persona", "zenya"),
            "scheduled_for": sched_for,
            "status": task["status"],
        })

    # Sort by date descending
    calendar = sorted(by_date.values(), key=lambda d: d["date"], reverse=True)

    return {
        "days": days,
        "total_content": len(content_res.data or []),
        "total_scheduled": len(sched_res.data or []),
        "calendar": calendar,
    }


# ══════════════════════════════════════════════════════════════
# v2 ENDPOINTS
# ══════════════════════════════════════════════════════════════

# ── GET /content/templates ────────────────────────────────────

@router.get("/templates")
async def get_content_templates(
    platform: Optional[str] = None,
    format: Optional[str] = None,
):
    """
    List available content templates with their structure and constraints.
    Filter by platform and/or format.
    """
    templates = list_templates()

    if platform:
        templates = [t for t in templates if t["platform"] == platform]
    if format:
        templates = [t for t in templates if t["format"] == format]

    return {
        "templates": templates,
        "count": len(templates),
        "platforms": [p.value for p in Platform],
        "formats": [f.value for f in ContentFormat],
    }


# ── GET /content/{id}/preview ─────────────────────────────────

@router.get("/{content_id}/preview")
async def preview_content(content_id: str):
    """
    Return a structured preview of a content item formatted for its target platform.
    Includes platform-specific metadata (aspect ratio, duration limits, hashtag strategy).
    """
    try:
        result = (
            supabase
            .table("generated_content")
            .select("*")
            .eq("id", content_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if not result.data:
        raise HTTPException(status_code=404, detail="Content not found")

    item = result.data[0]

    # Resolve platform (default to instagram for v1 content)
    platform_str = item.get("platform") or "instagram"
    try:
        platform = Platform(platform_str)
    except ValueError:
        platform = Platform.INSTAGRAM

    # Resolve format
    format_str = item.get("format") or "post"
    # Map v1 format names
    v1_map = {"instagram_post": "post"}
    format_str = v1_map.get(format_str, format_str)
    try:
        fmt = ContentFormat(format_str)
    except ValueError:
        fmt = ContentFormat.POST

    # Get platform constraints
    constraints = get_platform_constraints(fmt, platform)

    # Get template info
    template = get_template(fmt, platform)
    template_info = template.to_dict() if template else None

    # Build preview text based on format
    content = item.get("content") or ""
    hashtags = item.get("hashtags") or []
    preview_text = _build_preview_text(content, hashtags, fmt, platform)

    return {
        "id": content_id,
        "platform": platform.value,
        "format": fmt.value,
        "persona": item.get("persona", "zenya"),
        "topic": item.get("topic", ""),
        "content": content,
        "hashtags": hashtags,
        "status": item.get("status", "draft"),
        "created_at": item.get("created_at"),
        "platform_metadata": {
            "constraints": constraints,
            "template": template_info,
        },
        "preview_text": preview_text,
        "char_count": len(content),
        "hashtag_count": len(hashtags),
    }


# ── POST /content/generate-batch ──────────────────────────────

@router.post("/generate-batch")
async def generate_batch(req: BatchGenerateRequest):
    """
    Generate multiple content items at once from a week/multi-day plan.
    Creates one runtime_task per item, all with status=pending.
    Returns the list of created task IDs.
    """
    client_id = req.client_id or settings.sparkle_internal_client_id
    created_tasks: list[dict] = []
    errors: list[dict] = []

    for day in req.days:
        for idx, item in enumerate(day.items):
            # Validate format+platform combo
            if not validate_format_for_platform(item.format, item.platform):
                errors.append({
                    "date": day.date,
                    "index": idx,
                    "topic": item.topic,
                    "error": f"Format '{item.format.value}' not supported on '{item.platform.value}'",
                })
                continue

            # Create a scheduled task for each item
            # Schedule at 10:00 BRT (13:00 UTC) by default for the target date
            scheduled_iso = f"{day.date}T13:00:00+00:00"

            try:
                result = (
                    supabase
                    .table("runtime_tasks")
                    .insert({
                        "agent_id": "content-engine",
                        "client_id": client_id,
                        "task_type": "generate_content",
                        "payload": {
                            "triggered_by": "batch_endpoint",
                            "topic": item.topic,
                            "format": item.format.value,
                            "platform": item.platform.value,
                            "persona": item.persona,
                            "source_type": "batch",
                            "scheduled_for": scheduled_iso,
                            "batch_date": day.date,
                        },
                        "status": "pending",
                        "priority": 5,
                        "scheduled_for": scheduled_iso,
                    })
                    .execute()
                )
                if result.data:
                    task = result.data[0]
                    created_tasks.append({
                        "task_id": task.get("id"),
                        "date": day.date,
                        "topic": item.topic,
                        "format": item.format.value,
                        "platform": item.platform.value,
                        "persona": item.persona,
                    })
            except Exception as exc:
                errors.append({
                    "date": day.date,
                    "index": idx,
                    "topic": item.topic,
                    "error": str(exc),
                })

    return {
        "message": f"Batch created: {len(created_tasks)} tasks scheduled, {len(errors)} errors",
        "tasks": created_tasks,
        "errors": errors,
        "total_scheduled": len(created_tasks),
        "total_errors": len(errors),
    }


# ── Helpers ──────────────────────────────────────────────────

def _build_preview_text(
    content: str,
    hashtags: list[str],
    fmt: ContentFormat,
    platform: Platform,
) -> str:
    """Build a human-readable preview string for a content item."""
    meta = PLATFORM_METADATA.get(platform, {})
    max_caption = meta.get("max_caption_length", 2200)

    lines: list[str] = []

    # Header
    lines.append(f"--- {platform.value.upper()} | {fmt.value.upper()} ---")
    lines.append("")

    # Truncate content for preview if too long
    if len(content) > 500:
        preview_content = content[:500] + "..."
    else:
        preview_content = content

    lines.append(preview_content)

    # Hashtags
    if hashtags:
        hashtag_strategy = meta.get("hashtag_strategy", {})
        max_tags = hashtag_strategy.get("recommended", 10)
        tags_to_show = hashtags[:max_tags]
        lines.append("")
        lines.append(" ".join(f"#{h}" for h in tags_to_show))
        if len(hashtags) > max_tags:
            lines.append(f"  (+{len(hashtags) - max_tags} mais)")

    # Character count warning
    if len(content) > max_caption:
        lines.append("")
        lines.append(f"[AVISO: {len(content)} chars — excede limite de {max_caption}]")

    return "\n".join(lines)




# ══════════════════════════════════════════════════════════════
# COPY SPECIALIST (CONTENT-1.4)
# ══════════════════════════════════════════════════════════════

class CopyBriefRequest(BaseModel):
    theme: str
    mood: str
    style: str
    platform: str = "instagram"
    include_narration: bool = True
    client_id: Optional[str] = None


class CopyApplyRequest(CopyBriefRequest):
    pass


@router.post("/copy/generate")
async def generate_copy_endpoint(req: CopyBriefRequest):
    """Gera caption + voice_script para a Zenya via Copy Specialist."""
    from runtime.content.copy_specialist import generate_copy
    try:
        result = await generate_copy(
            theme=req.theme,
            mood=req.mood,
            style=req.style,
            platform=req.platform,
            include_narration=req.include_narration,
            client_id=req.client_id or settings.sparkle_internal_client_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return result


@router.post("/copy/apply/{content_piece_id}")
async def apply_copy_endpoint(content_piece_id: str, req: CopyApplyRequest):
    """Gera copy e persiste em content_pieces."""
    from runtime.content.copy_specialist import apply_copy_to_piece
    # Verificar se o piece existe
    check = supabase.table("content_pieces").select("id").eq("id", content_piece_id).execute()
    if not check.data:
        raise HTTPException(status_code=404, detail="content_piece não encontrado")
    try:
        result = await apply_copy_to_piece(
            content_piece_id=content_piece_id,
            theme=req.theme,
            mood=req.mood,
            style=req.style,
            platform=req.platform,
            include_narration=req.include_narration,
            client_id=req.client_id or settings.sparkle_internal_client_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return result


# ══════════════════════════════════════════════════════════════
# VOICE GENERATOR (CONTENT-1.4)
# ══════════════════════════════════════════════════════════════

class VoiceGenerateRequest(BaseModel):
    voice_script: Optional[str] = None


class VoiceApplyRequest(BaseModel):
    voice_script: Optional[str] = None


@router.post("/voice/generate")
async def generate_voice_endpoint(req: VoiceGenerateRequest):
    """Gera áudio MP3 via ElevenLabs com a voz da Zenya."""
    from runtime.content.voice_generator import generate_voice_for_piece
    # voice_script obrigatório no body (pode ser null explicitamente)
    if "voice_script" not in req.model_fields_set and req.voice_script is None:
        raise HTTPException(status_code=422, detail="voice_script é obrigatório")
    if req.voice_script is not None and req.voice_script.strip() == "":
        raise HTTPException(status_code=400, detail="voice_script não pode ser string vazia")
    import uuid as _uuid
    tmp_id = str(_uuid.uuid4())
    try:
        audio_url = await generate_voice_for_piece(
            content_piece_id=tmp_id,
            voice_script=req.voice_script,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"audio_url": audio_url}


@router.post("/voice/apply/{content_piece_id}")
async def apply_voice_endpoint(content_piece_id: str, req: VoiceApplyRequest):
    """Gera áudio e persiste audio_url em content_pieces."""
    from runtime.content.voice_generator import generate_voice_for_piece
    check = supabase.table("content_pieces").select("id").eq("id", content_piece_id).execute()
    if not check.data:
        raise HTTPException(status_code=404, detail="content_piece não encontrado")
    if req.voice_script is not None and req.voice_script.strip() == "":
        raise HTTPException(status_code=400, detail="voice_script não pode ser string vazia")
    try:
        audio_url = await generate_voice_for_piece(
            content_piece_id=content_piece_id,
            voice_script=req.voice_script,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"audio_url": audio_url}


@router.get("/voice/status")
async def voice_status_endpoint():
    """Status do engine TTS para a Zenya (ElevenLabs voice ID configurado)."""
    from runtime.utils.tts import get_tts_info
    info = get_tts_info()
    info["zenya_voice_id"] = settings.elevenlabs_zenya_voice_id or None
    return info

# ══════════════════════════════════════════════════════════════
# IMAGE GENERATOR (CONTENT-1.2)
# ══════════════════════════════════════════════════════════════

class ImageGenerateRequest(BaseModel):
    theme: str
    mood: str
    style: str = "influencer_natural"
    client_id: Optional[str] = None


class ImageApplyRequest(ImageGenerateRequest):
    pass


@router.post("/image/generate")
async def generate_image_endpoint(req: ImageGenerateRequest):
    """
    Gera imagem da Zenya via Gemini Image API.
    Seleciona referência Tier A da Style Library automaticamente.
    Retorna image_url (Supabase Storage) ou erro 400/500.
    """
    from runtime.content.image_engineer import prepare_generation, get_tier_a_reference, build_prompt
    from runtime.content.image_generator import generate_image_gemini
    import uuid as _uuid

    if req.style not in ("cinematic", "influencer_natural"):
        raise HTTPException(status_code=400, detail="style deve ser 'cinematic' ou 'influencer_natural'")

    try:
        ref = await get_tier_a_reference(req.style)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    prompt = build_prompt(req.theme, req.mood, req.style)
    ref_url = ref.get("storage_path") or ref.get("image_url")

    try:
        from runtime.content.image_generator import generate_image_gemini, CONTENT_BUCKET
        image_bytes = await generate_image_gemini(prompt, ref_url)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Gemini Image error: {exc}")

    # Salvar com UUID temporário
    tmp_id = str(_uuid.uuid4())
    path = f"images/{tmp_id}.png"
    supabase.storage.from_(CONTENT_BUCKET).upload(
        path=path,
        file=image_bytes,
        file_options={"content-type": "image/png", "upsert": "true"},
    )
    image_url = supabase.storage.from_(CONTENT_BUCKET).get_public_url(path)

    return {
        "image_url": image_url,
        "style": req.style,
        "style_ref_id": ref["id"],
        "prompt_preview": prompt[:200],
    }


@router.post("/image/apply/{content_piece_id}")
async def apply_image_endpoint(content_piece_id: str, req: ImageApplyRequest):
    """
    Gera imagem e persiste image_url + status em content_pieces.
    Requer content_piece existente.
    """
    from runtime.content.image_engineer import prepare_generation
    from runtime.content.image_generator import generate_image_for_piece

    check = supabase.table("content_pieces").select("id").eq("id", content_piece_id).execute()
    if not check.data:
        raise HTTPException(status_code=404, detail="content_piece não encontrado")

    if req.style not in ("cinematic", "influencer_natural"):
        raise HTTPException(status_code=400, detail="style deve ser 'cinematic' ou 'influencer_natural'")

    try:
        gen_data = await prepare_generation(content_piece_id, req.theme, req.mood, req.style)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    ref_url = gen_data["reference"].get("storage_path") or gen_data["reference"].get("image_url")
    image_url = await generate_image_for_piece(
        content_piece_id=content_piece_id,
        prompt=gen_data["prompt"],
        reference_image_url=ref_url,
    )

    if image_url is None:
        # Falha registrada no content_piece — buscar error_log
        result = supabase.table("content_pieces").select("error_log, status").eq(
            "id", content_piece_id
        ).execute()
        info = result.data[0] if result.data else {}
        raise HTTPException(status_code=500, detail={
            "message": "Falha na geração de imagem",
            "status": info.get("status"),
            "error_log": info.get("error_log"),
        })

    return {"image_url": image_url, "content_piece_id": content_piece_id}


@router.get("/image/status")
async def image_status_endpoint():
    """Status do engine de geração de imagem (Gemini)."""
    key_configured = bool(settings.gemini_api_key)
    return {
        "engine": "Google Gemini Image",
        "model": "gemini-2.0-flash-exp-image-generation",
        "fallback_model": "imagen-3.0-generate-002",
        "gemini_api_key_configured": key_configured,
        "status": "ready" if key_configured else "unconfigured",
    }


# ══════════════════════════════════════════════════════════════
# VIDEO GENERATOR (CONTENT-1.3)
# ══════════════════════════════════════════════════════════════

class VideoGenerateRequest(BaseModel):
    image_url: str
    style: str = "influencer_natural"
    theme: Optional[str] = None
    content_piece_id: Optional[str] = None


class VideoApplyRequest(BaseModel):
    image_url: str
    style: str = "influencer_natural"
    theme: Optional[str] = None


@router.post("/video/generate")
async def generate_video_endpoint(req: VideoGenerateRequest):
    """
    Gera vídeo 9:16 via Google Veo a partir de uma imagem.
    Retorna video_url (Supabase Storage).
    """
    from runtime.content.video_engineer import build_video_prompt, get_video_duration
    from runtime.content.video_generator import generate_video_for_piece, VeoVideoGenerator
    import uuid as _uuid

    if req.style not in ("cinematic", "influencer_natural"):
        raise HTTPException(status_code=400, detail="style deve ser 'cinematic' ou 'influencer_natural'")

    prompt = build_video_prompt(req.style, req.theme)
    tmp_id = req.content_piece_id or str(_uuid.uuid4())

    video_url = await generate_video_for_piece(
        content_piece_id=tmp_id,
        image_url=req.image_url,
        prompt=prompt,
        style=req.style,
    )

    if video_url is None:
        raise HTTPException(status_code=500, detail="Falha na geração de vídeo — verifique GEMINI_API_KEY e acesso ao Veo")

    return {
        "video_url": video_url,
        "style": req.style,
        "duration_seconds": get_video_duration(req.style),
    }


@router.post("/video/apply/{content_piece_id}")
async def apply_video_endpoint(content_piece_id: str, req: VideoApplyRequest):
    """
    Gera vídeo e persiste video_url + status em content_pieces.
    """
    from runtime.content.video_engineer import build_video_prompt
    from runtime.content.video_generator import generate_video_for_piece

    check = supabase.table("content_pieces").select("id").eq("id", content_piece_id).execute()
    if not check.data:
        raise HTTPException(status_code=404, detail="content_piece não encontrado")

    if req.style not in ("cinematic", "influencer_natural"):
        raise HTTPException(status_code=400, detail="style deve ser 'cinematic' ou 'influencer_natural'")

    prompt = build_video_prompt(req.style, req.theme)
    video_url = await generate_video_for_piece(
        content_piece_id=content_piece_id,
        image_url=req.image_url,
        prompt=prompt,
        style=req.style,
    )

    if video_url is None:
        result = supabase.table("content_pieces").select("error_log, status").eq(
            "id", content_piece_id
        ).execute()
        info = result.data[0] if result.data else {}
        raise HTTPException(status_code=500, detail={
            "message": "Falha na geração de vídeo",
            "status": info.get("status"),
            "error_log": info.get("error_log"),
        })

    return {"video_url": video_url, "content_piece_id": content_piece_id}


@router.get("/video/status")
async def video_status_endpoint():
    """Status do engine de geração de vídeo (Veo)."""
    key_configured = bool(settings.gemini_api_key)
    return {
        "engine": "Google Veo",
        "model": "veo-2.0-generate-001",
        "gemini_api_key_configured": key_configured,
        "aspect_ratio": "9:16",
        "status": "ready" if key_configured else "unconfigured",
    }


# ── Style Library (CONTENT-0.1) ───────────────────────────────
from runtime.content.style_library import router as library_router
router.include_router(library_router, tags=["style-library"])
