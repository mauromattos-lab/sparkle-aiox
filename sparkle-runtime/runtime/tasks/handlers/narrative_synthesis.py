"""
narrative_synthesis handler — S9-P4: Narrative Synthesis.

Para cada entidade com >= 3 chunks no Brain, gera uma narrativa consolidada
e atualiza o campo narrative em brain_entities.

Fluxo:
  1. Busca entidades do client_id em brain_entities
  2. Para cada entidade, conta chunks com essa entidade em entity_tags
  3. Se >= 3 chunks: sintetiza narrativa via Claude Haiku
  4. Atualiza brain_entities.narrative + metadata.last_synthesized
  5. Retorna stats: {entities_processed, entities_updated, skipped}

Dependência: S9-P1 (canonicalização) deve estar funcional.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from runtime.config import settings
from runtime.db import supabase
from runtime.utils.llm import call_claude


_NARRATIVE_SYSTEM = """Você é o sintetizador de narrativa do Brain Sparkle.

Dado um conjunto de trechos sobre uma entidade (pessoa, cliente, personagem ou conceito),
gere uma narrativa coerente de 3-5 parágrafos que:

- Resume o que o sistema sabe sobre esta entidade
- Destaca padrões recorrentes, decisões tomadas e contexto atual
- É escrita em terceira pessoa, tom objetivo e informativo
- Pode ser lida por qualquer agente para entender rapidamente quem/o que é esta entidade
- NÃO inventa informações — usa apenas o que está nos trechos

Formato: texto corrido, sem bullet points, sem cabeçalhos."""


async def handle_narrative_synthesis(task: dict) -> dict:
    """
    Sintetiza narrativas para entidades com >= 3 chunks no Brain.
    """
    payload = task.get("payload", {})
    task_id = task.get("id")
    client_id = task.get("client_id") or settings.sparkle_internal_client_id
    target_entity = payload.get("entity_name")  # opcional: sintetiza só uma entidade
    min_chunks = payload.get("min_chunks", 3)

    # Busca entidades
    try:
        query = supabase.table("brain_entities").select("id,canonical_name,aliases")
        query = query.eq("client_id", client_id)
        if target_entity:
            query = query.eq("canonical_name", target_entity)

        entities_result = await asyncio.to_thread(lambda: query.execute())
        entities = entities_result.data or []
    except Exception as e:
        return {"error": f"Falha ao buscar brain_entities: {e}"}

    processed = 0
    updated = 0
    skipped = 0

    for entity in entities:
        entity_id = entity["id"]
        entity_name = entity["canonical_name"]
        processed += 1

        # Conta e busca chunks desta entidade
        try:
            # schema produção: raw_content, entity_tags está em chunk_metadata
            chunks_result = await asyncio.to_thread(
                lambda: supabase.table("brain_chunks")
                .select("raw_content,canonical_content,created_at,chunk_metadata")
                .is_("client_id", "null")
                .order("created_at", desc=False)
                .limit(30)
                .execute()
            )
            # Filtra chunks que mencionam a entidade no chunk_metadata.entity_tags
            all_chunks = chunks_result.data or []
            chunks = [
                c for c in all_chunks
                if entity_name in (c.get("chunk_metadata") or {}).get("entity_tags", [])
                or entity_name.lower() in (c.get("raw_content") or "").lower()
            ]
        except Exception as e:
            print(f"[narrative_synthesis] falha ao buscar chunks para {entity_name}: {e}")
            skipped += 1
            continue

        if len(chunks) < min_chunks:
            skipped += 1
            continue

        # Sintetiza narrativa
        corpus = "\n\n---\n\n".join([
            c.get("canonical_content") or c.get("raw_content", "") for c in chunks
        ])

        try:
            narrative = await call_claude(
                prompt=(
                    f"Entidade: {entity_name}\n\n"
                    f"Trechos do Brain:\n\n{corpus[:6000]}"
                ),
                system=_NARRATIVE_SYSTEM,
                model="claude-haiku-4-5-20251001",
                client_id=client_id,
                task_id=task_id,
                agent_id="brain",
                purpose="narrative_synthesis",
                max_tokens=800,
            )
        except Exception as e:
            print(f"[narrative_synthesis] falha na síntese para {entity_name}: {e}")
            skipped += 1
            continue

        # Atualiza brain_entities.narrative
        try:
            now = datetime.now(timezone.utc).isoformat()
            await asyncio.to_thread(
                lambda: supabase.table("brain_entities")
                .update({
                    "narrative": narrative.strip(),
                    "metadata": {"last_synthesized": now, "chunk_count": len(chunks)},
                    "updated_at": now,
                })
                .eq("id", entity_id)
                .execute()
            )
            updated += 1
        except Exception as e:
            print(f"[narrative_synthesis] falha ao atualizar entidade {entity_name}: {e}")
            skipped += 1

    return {
        "message": (
            f"Narrative Synthesis concluída.\n"
            f"Entidades processadas: {processed}\n"
            f"Narrativas atualizadas: {updated}\n"
            f"Puladas (< {min_chunks} chunks ou erro): {skipped}"
        ),
        "processed": processed,
        "updated": updated,
        "skipped": skipped,
        "client_id": client_id,
    }
