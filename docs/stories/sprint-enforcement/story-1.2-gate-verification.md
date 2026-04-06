# Story 1.2 — Gate Verification Obrigatório

**Sprint:** Process Enforcement v1
**Status:** `BLOQUEADA` — aguarda Story 1.1 concluída
**Sequência:** 2 de 3 — só iniciar após Story 1.1 com `qa_approved`
**Design spec:** `docs/stories/sprint-enforcement/design-spec.md` — Seção 3

---

## User Story

> Como sistema,
> quero verificar que o estado foi persistido no Supabase antes de aceitar qualquer avanço de gate,
> para que nenhum agente avance sem ter gravado o que fez.

---

## Contexto técnico

**Arquivo principal:** `sparkle-runtime/runtime/workflows/pipeline_enforcement.py`
**Arquivo secundário:** `sparkle-runtime/runtime/pipeline/router.py`

**Pré-requisito:** Story 1.1 concluída — `SCHEMA_VERSION`, `is_legacy_run()` e `normalize_step()` devem existir.

**Fluxo atual do `/pipeline/advance`:**
```
check_gates() → [NOVO: verify_state_persisted()] → record_transition()
```

**Tabela consultada:** `agent_work_items`
**Campos relevantes:** `sprint_item`, `verified` (bool), `status`, `handoff_to`

---

## Acceptance Criteria

- [ ] **AC1** — `verify_state_persisted(sprint_item, step_name, schema_version)` implementada em `pipeline_enforcement.py` conforme design spec seção 3.1
- [ ] **AC2** — Runs legados (`schema_version < 2`) retornam `allowed: True` com `skipped: True` — sem impacto em itens existentes
- [ ] **AC3** — Item sem registro em `agent_work_items` retorna HTTP 422 com `error_code: "state_missing"` e mensagem com `action_required`
- [ ] **AC4** — Item com `verified: false` retorna HTTP 422 com `error_code: "state_unverified"` e mensagem específica
- [ ] **AC5** — `notify_violation()` atualizada com parâmetro `violation_type` (gate_skip | state_missing | handoff_invalid) conforme design spec seção 3.3
- [ ] **AC6** — `_should_notify()` implementada com cache em memória TTL 5 min — deduplicação por `(item_id, violation_type)` conforme design spec seção 3.4
- [ ] **AC7** — `verify_state_persisted()` inserida em `router.py` após `check_gates()` e antes de `record_transition()` conforme design spec seção 3.2
- [ ] **AC8** — Violação por `state_missing` gera log em `runtime_tasks` com `task_type: "pipeline_violation_alert"` e `violation_type: "state_missing"`

---

## Integration Verifications

- [ ] **IV1** — `POST /pipeline/advance` sem `POST /system/state` prévio retorna 422 com mensagem `"Estado não persistido. Execute POST /system/state..."` e `action_required`
- [ ] **IV2** — `POST /pipeline/advance` após `POST /system/state` com `verified: true` avança normalmente (200 OK)
- [ ] **IV3** — Friday recebe notificação WhatsApp quando gate bloqueado por `state_missing` (verificar no Chatwoot)
- [ ] **IV4** — Segunda tentativa de violar o mesmo gate dentro de 5 min NÃO gera segunda notificação Friday (deduplicação ativa)

---

## Notas de implementação

- `sprint_item` é extraído de `run.get("context", {}).get("sprint_item")` — pode ser None em runs legados
- Query Supabase em `verify_state_persisted()` usa `.single()` — tratar exceção se não encontrado
- Latência adicional deve ser < 200ms (query por `sprint_item` indexado)
- Não remover comportamento existente de `notify_violation()` — apenas adicionar `violation_type`

---

## Handoff para @dev

```
---
GATE_CONCLUÍDO: Gate 3 — Stories prontas
STATUS: AGUARDANDO_DEV
PRÓXIMO: @dev
SPRINT_ITEM: PROC-ENF-V1-1.2

ENTREGA:
  - Story: docs/stories/sprint-enforcement/story-1.2-gate-verification.md
  - Design spec (seção 3): docs/stories/sprint-enforcement/design-spec.md
  - Arquivo principal: sparkle-runtime/runtime/workflows/pipeline_enforcement.py
  - Arquivo secundário: sparkle-runtime/runtime/pipeline/router.py

SUPABASE_ATUALIZADO: não aplicável (story de planejamento)

PROMPT_PARA_PRÓXIMO: |
  Você é @dev (Dex). Contexto direto — comece aqui.

  PRÉ-REQUISITO OBRIGATÓRIO: Story 1.1 deve estar com status qa_approved.
  Confirme antes de começar: GET /pipeline/status/PROC-ENF-V1-1.1

  O QUE FOI FEITO:
  Story 1.2 criada. Sua tarefa é adicionar verificação obrigatória de estado
  persistido no Supabase antes de aceitar qualquer avanço de gate.

  ARQUIVOS A MODIFICAR:
  1. sparkle-runtime/runtime/workflows/pipeline_enforcement.py
     - Adicionar verify_state_persisted() (design spec seção 3.1 — código exato)
     - Atualizar notify_violation() com violation_type param (design spec 3.3)
     - Adicionar _should_notify() com cache TTL 5min (design spec 3.4)
  2. sparkle-runtime/runtime/pipeline/router.py
     - Inserir verify_state_persisted() em pipeline_advance() (design spec 3.2)
     - Extrair sprint_item do context do workflow_run

  REFERÊNCIA OBRIGATÓRIA: design spec seção 3.1, 3.2, 3.3 e 3.4.

  CRITÉRIOS DE SAÍDA DO SEU GATE:
  - [ ] AC1 a AC8 todos implementados
  - [ ] IV1 a IV4 todos passando
  - [ ] Story 1.1 não quebrada (testar IV1-IV4 da 1.1 também)

  SE aprovado pelo @qa: STATUS = dev_complete, PRÓXIMO = @qa
  SE bloqueio técnico: STATUS = blocked, PRÓXIMO = @sm com razão específica
---
```

---

*Story 1.2 — Process Enforcement v1 | River 🌊*
