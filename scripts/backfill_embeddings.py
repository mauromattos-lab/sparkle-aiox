#!/usr/bin/env python3
"""
Backfill de embeddings para chunks sem embedding em brain_chunks.

Rodar no VPS APÓS P1 estar validado e BRAIN_EMBEDDINGS_ENABLED=true:
  cd /opt/sparkle-runtime/sparkle-runtime
  python scripts/backfill_embeddings.py --dry-run   # estima custo, não executa
  python scripts/backfill_embeddings.py             # executa de fato

Regras:
- Processa em batches de 10 para não estourar rate limit OpenAI
- Pausa 1s entre batches
- Alerta se custo estimado > $1 antes de prosseguir
- Log de progresso a cada batch
- Requer BRAIN_EMBEDDINGS_ENABLED=true e OPENAI_API_KEY configuradas
"""
import asyncio
import os
import sys

# Adicionar runtime ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runtime.db import supabase
from runtime.utils.embeddings import generate_embedding, estimate_cost_usd

BATCH_SIZE = 10
BATCH_PAUSE_SECS = 1.0


async def main():
    dry_run = "--dry-run" in sys.argv

    # Verificar pré-condições
    embeddings_enabled = os.getenv("BRAIN_EMBEDDINGS_ENABLED", "false").lower() in ("true", "1", "yes")
    if not embeddings_enabled and not dry_run:
        print("[backfill] ERRO: BRAIN_EMBEDDINGS_ENABLED não está habilitado.")
        print("[backfill] Configure BRAIN_EMBEDDINGS_ENABLED=true no .env antes de executar o backfill real.")
        print("[backfill] Para dry-run de estimativa de custo, rode: python scripts/backfill_embeddings.py --dry-run")
        sys.exit(1)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key and not dry_run:
        print("[backfill] ERRO: OPENAI_API_KEY não configurada no .env.")
        sys.exit(1)

    # Buscar chunks sem embedding
    result = supabase.table("brain_chunks").select(
        "id, raw_content, canonical_content"
    ).is_("embedding", "null").execute()

    chunks = result.data or []
    total = len(chunks)

    if total == 0:
        print("[backfill] Todos os chunks já têm embedding. Nada a fazer.")
        return

    # Calcular custo estimado
    total_chars = sum(
        len(c.get("canonical_content") or c.get("raw_content") or "")
        for c in chunks
    )
    estimated_cost = await estimate_cost_usd(total_chars)

    print(f"[backfill] {total} chunks sem embedding")
    print(f"[backfill] ~{total_chars:,} chars totais")
    print(f"[backfill] Custo estimado: ${estimated_cost:.4f} USD (model=text-embedding-3-small @ $0.02/1M tokens)")
    print(f"[backfill] Batches: {(total + BATCH_SIZE - 1) // BATCH_SIZE} × {BATCH_SIZE} chunks, pausa={BATCH_PAUSE_SECS}s entre batches")

    if estimated_cost > 1.0:
        print(f"[backfill] ALERTA: custo estimado ${estimated_cost:.4f} > $1.00. Confirmar com Mauro antes de prosseguir.")
        if not dry_run:
            confirm = input("Continuar? (s/N): ")
            if confirm.lower() != "s":
                print("[backfill] Abortado.")
                return

    if dry_run:
        print()
        print("[backfill] ─── DRY RUN CONCLUÍDO ───────────────────────────────────")
        print(f"[backfill] Chunks a processar : {total}")
        print(f"[backfill] Total de chars      : {total_chars:,}")
        print(f"[backfill] Custo estimado      : ${estimated_cost:.6f} USD")
        print(f"[backfill] Custo real máximo   : ${estimated_cost * 1.2:.6f} USD (margem 20%)")
        print("[backfill] Nenhum embedding foi gerado. Remova --dry-run para executar.")
        return

    # Processar em batches
    success = 0
    failed = 0
    skipped = 0

    print()
    print(f"[backfill] Iniciando backfill de {total} chunks...")
    print()

    for i in range(0, total, BATCH_SIZE):
        batch = chunks[i: i + BATCH_SIZE]
        batch_ok = 0
        batch_fail = 0

        for chunk in batch:
            chunk_id = chunk["id"]
            content = chunk.get("canonical_content") or chunk.get("raw_content") or ""
            if not content.strip():
                print(f"[backfill]   skip chunk {chunk_id} — conteúdo vazio")
                skipped += 1
                continue

            embedding = await generate_embedding(content)
            if embedding:
                try:
                    supabase.table("brain_chunks").update(
                        {"embedding": embedding}
                    ).eq("id", chunk_id).execute()
                    success += 1
                    batch_ok += 1
                except Exception as e:
                    print(f"[backfill]   WARNING: falha ao salvar embedding para {chunk_id}: {e}")
                    failed += 1
                    batch_fail += 1
            else:
                failed += 1
                batch_fail += 1
                print(f"[backfill]   WARNING: falha ao gerar embedding para {chunk_id}")

        batch_num = i // BATCH_SIZE + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
        pct = min((i + BATCH_SIZE) / total * 100, 100)
        print(f"[backfill] Batch {batch_num}/{total_batches} ({pct:.0f}%) — ok={batch_ok} fail={batch_fail} | acumulado: ok={success} fail={failed}")

        if i + BATCH_SIZE < total:
            await asyncio.sleep(BATCH_PAUSE_SECS)

    print()
    print("[backfill] ─── RESULTADO FINAL ─────────────────────────────────────")
    print(f"[backfill] Total chunks     : {total}")
    print(f"[backfill] Embeddings ok    : {success}")
    print(f"[backfill] Falhas           : {failed}")
    print(f"[backfill] Skipped (vazio)  : {skipped}")
    custo_real = await estimate_cost_usd(total_chars)
    print(f"[backfill] Custo estimado   : ${custo_real:.6f} USD")
    print()

    if failed > 0:
        print(f"[backfill] ATENÇÃO: {failed} chunk(s) sem embedding após backfill. Verificar OPENAI_API_KEY e logs acima.")
        sys.exit(2)
    else:
        print("[backfill] Backfill concluído com sucesso. 100% dos chunks têm embedding.")


if __name__ == "__main__":
    asyncio.run(main())
