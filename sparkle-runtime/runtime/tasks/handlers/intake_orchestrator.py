"""
Handler intake_orchestrator — ONB-2: Orquestrador do intake automático.

Dispara em PARALELO (AC-5.1):
  1. Scrape do site do cliente (reutiliza brain_ingest_pipeline)
  2. Scrape do Instagram via Apify (scrape_instagram handler)
  3. Formulário WhatsApp sequencial (intake_form_whatsapp handler)

Consolida resultados progressivamente assim que qualquer fonte retornar (AC-5.2).

Integração com pipeline de onboarding:
- Chamado automaticamente quando a fase 'intake' inicia (gate 1 passou).
- Lê dados do cliente via client_id na tabela clients.
"""
from __future__ import annotations

import asyncio
from typing import Optional

from runtime.db import supabase
from runtime.onboarding.consolidator import consolidate_intake


async def _get_client_data(client_id: str) -> dict:
    """Busca dados do cliente no Supabase."""
    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("clients")
            .select("id,name,website,instagram,whatsapp,niche")
            .eq("id", client_id)
            .maybe_single()
            .execute()
        )
        return result.data if result and result.data else {}
    except Exception as e:
        print(f"[intake_orchestrator] falha ao buscar cliente {client_id}: {e}")
        return {}


async def _run_site_scrape(client_id: str, site_url: Optional[str]) -> dict:
    """
    AC-1.1: Dispara brain_ingest_pipeline para o site do cliente.
    AC-1.2: Falha graciosamente se URL vazia ou inacessível.
    AC-1.3: Dados salvos em brain_raw_ingestions + brain_chunks.
    """
    if not site_url:
        print(f"[intake_orchestrator] site_url vazio — skip (client_id={client_id})")
        return {"skipped": True, "reason": "site_url nao fornecido", "chunks_inserted": 0, "scrape_site_failed": False}

    # Normaliza URL
    if not site_url.startswith(("http://", "https://")):
        site_url = "https://" + site_url

    from runtime.tasks.handlers.brain_ingest_pipeline import handle_brain_ingest_pipeline

    task = {
        "id": f"intake-site-{client_id}",
        "client_id": client_id,
        "payload": {
            "source_type": "website",
            "source_ref": site_url,
            "title": f"Site do cliente — onboarding",
            "persona": "cliente",
            "run_dna": True,
            "run_insights": False,
            "run_narrative": False,
            "run_synthesis": False,
        },
    }

    try:
        result = await handle_brain_ingest_pipeline(task)
        chunks = result.get("chunks_inserted", 0)
        if chunks == 0 and "error" in result:
            print(f"[intake_orchestrator] site scrape falhou: {result.get('error')}")
            return {"skipped": False, "scrape_site_failed": True, "chunks_inserted": 0, "error": result.get("error")}

        print(f"[intake_orchestrator] site scrape OK: {chunks} chunks para {site_url}")
        return {
            "skipped": False,
            "scrape_site_failed": False,
            "chunks_inserted": chunks,
            "title": result.get("brain_content", ""),
        }
    except Exception as e:
        # AC-1.2: falha graciosa, não bloqueia pipeline
        print(f"[intake_orchestrator] site scrape exception: {e}")
        return {"skipped": False, "scrape_site_failed": True, "chunks_inserted": 0, "error": str(e)[:200]}


async def _run_instagram_scrape(client_id: str, instagram_url: Optional[str]) -> dict:
    """
    AC-2.1 a 2.4: Scrape Instagram via Apify.
    Pula silenciosamente se instagram_url vazio.
    """
    from runtime.tasks.handlers.scrape_instagram import handle_scrape_instagram

    task = {
        "id": f"intake-instagram-{client_id}",
        "client_id": client_id,
        "payload": {
            "client_id": client_id,
            "instagram_url": instagram_url or "",
        },
    }
    try:
        return await handle_scrape_instagram(task)
    except Exception as e:
        print(f"[intake_orchestrator] instagram scrape exception: {e}")
        return {"skipped": False, "error": str(e)[:200], "chunks_inserted": 0}


async def _run_form_whatsapp(
    client_id: str,
    phone: Optional[str],
    business_type: Optional[str],
    client_name: Optional[str],
) -> dict:
    """
    AC-3.x: Inicia formulário WhatsApp sequencial.
    AC-3.7: Pula se phone vazio.
    """
    from runtime.tasks.handlers.intake_form_whatsapp import handle_intake_form_whatsapp

    task = {
        "id": f"intake-form-{client_id}",
        "client_id": client_id,
        "payload": {
            "action": "start",
            "client_id": client_id,
            "phone": phone or "",
            "business_type": business_type or "generico",
            "client_name": client_name or "",
        },
    }
    try:
        return await handle_intake_form_whatsapp(task)
    except Exception as e:
        print(f"[intake_orchestrator] form whatsapp exception: {e}")
        return {"skipped": False, "error": str(e)[:200]}


async def handle_intake_orchestrator(task: dict) -> dict:
    """
    Orquestrador principal do intake (ONB-2).

    Payload:
    {
        "client_id": "..."   // obrigatório
    }

    Lê dados de clients (website, instagram, whatsapp, niche) e dispara
    scrape de site, scrape de Instagram e formulário WhatsApp em PARALELO.
    """
    payload = task.get("payload", {})
    client_id: Optional[str] = payload.get("client_id") or task.get("client_id")

    if not client_id:
        return {"error": "client_id obrigatorio"}

    # Busca dados do cliente
    client = await _get_client_data(client_id)
    if not client:
        return {"error": f"cliente nao encontrado: {client_id}"}

    site_url = client.get("website", "") or payload.get("site_url", "")
    instagram_url = client.get("instagram", "") or payload.get("instagram_url", "")
    phone = client.get("whatsapp", "") or payload.get("phone", "")
    business_type = client.get("niche", "generico") or payload.get("business_type", "generico")
    client_name = client.get("name", "")

    print(
        f"[intake_orchestrator] Iniciando intake PARALELO para {client_name} "
        f"(client_id={client_id[:12]}...)"
    )

    # AC-5.1: Dispara tudo em paralelo
    site_result, instagram_result, form_result = await asyncio.gather(
        _run_site_scrape(client_id, site_url),
        _run_instagram_scrape(client_id, instagram_url),
        _run_form_whatsapp(client_id, phone, business_type, client_name),
        return_exceptions=False,
    )

    # AC-5.2: Consolida assim que qualquer fonte tiver dados
    # (gather já esperou todas, mas cada fonte pode ter chegado em momentos diferentes)
    has_site_data = not site_result.get("scrape_site_failed") and site_result.get("chunks_inserted", 0) > 0
    has_instagram_data = not instagram_result.get("skipped") and instagram_result.get("chunks_inserted", 0) > 0
    form_complete = form_result.get("completed", False)
    form_partial = form_result.get("partial", False)

    # Form foi iniciado (não concluído ainda — usuário vai responder depois)
    # intake_form tem respostas apenas quando action=answer é chamado pelo webhook
    form_answers = []  # Respostas virão via webhook quando usuário responder

    summary = await consolidate_intake(
        client_id=client_id,
        site_data=site_result if has_site_data else None,
        instagram_data=instagram_result if has_instagram_data else None,
        form_answers=form_answers,
        form_complete=form_complete,
        form_partial=form_partial,
    )

    intake_complete = summary.get("intake_complete", False)
    score = summary.get("completeness_score", 0)

    print(
        f"[intake_orchestrator] Intake concluido para {client_id[:12]}... "
        f"score={score}% intake_complete={intake_complete}"
    )

    return {
        "status": "ok",
        "client_id": client_id,
        "client_name": client_name,
        "site": site_result,
        "instagram": instagram_result,
        "form": form_result,
        "intake_summary": summary,
        "completeness_score": score,
        "intake_complete": intake_complete,
        "message": (
            f"Intake iniciado para '{client_name}'. "
            f"Score atual: {score}% (site: {'ok' if has_site_data else 'skip'}, "
            f"instagram: {'ok' if has_instagram_data else 'skip'}, "
            f"form: {'enviado' if form_result.get('started') else 'skip'}). "
            f"intake_complete={intake_complete}"
        ),
    }
