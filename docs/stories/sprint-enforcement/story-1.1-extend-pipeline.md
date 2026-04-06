# Story 1.1 — Estender Pipeline para 7 Gates

**Sprint:** Process Enforcement v1
**Status:** `AGUARDANDO_DEV`
**Sequência:** 1 de 3 — deve ser implementada ANTES de 1.2 e 1.3
**Design spec:** `docs/stories/sprint-enforcement/design-spec.md` — Seção 2

---

## User Story

> Como agente do AIOS,
> quero que o sistema reconheça todos os 7 gates do processo v2,
> para que nenhum gate da Fase 1 (planejamento) seja ignorável.

---

## Contexto técnico

**Arquivo principal:** `sparkle-runtime/runtime/workflows/pipeline_enforcement.py`
**Arquivo secundário:** `sparkle-runtime/runtime/workflows/templates.py`

**Estado atual — PIPELINE_STEPS (5 steps):**
```python
{"step": 0, "name": "story_created",    "agent": "@architect/@pm"}
{"step": 1, "name": "dev_implementing", "agent": "@dev"}
{"step": 2, "name": "qa_validating",    "agent": "@qa"}
{"step": 3, "name": "devops_deploying", "agent": "@devops"}
{"step": 4, "name": "done",             "agent": "system"}
```

**Estado alvo — PIPELINE_STEPS (8 entries, steps 0-7):**
```python
{"step": 0, "name": "prd_approved",    "agent": "@pm"}
{"step": 1, "name": "spec_approved",   "agent": "@architect"}
{"step": 2, "name": "stories_ready",   "agent": "@sm"}
{"step": 3, "name": "dev_complete",    "agent": "@dev"}
{"step": 4, "name": "qa_approved",     "agent": "@qa"}
{"step": 5, "name": "po_accepted",     "agent": "@po"}
{"step": 6, "name": "devops_deployed", "agent": "@devops"}
{"step": 7, "name": "done",            "agent": "system"}
```

---

## Acceptance Criteria

- [ ] **AC1** — `PIPELINE_STEPS` atualizado com 8 entries (steps 0-7) conforme design spec seção 2.1
- [ ] **AC2** — `SCHEMA_VERSION = 2` adicionado como constante em `pipeline_enforcement.py`
- [ ] **AC3** — `LEGACY_STEP_MAP` implementado com mapeamento de steps v1 → v2 conforme design spec seção 2.2
- [ ] **AC4** — `is_legacy_run(run)` e `normalize_step(run)` implementados conforme design spec seção 2.2
- [ ] **AC5** — `_get_pipeline_run()` e `check_gates()` atualizados para usar `normalize_step()`
- [ ] **AC6** — Aliases legados adicionados a `NAME_TO_STEP`: `"story_created": 2`, `"dev_implementing": 3`, `"qa_validating": 4`, `"devops_deploying": 6`
- [ ] **AC7** — Template `aios_pipeline` em `templates.py` atualizado com os 8 steps
- [ ] **AC8** — Novos runs criados via `/pipeline/advance` inserem `schema_version: 2` no context

---

## Integration Verifications

- [ ] **IV1** — `workflow_run` existente com `current_step: 2` (qa_validating antigo) não quebra após deploy: `GET /pipeline/status/{id_legado}` retorna 200 com step mapeado corretamente
- [ ] **IV2** — `POST /pipeline/advance` com `target_step: "prd_approved"` em item novo retorna 200
- [ ] **IV3** — `POST /pipeline/advance` tentando ir de `prd_approved` (step 0) para `dev_complete` (step 3) retorna 422 com mensagem de violação
- [ ] **IV4** — `GET /pipeline/status/{novo_item}` retorna 8 steps com `schema_version: 2`

---

## Notas de implementação

- Seguir exatamente o design spec seção 2.2 — não inventar estratégia diferente
- `normalize_step()` deve ser chamado ANTES de qualquer validação de transição
- Aliases legados em `NAME_TO_STEP` garantem que strings antigas ainda funcionam
- NÃO fazer migration SQL — toda compatibilidade é em código

---

## Handoff para @dev

```
---
GATE_CONCLUÍDO: Gate 3 — Stories prontas
STATUS: AGUARDANDO_DEV
PRÓXIMO: @dev
SPRINT_ITEM: PROC-ENF-V1-1.1

ENTREGA:
  - Story: docs/stories/sprint-enforcement/story-1.1-extend-pipeline.md
  - Design spec (seção 2): docs/stories/sprint-enforcement/design-spec.md
  - Arquivo principal: sparkle-runtime/runtime/workflows/pipeline_enforcement.py
  - Arquivo secundário: sparkle-runtime/runtime/workflows/templates.py

SUPABASE_ATUALIZADO: não aplicável (story de planejamento)

PROMPT_PARA_PRÓXIMO: |
  Você é @dev (Dex). Contexto direto — comece aqui.

  O QUE FOI FEITO:
  Story 1.1 criada com design spec completo. Sua tarefa é estender o
  PIPELINE_STEPS de 5 para 7 gates sem quebrar workflow_runs existentes.

  ARQUIVOS A MODIFICAR:
  1. sparkle-runtime/runtime/workflows/pipeline_enforcement.py
     - Substituir PIPELINE_STEPS com 8 entries (ver AC1 + design spec 2.1)
     - Adicionar SCHEMA_VERSION = 2
     - Adicionar LEGACY_STEP_MAP (design spec 2.2)
     - Implementar is_legacy_run() e normalize_step() (design spec 2.2)
     - Atualizar _get_pipeline_run() e check_gates() para usar normalize_step()
     - Adicionar aliases em NAME_TO_STEP (design spec 2.2)
  2. sparkle-runtime/runtime/workflows/templates.py
     - Atualizar template aios_pipeline com 8 steps

  REFERÊNCIA OBRIGATÓRIA: design spec seção 2.1 e 2.2 — código exato está lá.

  CRITÉRIOS DE SAÍDA DO SEU GATE:
  - [ ] AC1 a AC8 todos implementados
  - [ ] IV1 a IV4 todos passando (testar localmente antes de entregar)
  - [ ] Nenhum teste existente quebrado

  SE aprovado pelo @qa: STATUS = dev_complete, PRÓXIMO = @qa
  SE bloqueio técnico: STATUS = blocked, PRÓXIMO = @sm com razão específica
---
```

---

---

## QA Results

**Revisor:** @qa (Quinn)
**Data:** 2026-04-06
**Gate Decision:** `PASS ✅`

### Verificação dos ACs

| AC | Status | Evidência |
|----|--------|-----------|
| AC1: 8 PIPELINE_STEPS (steps 0-7) | ✅ PASS | `len(PIPELINE_STEPS) == 8`, steps 0-7 confirmados |
| AC2: SCHEMA_VERSION = 2 | ✅ PASS | Linha 26: `SCHEMA_VERSION = 2` |
| AC3: LEGACY_STEP_MAP implementado | ✅ PASS | `{0:2, 1:3, 2:4, 3:6, 4:7}` conforme spec |
| AC4: is_legacy_run() + normalize_step() | ✅ PASS | Funções implementadas, comportamento correto |
| AC5: check_gates() usa normalize_step() | ✅ PASS | Linha 222: `current_step = normalize_step(run)` |
| AC6: Aliases legados em NAME_TO_STEP | ✅ PASS | story_created→2, dev_implementing→3, qa_validating→4, devops_deploying→6 |
| AC7: template aios_pipeline v2 com 8 steps | ✅ PASS | templates.py versão 2, 8 steps corretos |
| AC8: record_transition injeta schema_version:2 | ✅ PASS | Linhas 157-159, conditional upgrade |

### Verificação dos IVs

| IV | Status | Resultado observado |
|----|--------|---------------------|
| IV1: legacy step 2 → step 4 qa_approved | ✅ PASS | normalize_step retornou 4 (qa_approved) |
| IV2: advance prd_approved → 200 OK | ✅ PASS | HTTP 200, step_name: prd_approved |
| IV3: skip prd_approved→dev_complete → 422 | ✅ PASS | HTTP 422, "Step dev_complete requer spec_approved concluido" |
| IV4: GET /pipeline/status retorna 8 steps | ✅ PASS | total_steps: 8, todos os step names corretos |

### Testes adicionais executados por QA

- **Matriz completa de transição (9 pares):** todos corretos (7 válidos + 2 skips rejeitados)
- **Legacy step mapping completo (steps 0-4):** todos mapeados corretamente para v2
- **Runs v2 não afetados por normalize_step:** confirmado (is_legacy=False, step preservado)

### Observações (não-bloqueantes)

- **Obs-1 (LOW):** Em `pipeline_advance` no router.py, a variável `current_step` usada em `notify_violation` vem de `run.get("current_step", 0)` sem normalizar — para legacy items, a mensagem de violação pode exibir o step antigo. Não bloqueia; impacto apenas cosmético em mensagens WhatsApp.
- **Obs-2 (INFO):** `normalize_step` para step -1 (estado inicial de testes) retorna -1 sem mapear — comportamento esperado pois -1 não está no LEGACY_STEP_MAP.

### Conclusão

Implementação sólida. Backward compatibility preservada por código sem migration SQL. Todos os 8 ACs e 4 IVs verificados com evidências. Regressão não detectada.

**STATUS: `qa_approved` → próximo: @po**

*— Quinn, guardião da qualidade 🛡️*

---

*Story 1.1 — Process Enforcement v1 | River 🌊*
