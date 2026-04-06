# Story 1.3 — Handoff Schema Validation

**Sprint:** Process Enforcement v1
**Status:** `BLOQUEADA` — aguarda Story 1.2 concluída
**Sequência:** 3 de 3 — só iniciar após Story 1.2 com `qa_approved`
**Design spec:** `docs/stories/sprint-enforcement/design-spec.md` — Seção 4

---

## User Story

> Como próximo agente na sequência,
> quero receber um handoff completo e validado,
> para que eu sempre tenha o contexto necessário para começar sem ambiguidade.

---

## Contexto técnico

**Arquivo novo:** `sparkle-runtime/runtime/pipeline/handoff_validator.py`
**Arquivo modificado:** `sparkle-runtime/runtime/pipeline/router.py`

**Pré-requisito:** Stories 1.1 e 1.2 concluídas. `SCHEMA_VERSION`, `verify_state_persisted()` e `notify_violation(violation_type)` devem existir.

**Campos obrigatórios do bloco de handoff:**
```
gate_concluido        string     "Gate 4 — QA aprovado"
status                string     "AGUARDANDO_PO"
proximo               string     "@po"  (deve começar com @)
sprint_item           string     "PROC-ENF-V1"
entrega               list[str]  mínimo 1 item
supabase_atualizado   bool       deve ser True
prompt_para_proximo   string     mínimo 100 caracteres
```

**Storage:** `runtime_tasks` com `task_type: "handoff_validation"`
**One-time use:** campo `consumed` no payload — False → True após uso

---

## Acceptance Criteria

- [ ] **AC1** — `sparkle-runtime/runtime/pipeline/handoff_validator.py` criado com `HandoffPayload`, `validate_handoff()` e `store_handoff()` conforme design spec seção 4.1
- [ ] **AC2** — `validate_handoff()` valida: `entrega` não vazia, `supabase_atualizado: True`, `prompt_para_proximo` ≥ 100 chars, `proximo` começa com `@`
- [ ] **AC3** — `store_handoff()` salva em `runtime_tasks` com `task_type: "handoff_validation"` e `consumed: False`
- [ ] **AC4** — `consume_handoff(handoff_validation_id)` implementada — marca `consumed: True` e rejeita reuso
- [ ] **AC5** — Endpoint `POST /pipeline/validate-handoff` adicionado em `router.py` conforme design spec seção 4.2
- [ ] **AC6** — `AdvanceRequest` atualizado com `handoff_validation_id: Optional[str]` conforme design spec seção 4.3
- [ ] **AC7** — `POST /pipeline/advance` exige `handoff_validation_id` para items com `schema_version >= 2`; items legados passam sem ele
- [ ] **AC8** — Violação por handoff inválido gera notificação Friday com `violation_type: "handoff_invalid"` e lista de campos faltando

---

## Integration Verifications

- [ ] **IV1** — `POST /pipeline/validate-handoff` com `prompt_para_proximo` ausente retorna 422 com `missing_or_invalid_fields: ["prompt_para_proximo"]`
- [ ] **IV2** — Handoff completo e válido retorna 200 com `handoff_validation_id` (UUID)
- [ ] **IV3** — `POST /pipeline/advance` com `handoff_validation_id` válido avança pipeline normalmente
- [ ] **IV4** — Segunda tentativa de usar o mesmo `handoff_validation_id` em `/pipeline/advance` retorna 422 com `error: "handoff_consumed"`

---

## Notas de implementação

- `consume_handoff()` itera `runtime_tasks` — ver risco no design spec seção 4.4 (adicionar index se necessário)
- `handoff_validation_id` é UUID v4 gerado em `store_handoff()`
- Items legados (`schema_version < 2`) passam pelo `/pipeline/advance` sem `handoff_validation_id` — não bloquear
- Truncar `prompt_para_proximo` para 200 chars no storage (log) — não no payload de validação

---

## Handoff para @dev

```
---
GATE_CONCLUÍDO: Gate 3 — Stories prontas
STATUS: AGUARDANDO_DEV
PRÓXIMO: @dev
SPRINT_ITEM: PROC-ENF-V1-1.3

ENTREGA:
  - Story: docs/stories/sprint-enforcement/story-1.3-handoff-validation.md
  - Design spec (seção 4): docs/stories/sprint-enforcement/design-spec.md
  - Arquivo novo: sparkle-runtime/runtime/pipeline/handoff_validator.py
  - Arquivo modificado: sparkle-runtime/runtime/pipeline/router.py

SUPABASE_ATUALIZADO: não aplicável (story de planejamento)

PROMPT_PARA_PRÓXIMO: |
  Você é @dev (Dex). Contexto direto — comece aqui.

  PRÉ-REQUISITO OBRIGATÓRIO: Stories 1.1 e 1.2 devem estar com status qa_approved.
  Confirme: GET /pipeline/status/PROC-ENF-V1-1.1 e PROC-ENF-V1-1.2

  O QUE FOI FEITO:
  Story 1.3 criada. Sua tarefa é criar o sistema de validação de handoff —
  um novo arquivo Python + endpoint + atualização do AdvanceRequest.

  ARQUIVOS A CRIAR/MODIFICAR:
  1. CRIAR sparkle-runtime/runtime/pipeline/handoff_validator.py
     - HandoffPayload (Pydantic model)
     - validate_handoff() → (bool, list[str])
     - store_handoff() → str (UUID)
     - consume_handoff() → dict
     (design spec seção 4.1 — código completo está lá, use como base)

  2. MODIFICAR sparkle-runtime/runtime/pipeline/router.py
     - Importar handoff_validator
     - Adicionar POST /pipeline/validate-handoff (design spec 4.2)
     - Atualizar AdvanceRequest com handoff_validation_id (design spec 4.3)
     - Inserir consume_handoff() em pipeline_advance() (design spec 4.3)

  REFERÊNCIA OBRIGATÓRIA: design spec seção 4.1, 4.2 e 4.3.

  CRITÉRIOS DE SAÍDA DO SEU GATE:
  - [ ] AC1 a AC8 todos implementados
  - [ ] IV1 a IV4 todos passando
  - [ ] Stories 1.1 e 1.2 não quebradas (regressão)
  - [ ] POST /system/state → POST /pipeline/validate-handoff → POST /pipeline/advance
        funciona como fluxo completo end-to-end

  SE aprovado pelo @qa: STATUS = dev_complete, PRÓXIMO = @qa
  SE bloqueio técnico: STATUS = blocked, PRÓXIMO = @sm com razão específica
---
```

---

*Story 1.3 — Process Enforcement v1 | River 🌊*
