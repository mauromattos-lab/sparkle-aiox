"""
cross_source_synthesis handler — Fase 6 evoluida do Brain Pipeline.

Para cada dominio com 5+ insights no Brain, gera sintese cruzada:
  1. Agrupa insights por dominio
  2. Para cada dominio com massa critica: sintetiza via Sonnet
  3. Detecta conflitos entre fontes
  4. Gera documento estruturado
  5. Desativa sintese anterior do mesmo dominio (versionamento)

Usa Sonnet (nao Haiku) porque sintese cruzada e cognitivamente complexa.
"""
from __future__ import annotations

import asyncio
import json
import os
from collections import Counter
from datetime import datetime, timezone

import httpx

from runtime.config import settings
from runtime.db import supabase
from runtime.utils.llm import call_claude


_SYNTHESIS_SYSTEM = """Voce e o sintetizador de conhecimento do Brain Sparkle.

Dado um conjunto de insights extraidos de MULTIPLAS fontes sobre um mesmo dominio,
gere uma SINTESE CRUZADA que:

1. VISAO UNIFICADA (3-5 paragrafos):
   - O que o sistema sabe sobre este dominio
   - Quais sao os consensos entre as fontes
   - Qual a abordagem recomendada baseada na convergencia

2. FRAMEWORKS DOMINANTES:
   - Liste os frameworks/processos mais relevantes com titulo e descricao curta
   - Indique de qual fonte veio cada um

3. TECNICAS-CHAVE:
   - As tecnicas mais acionaveis, com exemplo de aplicacao

4. PRINCIPIOS FUNDAMENTAIS:
   - Verdades consensuais entre as fontes

5. CONFLITOS:
   - Se duas fontes discordam em algo, registre:
     {"topic": "...", "position_a": "Fonte A diz...", "position_b": "Fonte B diz...", "resolution": null}
   - resolution pode ser null (sem resolucao), ou uma recomendacao sua baseada em evidencia

Formato de saida OBRIGATORIO (JSON):
{
  "summary": "texto corrido da visao unificada",
  "key_frameworks": [{"title": "...", "description": "...", "source": "..."}],
  "key_techniques": [{"title": "...", "description": "...", "application": "...", "source": "..."}],
  "key_principles": [{"principle": "...", "source": "..."}],
  "conflicts": [{"topic": "...", "position_a": "...", "position_b": "...", "resolution": null}]
}

REGRAS:
- NAO invente informacao. Se so ha uma fonte, nao ha conflito.
- Se as fontes concordam, destaque isso como consenso forte.
- Priorizacao: quanto mais fontes concordam, mais importante o insight.
- Responda APENAS com JSON valido."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _get_embedding(text: str) -> list[float] | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": "text-embedding-3-small", "input": text[:8000]},
                timeout=10.0,
            )
            resp.raise_for_status()
            return resp.json()["data"][0]["embedding"]
    except Exception:
        return None


def _clean_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


async def handle_cross_source_synthesis(task: dict) -> dict:
    """
    Gera sintese cruzada por dominio a partir de insights do Brain.
    Payload:
      - domain: str opcional — sintetiza so um dominio
      - min_insights: int (default 5) — minimo de insights para disparar sintese
    """
    payload = task.get("payload", {})
    task_id = task.get("id")
    client_id = task.get("client_id") or settings.sparkle_internal_client_id
    target_domain = payload.get("domain")
    min_insights = payload.get("min_insights", 5)

    # 1. Descobre dominios com massa critica
    if target_domain:
        domains_to_process = [target_domain]
    else:
        result = await asyncio.to_thread(
            lambda: supabase.table("brain_insights")
            .select("domain")
            .eq("active", True)
            .execute()
        )
        counts = Counter(r["domain"] for r in (result.data or []))
        domains_to_process = [d for d, c in counts.items() if c >= min_insights]

    processed = 0
    updated = 0
    skipped = 0

    for domain in domains_to_process:
        processed += 1

        # 2. Busca todos insights deste dominio
        insights_result = await asyncio.to_thread(
            lambda d=domain: supabase.table("brain_insights")
            .select("id,insight_type,title,content,application,source_attribution,confidence,tags")
            .eq("domain", d)
            .eq("active", True)
            .order("confidence", desc=True)
            .limit(50)
            .execute()
        )
        insights = insights_result.data or []

        if len(insights) < min_insights:
            skipped += 1
            continue

        # 3. Monta corpus para sintese
        corpus_parts = []
        for ins in insights:
            part = f"[{ins.get('insight_type', 'insight').upper()}] {ins.get('title', '')}\n{ins.get('content', '')}"
            if ins.get("application"):
                part += f"\nAplicacao: {ins['application']}"
            if ins.get("source_attribution"):
                part += f"\nFonte: {ins['source_attribution']}"
            corpus_parts.append(part)

        corpus = "\n\n---\n\n".join(corpus_parts)

        # 4. Sintetiza via Sonnet (complexidade alta)
        try:
            raw = await call_claude(
                prompt=f"Dominio: {domain}\nTotal de insights: {len(insights)}\n\nInsights:\n\n{corpus[:8000]}",
                system=_SYNTHESIS_SYSTEM,
                model="claude-sonnet-4-6",
                client_id=client_id,
                task_id=task_id,
                agent_id="brain",
                purpose="cross_source_synthesis",
                max_tokens=2000,
            )
        except Exception as e:
            print(f"[cross_source_synthesis] Sonnet falhou para dominio {domain}: {e}")
            continue

        try:
            parsed = json.loads(_clean_json(raw))
        except json.JSONDecodeError:
            print(f"[cross_source_synthesis] JSON invalido para dominio {domain}")
            continue

        # 5. Desativa sintese anterior deste dominio
        try:
            await asyncio.to_thread(
                lambda d=domain: supabase.table("brain_domain_syntheses")
                .update({"active": False, "updated_at": _now()})
                .eq("domain", d)
                .eq("active", True)
                .execute()
            )
        except Exception:
            pass  # pode nao existir sintese anterior

        # 6. Calcula versao
        try:
            version_result = await asyncio.to_thread(
                lambda d=domain: supabase.table("brain_domain_syntheses")
                .select("version")
                .eq("domain", d)
                .order("version", desc=True)
                .limit(1)
                .execute()
            )
            next_version = (version_result.data[0]["version"] + 1) if version_result.data else 1
        except Exception:
            next_version = 1

        # 7. Embedding da sintese
        summary = parsed.get("summary", "")
        embedding = await _get_embedding(summary[:3000])

        # 8. Insere nova sintese
        insight_ids = [ins["id"] for ins in insights]
        unique_sources = set(
            ins.get("source_attribution", "") for ins in insights if ins.get("source_attribution")
        )

        row: dict = {
            "domain": domain,
            "version": next_version,
            "summary": summary,
            "key_frameworks": parsed.get("key_frameworks", []),
            "key_techniques": parsed.get("key_techniques", []),
            "key_principles": parsed.get("key_principles", []),
            "conflicts": parsed.get("conflicts", []),
            "source_insight_ids": insight_ids,
            "source_count": len(unique_sources),
            "pipeline_type": "especialista",
        }
        if client_id and client_id != settings.sparkle_internal_client_id:
            row["client_id"] = client_id
        if embedding:
            row["embedding"] = embedding

        try:
            await asyncio.to_thread(
                lambda r=row: supabase.table("brain_domain_syntheses").insert(r).execute()
            )
            updated += 1
        except Exception as e:
            print(f"[cross_source_synthesis] falha ao inserir sintese {domain}: {e}")

    return {
        "message": (
            f"Cross-Source Synthesis concluida. "
            f"Dominios processados: {processed}, Atualizados: {updated}, Pulados: {skipped}"
        ),
        "processed": processed,
        "updated": updated,
        "skipped": skipped,
        "domains": domains_to_process,
    }
