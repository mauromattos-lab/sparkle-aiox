"""
Brain Domain Synthesis — W2-BRAIN-1.

Atualiza automaticamente a síntese de um domínio/namespace quando novo
conteúdo aprovado é ingerido. Usa Claude Haiku para gerar texto conciso
(máx 500 tokens) a partir dos top-20 chunks aprovados por usage_count.

Funções públicas:
  async update_domain_synthesis(namespace: str) -> bool
  async get_brain_health() -> dict
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from runtime.db import supabase
from runtime.config import settings

logger = logging.getLogger(__name__)

_MAX_SYNTHESIS_TOKENS = 500
_TOP_CHUNKS = 20


async def update_domain_synthesis(namespace: str) -> bool:
    """
    Gera síntese atualizada de um namespace via Claude Haiku e persiste
    em brain_domain_syntheses (coluna domain = namespace).

    Retorna True em sucesso, False em falha (sem propagar exceção).
    Nunca falha o fluxo de aprovação se Haiku não responder.
    """
    try:
        # Busca top-20 chunks aprovados do namespace por usage_count
        res = await asyncio.to_thread(
            lambda: supabase.table("brain_chunks")
            .select("id,content,source_title,usage_count")
            .eq("namespace", namespace)
            .eq("curation_status", "approved")
            .is_("deleted_at", "null")
            .order("usage_count", desc=True)
            .limit(_TOP_CHUNKS)
            .execute()
        )
        chunks = res.data or []

        if not chunks:
            logger.info("[synthesis] namespace=%s: sem chunks aprovados — skip", namespace)
            return False

        # Montar contexto para o Haiku
        chunks_text = "\n\n".join(
            f"[{i+1}] {c.get('source_title', 'sem título')}\n{c.get('content', '')[:600]}"
            for i, c in enumerate(chunks)
        )

        prompt = (
            f"Você é um sistema de síntese de conhecimento. "
            f"Abaixo estão os {len(chunks)} chunks de conhecimento mais relevantes "
            f"do domínio '{namespace}'.\n\n"
            f"Gere uma síntese concisa (máximo {_MAX_SYNTHESIS_TOKENS} tokens) que capture:\n"
            f"- Os temas e conceitos centrais\n"
            f"- Princípios e frameworks chave\n"
            f"- O que é mais importante neste domínio\n\n"
            f"Seja direto e factual. Não inclua introduções ou conclusões genéricas.\n\n"
            f"CHUNKS:\n{chunks_text}"
        )

        # Chama Claude Haiku
        import anthropic
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        response = await asyncio.to_thread(
            lambda: client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=_MAX_SYNTHESIS_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
        )

        synthesis_text = response.content[0].text.strip() if response.content else ""
        if not synthesis_text:
            logger.warning("[synthesis] namespace=%s: Haiku retornou texto vazio", namespace)
            return False

        # Upsert em brain_domain_syntheses (domain = namespace)
        existing_res = await asyncio.to_thread(
            lambda: supabase.table("brain_domain_syntheses")
            .select("id,version")
            .eq("domain", namespace)
            .eq("active", True)
            .limit(1)
            .execute()
        )
        existing = (existing_res.data or [None])[0]

        now = datetime.now(timezone.utc).isoformat()

        if existing:
            new_version = (existing.get("version") or 1) + 1
            await asyncio.to_thread(
                lambda: supabase.table("brain_domain_syntheses")
                .update({
                    "summary": synthesis_text,
                    "source_count": len(chunks),
                    "version": new_version,
                    "updated_at": now,
                })
                .eq("id", existing["id"])
                .execute()
            )
            logger.info(
                "[synthesis] namespace=%s: síntese atualizada v%d (%d chunks)",
                namespace, new_version, len(chunks)
            )
        else:
            await asyncio.to_thread(
                lambda: supabase.table("brain_domain_syntheses")
                .insert({
                    "domain": namespace,
                    "summary": synthesis_text,
                    "source_count": len(chunks),
                    "version": 1,
                    "active": True,
                    "pipeline_type": "auto_synthesis",
                    "created_at": now,
                    "updated_at": now,
                })
                .execute()
            )
            logger.info(
                "[synthesis] namespace=%s: síntese criada (%d chunks)",
                namespace, len(chunks)
            )

        return True

    except Exception as e:
        logger.error("[synthesis] namespace=%s: erro — %s", namespace, e)
        return False


async def get_brain_health() -> dict:
    """
    Retorna dashboard de saúde do Brain com métricas reais.
    Usado pelo endpoint GET /brain/health.
    """
    try:
        # Contagens por status
        chunks_res = await asyncio.to_thread(
            lambda: supabase.table("brain_chunks")
            .select("curation_status,namespace,created_at")
            .is_("deleted_at", "null")
            .execute()
        )
        all_chunks = chunks_res.data or []

        total = len(all_chunks)
        approved = sum(1 for c in all_chunks if c.get("curation_status") == "approved")
        pending = sum(1 for c in all_chunks if c.get("curation_status") == "pending")
        rejected = sum(1 for c in all_chunks if c.get("curation_status") == "rejected")

        # Chunks stale: approved, usage_count=0, criado há >90 dias
        from datetime import timedelta
        ninety_days_ago = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        stale_res = await asyncio.to_thread(
            lambda: supabase.table("brain_chunks")
            .select("id", count="exact")
            .eq("curation_status", "approved")
            .eq("usage_count", 0)
            .lt("created_at", ninety_days_ago)
            .is_("deleted_at", "null")
            .execute()
        )
        stale = stale_res.count if stale_res.count is not None else 0

        approval_rate = round((approved / total * 100), 1) if total > 0 else 0.0

        # Namespaces breakdown
        ns_map: dict[str, dict] = {}
        for chunk in all_chunks:
            ns = chunk.get("namespace") or "unknown"
            if ns not in ns_map:
                ns_map[ns] = {"namespace": ns, "approved": 0, "pending": 0, "last_ingested_at": None}
            status = chunk.get("curation_status")
            if status == "approved":
                ns_map[ns]["approved"] += 1
            elif status == "pending":
                ns_map[ns]["pending"] += 1
            # Track most recent ingestion
            created = chunk.get("created_at")
            if created:
                current_last = ns_map[ns]["last_ingested_at"]
                if current_last is None or created > current_last:
                    ns_map[ns]["last_ingested_at"] = created

        namespaces = sorted(ns_map.values(), key=lambda x: x["approved"], reverse=True)

        # Syntheses
        synth_res = await asyncio.to_thread(
            lambda: supabase.table("brain_domain_syntheses")
            .select("domain,updated_at")
            .eq("active", True)
            .execute()
        )
        now = datetime.now(timezone.utc)
        syntheses = []
        for s in (synth_res.data or []):
            updated_raw = s.get("updated_at") or ""
            age_hours = None
            if updated_raw:
                try:
                    updated_dt = datetime.fromisoformat(updated_raw.replace("Z", "+00:00"))
                    age_hours = round((now - updated_dt).total_seconds() / 3600, 1)
                except Exception:
                    pass
            syntheses.append({
                "namespace": s.get("domain"),
                "updated_at": updated_raw,
                "age_hours": age_hours,
            })

        # Alerts
        alerts = []
        for s in syntheses:
            if s["age_hours"] is not None and s["age_hours"] > 48:
                alerts.append(
                    f"síntese '{s['namespace']}' tem {s['age_hours']:.0f}h sem atualização"
                )
        if pending > 50:
            alerts.append(f"Brain tem {pending} chunks pendentes de curadoria")

        return {
            "total_chunks": total,
            "approved_chunks": approved,
            "pending_chunks": pending,
            "rejected_chunks": rejected,
            "stale_chunks": stale,
            "approval_rate_percent": approval_rate,
            "namespaces": namespaces,
            "syntheses": syntheses,
            "alerts": alerts,
        }

    except Exception as e:
        logger.error("[synthesis] get_brain_health error: %s", e)
        return {"error": str(e)}
