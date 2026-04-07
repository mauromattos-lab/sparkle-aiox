---
epic: EPIC-BRAIN — Brain como Circulação Real
story: BRAIN-CURATE-01
title: "Brain Curate Scale Fix — Batch Size + Cron Dedup + Review Queue UI"
status: Ready for Dev
priority: P0
executor: "@dev"
sprint: sprint-core
prd: null
architecture: docs/architecture/sparkle-aiox-brownfield-architecture-2026-04.md
squad: null
depends_on: []
unblocks: [FRIDAY-CONTEXTUAL, CONTENT-WAVE2]
estimated_effort: "1h de agente (@dev)"
next_agent: "@qa"
next_command: "*review docs/stories/sprint-core/brain-curate-scale-fix.md"
next_gate: "qa_review"
---

# Story BRAIN-CURATE-01 — Brain Curate Scale Fix

**Sprint:** sprint-core
**Status:** `Ready for Dev`
**Architecture:** `docs/architecture/sparkle-aiox-brownfield-architecture-2026-04.md`

---

## User Story

> Como sistema Sparkle,
> quero que os chunks do Brain sejam processados mais rápido do que chegam,
> para que o Brain tenha conhecimento real circulando e não acumule backlog infinito.

---

## Contexto Técnico

**Estado diagnosticado em 2026-04-07:**
- 495 chunks `pending` (acumulando desde 2026-04-03)
- 260 chunks em `review` (Haiku avaliou score 0.4-0.7, aguardam humano — invisíveis na UI)
- 9 chunks `approved`
- BATCH_SIZE=20 processa só 20 chunks por execução
- Cron duplicado: 2 instâncias rodando ao mesmo tempo (mesmo timestamp nos logs)
- Portal `/brain/curation` não exibe `review` queue por padrão — Mauro nunca vê

**Causa raiz:**
- Taxa de ingestão (~165/dia) > taxa de curadoria (~60/dia com batch=20 × 3 crons)
- 2 instâncias do mesmo cron processam o mesmo batch sem coordenação

---

## Acceptance Criteria

- [x] **AC1** — `BATCH_SIZE` em `brain_curate.py` aumentado de 20 para **50**. Com 3 execuções/dia, processa até 150 chunks/dia — acima da taxa de ingestão atual.

- [x] **AC2** — Cron `brain_curate` em `scheduler.py` auditado. Confirmado: **exatamente 1 job registrado** com id `"brain_curate"` e `replace_existing=True`. Os nomes duplicados no banco (`brain_curate_02h/10h/18h`) vêm de código antigo na VPS — serão substituídos no próximo deploy. `cron_logger.py` contém apenas docstring de exemplo, não registros reais.

- [x] **AC3** — Página `/brain/curation` no Portal atualizada: aba "Para Revisao" adicionada com count de `stats?.review`. Chunks em `review` mostram badge `[AUTO]` quando `curation_note` começa com `[auto]`. Botões aprovar/rejeitar habilitados para `review` além de `pending`. StatsBar atualizada com 5 colunas (inclui "Para Revisao"). Endpoint de stats corrigido para `/brain/curate/stats` (retorna `review` count).

- [ ] **AC4** — Verificação pós-fix: após próxima execução do cron, confirmar via Supabase que chunks `pending` diminuíram e `review`/`approved` aumentaram.

---

## Dev Notes

### Fix AC1 — BATCH_SIZE

```python
# sparkle-runtime/runtime/tasks/handlers/brain_curate.py
# Linha 27
BATCH_SIZE = 50  # era 20
```

### Fix AC2 — Dedup cron

Verificar em `scheduler.py` se `brain_curate` está sendo adicionado mais de uma vez. Buscar por `id="brain_curate"` — deve aparecer exatamente 1 vez. Se houver duplicata, remover a extra.

### Fix AC3 — Portal review queue

Em `portal/app/brain/curation/page.tsx`:

1. Estado inicial do filtro: manter `pending` como default visual, mas o fetch deve buscar `pending` E `review` juntos (ou adicionar tab `review` explícita)
2. Solução mais simples: adicionar tab `review` na lista de filtros existente (linha ~469):
```typescript
{ key: 'review' as const, label: 'Para Revisão', count: stats?.review },
```
3. Badge no ChunkCard para `review`: mostrar `[AUTO]` na nota de curadoria quando `curation_note` começa com `[auto]`
4. Atualizar `CurationStats` interface para incluir `review?: number`
5. Atualizar `loadStats` para usar `/brain/curate/stats` (que já retorna `review`) em vez de `/brain/curation/stats`

### Endpoints disponíveis (não criar novos)
- `GET /brain/curate/stats` → retorna `{pending, approved, review, rejected, total}`
- `GET /brain/curation/queue?status=review` → já funciona
- `POST /brain/curation/{id}/approve` → já funciona para qualquer status

---

## Integration Verifications

- [ ] `SELECT curation_status, COUNT(*) FROM brain_chunks GROUP BY 1` — pending decrescendo após fix
- [ ] Logs do cron: apenas 1 linha por horário de execução (não 2)
- [ ] Portal `/brain/curation`: aba "Para Revisão" visível com 260 chunks

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `sparkle-runtime/runtime/tasks/handlers/brain_curate.py` | MODIFICAR | BATCH_SIZE 20 → 50 |
| `sparkle-runtime/runtime/scheduler.py` | VERIFICAR/MODIFICAR | Remover registro duplicado de brain_curate |
| `portal/app/brain/curation/page.tsx` | MODIFICAR | Adicionar tab review + badge [AUTO] |

---

---

## Dev Agent Record

**Executor:** @dev (Dex)
**Iniciado em:** 2026-04-07
**Concluído em:** 2026-04-07
**Notas de implementação:**
- AC1: `BATCH_SIZE = 50` em `brain_curate.py` (era 20). Taxa de curadoria sobe de ~60/dia para ~150/dia com 3 crons/dia.
- AC2: Auditoria do `scheduler.py` — confirmado 1 registro único com `replace_existing=True`. Nomes duplicados no banco vêm de código VPS antigo, serão resolvidos no deploy.
- AC3: `portal/app/brain/curation/page.tsx` — 6 mudanças: (1) `CurationStats.review` field, (2) endpoint stats → `/brain/curate/stats`, (3) tipo filtro inclui `'review'`, (4) tab "Para Revisao" adicionada, (5) badge `AUTO` para notas auto-curadas, (6) botões aprovar/rejeitar habilitados para status `review`, (7) StatsBar com 5 colunas.

**File List:**
| Arquivo | Ação |
|---------|------|
| `sparkle-runtime/runtime/tasks/handlers/brain_curate.py` | MODIFICADO — BATCH_SIZE 20→50 |
| `portal/app/brain/curation/page.tsx` | MODIFICADO — tab review + badge AUTO + stats endpoint |

---

## QA Results

_(aguardando @qa)_
