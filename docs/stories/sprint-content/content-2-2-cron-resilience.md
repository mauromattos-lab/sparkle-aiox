---
epic: EPIC-CONTENT-WAVE2 — Domínio Conteúdo Wave 2 (Estabilização + Volume)
story: CONTENT-2.2
title: "Resiliência Cron — Stuck Pieces Timeout + Retry Automático"
status: Done
priority: P0
executor: "@dev"
sprint: Content Wave 2
prd: docs/prd/domain-content-wave2-prd.md
architecture: docs/architecture/domain-content-wave2-architecture.md
squad: squads/content/
depends_on: []
unblocks: [CONTENT-2.5]
estimated_effort: "3h de agente (@dev)"
---

# Story 2.2 — Resiliência Cron — Stuck Pieces Timeout + Retry Automático

**Sprint:** Content Wave 2
**Status:** `Done`
**PRD:** `docs/prd/domain-content-wave2-prd.md` — FR-W2-02
**Architecture:** `docs/architecture/domain-content-wave2-architecture.md` — FR-W2-02

> **Paralelismo:** Esta story não depende de CONTENT-2.1 e pode rodar em paralelo com ela.

---

## User Story

> Como sistema de pipeline de conteúdo,
> quero detectar automaticamente peças travadas em estados de geração por mais de 20 minutos e reprocessá-las (até 3 tentativas) ou marcá-las como falha permanente com notificação,
> para que nenhuma peça fique presa indefinidamente sem intervenção humana.

---

## Contexto Técnico

**Estado atual:**
- O `content_pipeline_tick` (a cada 5 min) processa peças em `image_generating` ou `video_generating`, mas apenas para avançar o pipeline — não detecta peças travadas.
- Se um provider (Fal.ai, Kling) trava ou falha silenciosamente, a peça permanece em `*_generating` indefinidamente.
- Não há campos `retry_count`, `failed_permanent` ou `error_reason` na tabela `content_pieces`.

**Estado alvo:**
- Migration adiciona `retry_count`, `failed_permanent`, `error_reason` em `content_pieces`.
- Novo job `content_stuck_check` (a cada 30 min, independente do pipeline_tick) detecta stuck pieces e faz retry automático.
- Após 3 retries sem sucesso: `failed_permanent = true` + notificação Friday.
- Lógica de otimistic lock no UPDATE para evitar race condition com `pipeline_tick`.

---

## Acceptance Criteria

- [x] **AC1** — Migration `migrations/015_content_pieces_resilience.sql` aplicada com sucesso: colunas `retry_count INTEGER NOT NULL DEFAULT 0`, `failed_permanent BOOLEAN NOT NULL DEFAULT FALSE`, `error_reason TEXT` adicionadas em `content_pieces`; índice `idx_content_pieces_stuck` criado em `(status, updated_at) WHERE failed_permanent = FALSE`.

- [x] **AC2** — Query de detecção de stuck pieces retorna corretamente peças com `status IN ('image_generating', 'video_generating', 'copy_generating')` E `updated_at < NOW() - INTERVAL '20 minutes'` E `failed_permanent = FALSE`. Peças com `failed_permanent = TRUE` nunca são selecionadas.

- [x] **AC3** — Para cada stuck piece com `retry_count < 3`: UPDATE usa otimistic lock (condição `WHERE id = $id AND status = $status AND updated_at = $updated_at`); se 0 rows afetadas (pipeline_tick já avançou), skip silencioso; se 1 row afetada, status é resetado conforme mapeamento: `image_generating → briefed`, `video_generating → image_done`, `copy_generating → image_done`; `retry_count` é incrementado; `error_reason = 'timeout_auto_retry'`.

- [x] **AC4** — Após resetar o status, `advance_pipeline(piece)` é chamado para reiniciar o processamento da peça imediatamente (sem aguardar próximo tick do `pipeline_tick`).

- [x] **AC5** — Para stuck piece com `retry_count >= 3`: UPDATE seta `failed_permanent = TRUE`, `status = 'image_failed'` ou `'video_failed'` (conforme status atual), `error_reason = 'max_retries_exceeded'`; Friday é notificada com mensagem contendo piece_id e número de tentativas.

- [x] **AC6** — Timeout configurável via variável de ambiente `PIPELINE_TIMEOUT_MINUTES` (default `20`); o valor é lido de `settings.pipeline_timeout_minutes` — nunca hardcoded.

- [x] **AC7** — Novo job `content_stuck_check` registrado em `register_content_jobs()` com `IntervalTrigger(minutes=30)` e `id="content_stuck_check"`; decorado com `@log_cron("content_stuck_check")`; roda como job **separado** do `content_pipeline_tick` (não dentro do loop existente).

- [x] **AC8** — `runtime/config.py` atualizado com campo `pipeline_timeout_minutes: int = int(os.environ.get("PIPELINE_TIMEOUT_MINUTES", "20"))`.

---

## Dev Notes

### Query de detecção de stuck pieces

```sql
SELECT id, status, retry_count, updated_at
FROM content_pieces
WHERE status IN ('image_generating', 'video_generating', 'copy_generating')
  AND updated_at < NOW() - INTERVAL '20 minutes'
  AND failed_permanent = FALSE
```

O valor `20 minutes` deve ser substituído pelo valor de `settings.pipeline_timeout_minutes` ao montar a query.

### Mapeamento de status para retry

```
image_generating → briefed
video_generating → image_done
copy_generating  → image_done
```

### Fluxo de retry (pseudocódigo)

```
Para cada stuck piece:
  SE retry_count < 3:
    UPDATE com otimistic lock:
      SET status = RETRY_FROM[piece.status],
          retry_count = retry_count + 1,
          error_reason = 'timeout_auto_retry',
          updated_at = now()
      WHERE id = piece.id
        AND status = piece.status
        AND updated_at = piece.updated_at
    SE 0 rows afetadas → skip (pipeline_tick agiu primeiro)
    SE 1 row afetada → chamar advance_pipeline(piece_atualizado)
  SENÃO (retry_count >= 3):
    UPDATE:
      SET status = f'{domain}_failed',   -- image_failed ou video_failed
          failed_permanent = TRUE,
          error_reason = 'max_retries_exceeded',
          updated_at = now()
    Notificar Friday: "⚠️ Piece {piece_id[:8]} atingiu limite de retries ({retry_count}). Falha permanente."
```

### Registro do job em register_content_jobs()

```python
@log_cron("content_stuck_check")
async def _run_content_stuck_check() -> None:
    """Detecta stuck pieces e faz retry automático (max 3x) ou marca failed_permanent."""
    ...

# Em register_content_jobs():
scheduler.add_job(
    _run_content_stuck_check,
    trigger=IntervalTrigger(minutes=30),
    id="content_stuck_check",
    replace_existing=True,
)
```

### Migration 015_content_pieces_resilience.sql

```sql
ALTER TABLE content_pieces
    ADD COLUMN IF NOT EXISTS retry_count      INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS failed_permanent BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS error_reason     TEXT;

CREATE INDEX IF NOT EXISTS idx_content_pieces_stuck
    ON content_pieces (status, updated_at)
    WHERE failed_permanent = FALSE;

COMMENT ON COLUMN content_pieces.retry_count IS
    'Número de tentativas de retry automático por timeout. Max 3.';
COMMENT ON COLUMN content_pieces.failed_permanent IS
    'TRUE quando retry_count >= 3. Piece não será reprocessada automaticamente.';
COMMENT ON COLUMN content_pieces.error_reason IS
    'Causa técnica da falha (timeout_auto_retry, max_retries_exceeded, etc.)';
```

### Risco: Race condition com pipeline_tick

O `pipeline_tick` roda a cada 5 min. O `stuck_check` roda a cada 30 min. Uma peça pode ser avançada pelo `pipeline_tick` entre a SELECT e o UPDATE do `stuck_check`. O otimistic lock (AC3) resolve: se UPDATE retornar 0 rows, a peça já foi movida — skip silencioso, sem erro.

---

## Integration Verifications

- [ ] Inserir uma peça manualmente com `status='image_generating'` e `updated_at = now() - interval '25 minutes'` — após o próximo `content_stuck_check`, `status = 'briefed'` e `retry_count = 1`
- [ ] Após 3 resets sem avanço (forçar falha), `failed_permanent = TRUE` e `status = 'image_failed'`
- [ ] Friday recebe notificação quando `failed_permanent` é setado
- [ ] Peça com `updated_at < 20 min` (ex: 10 min atrás) não é tocada pelo stuck_check
- [ ] Peça com `failed_permanent = TRUE` nunca é processada novamente pelo stuck_check
- [ ] `PIPELINE_TIMEOUT_MINUTES=30` no .env → stuck_check usa 30 min como threshold (verificar via log)
- [ ] `pytest sparkle-runtime/tests/content/test_stuck_check.py -v` passa sem erros (após CONTENT-2.5)

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `migrations/015_content_pieces_resilience.sql` | Criar | ALTER TABLE content_pieces ADD COLUMNS retry_count, failed_permanent, error_reason + índice |
| `runtime/crons/content.py` | Modificar | Adicionar _run_content_stuck_check() com @log_cron + registrar job no register_content_jobs() |
| `runtime/config.py` | Modificar | Adicionar pipeline_timeout_minutes (int, default 20) |

---

## Dev Agent Record

**Executor:** @dev (Dex)
**Iniciado em:** 2026-04-07
**Concluído em:** 2026-04-07
**Notas de implementação:**
- Migration `015_content_pieces_resilience.sql` criada localmente e aplicada via MCP Supabase com sucesso
- `_STUCK_RETRY_FROM` e `_STUCK_FAILED_STATUS` definidos como dicts no topo da seção (fora da função) para clareza
- Threshold timestamp calculado em Python com `datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)` — Supabase Python client não suporta `NOW() - INTERVAL` diretamente
- Optimistic lock implementado com `.eq("status", cs).eq("updated_at", ua)` — se `result.data` for vazio/falsy, skip silencioso
- Falha permanente usa `_STUCK_FAILED_STATUS` para mapear `copy_generating → video_failed` (domínio de vídeo)
- `_notify_friday_permanent_failure()` extraída como função auxiliar para manter `_run_content_stuck_check()` legível
- `pipeline_timeout_minutes` adicionado em `Settings` com comentário explicativo sobre o env var correspondente

---

## QA Results

**Revisor:** @qa (Quinn)
**Data:** 2026-04-07
**Resultado:** PASS com CONCERNS

| AC | Status | Nota |
|----|--------|------|
| AC1 | PASS | Supabase confirmado via MCP: `retry_count INTEGER NOT NULL DEFAULT 0`, `failed_permanent BOOLEAN NOT NULL DEFAULT FALSE`, `error_reason TEXT NULL`. Índice `idx_content_pieces_stuck ON (status, updated_at) WHERE failed_permanent = FALSE` presente. Migration file idêntica ao spec. |
| AC2 | PASS | Query usa `.in_("status", stuck_statuses)` (lista derivada de `_STUCK_RETRY_FROM.keys()`), `.lt("updated_at", threshold_iso)`, `.eq("failed_permanent", False)`. Threshold calculado em Python com `timedelta` (correto — Supabase client não suporta `NOW() - INTERVAL` diretamente). Peças com `failed_permanent=True` excluídas pela query. |
| AC3 | PASS | Optimistic lock presente com `.eq("status", cs).eq("updated_at", ua)` no UPDATE. Skip silencioso via `if not update_result.data`. Mapeamento `_STUCK_RETRY_FROM` correto: `image_generating→briefed`, `video_generating→image_done`, `copy_generating→image_done`. `retry_count` incrementado como `rc + 1`. `error_reason="timeout_auto_retry"` setado. |
| AC4 | PASS | Re-fetch completo da peça (`SELECT * WHERE id = pid LIMIT 1`) realizado após UPDATE bem-sucedido. `await _advance(fresh_piece)` chamado somente se `fresh_piece` não for None. Ordem correta: UPDATE → re-fetch → advance. |
| AC5 | PASS com CONCERN | `failed_permanent=True`, `status=failed_status` (via `_STUCK_FAILED_STATUS`), `error_reason="max_retries_exceeded"` corretos. Notificação Friday via `_notify_friday_permanent_failure(piece_id, retry_count)` com mensagem contendo `piece_id[:8]` e `retry_count`. **CONCERN:** O UPDATE de falha permanente usa apenas `.eq("id", pid)` — sem optimistic lock. Se `pipeline_tick` avançar a peça entre a SELECT e este UPDATE (janela ~ms), o novo status legítimo será sobrescrito por `image_failed`/`video_failed`. Probabilidade baixa (peça com `retry_count=3` em window estreita), mas o retry path tem lock e o fail-permanent não — inconsistência de design. Sugestão: adicionar `.eq("status", current_status)` ao UPDATE de falha permanente. Não bloqueia aprovação. |
| AC6 | PASS | `settings.pipeline_timeout_minutes` usado na linha 183 de `content.py`. Configurável via `PIPELINE_TIMEOUT_MINUTES` env var com default `20` em `config.py` linha 84. Nunca hardcoded. |
| AC7 | PASS | `@log_cron("content_stuck_check")` presente. `IntervalTrigger(minutes=30)`, `id="content_stuck_check"`, `replace_existing=True` registrados em `register_content_jobs()`. Job separado do `content_pipeline_tick` (não dentro do loop existente). |
| AC8 | PASS | `pipeline_timeout_minutes: int = int(os.environ.get("PIPELINE_TIMEOUT_MINUTES", "20"))` em `Settings` com comentário explicativo. Padrão Pydantic Settings seguido. |

**Concerns (não bloqueantes):**
1. **AC5 — Optimistic lock ausente no fail-permanent path:** O UPDATE de `retry_count >= 3` não inclui `.eq("status", current_status)`, criando assimetria com o retry path. Risco real mas de baixa probabilidade. Recomenda-se adicionar em próxima iteração.

**Verificações de infraestrutura:**
- Supabase (MCP): colunas e índice confirmados em produção.
- `content.py`: implementação completa, estrutura limpa, dicts de mapeamento no escopo do módulo, auxiliar `_notify_friday_permanent_failure()` extraída corretamente.
- `config.py`: campo adicionado com comentário bilíngue adequado.
- `migrations/015_content_pieces_resilience.sql`: DDL exato ao spec da story.
