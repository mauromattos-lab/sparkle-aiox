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

---

## QA Results

**Revisor:** @qa (Quinn)
**Data:** 2026-04-06
**Gate Decision:** `PASS ✅`

### Verificação dos ACs

| AC | Status | Evidência |
|----|--------|-----------|
| AC1: verify_state_persisted() em pipeline_enforcement.py | ✅ PASS | Função presente, signature correta com 3 params |
| AC2: Runs legados (schema_version < 1) retornam skipped=True | ✅ PASS | `{'allowed': True, 'reason': 'legacy_run_skipped', 'skipped': True}` confirmado |
| AC3: state_missing → 422 + action_required | ✅ PASS | error_code, mensagem e action_required presentes na função |
| AC4: state_unverified → 422 + mensagem | ✅ PASS | `verified=false` check + error_code state_unverified implementados |
| AC5: notify_violation() com violation_type param | ✅ PASS | Default `'gate_skip'`, aceita gate_skip/state_missing/handoff_invalid |
| AC6: _should_notify() com cache TTL 5min | ✅ PASS | Dedup funcional: 2a chamada mesma chave retorna False |
| AC7: verify_state_persisted() inserido em router.py | ✅ PASS | Inserido após check_gates(), antes de record_transition() |
| AC8: Violação state_missing gera log runtime_tasks | ✅ PASS | `"violation_type": violation_type` em payload, `task_type: pipeline_violation_alert` |

### Verificação dos IVs

| IV | Status | Resultado observado |
|----|--------|---------------------|
| IV1: advance sem /system/state → 422 state_missing | ✅ PASS | `{"error": "state_missing", "action_required": "POST /system/state..."}` |
| IV2: advance após /system/state verified=true → 200 | ✅ PASS | HTTP 200, step avançou corretamente |
| IV3: Friday recebe notificação state_missing | ✅ WAIVED | Verificação por inspeção de código — `send_proactive` chamado após `_should_notify` retornar True |
| IV4: 2a tentativa dentro de 5min não gera 2a notificação | ✅ PASS | `_should_notify` retorna False na 2a chamada com mesma chave — confirmado em teste unitário |

### Testes adicionais executados por QA

- **Regressão Story 1.1:** Skip de gate ainda retorna violação (comportamento preservado)
- **Compatibilidade legacy:** `schema_version=1` → `skipped=True`, sem query no Supabase
- **sprint_item=None:** Retorna `skipped=True` (graceful para runs sem context)
- **Item inexistente no banco:** Retorna `state_missing` com mensagem clara

### Observações (não-bloqueantes)

- **Obs-1 (LOW):** `current_step` passado para `notify_violation` em router.py ainda usa `run.get("current_step", 0)` sem normalizar (herdado da Obs-1 da Story 1.1) — cosmético, não impacta lógica
- **Obs-2 (INFO):** IV3 não foi testado em produção (requer WhatsApp real ativo) — waivado por inspeção de código que confirma o caminho de execução

### Conclusão

Implementação correta e segura. Compatibilidade com runs legados preservada. Deduplicação de notificações funcional. Todos os 8 ACs verificados. Regressão Story 1.1 limpa.

**STATUS: `qa_approved` → próximo: @po**

*— Quinn, guardião da qualidade 🛡️*

---

*Story 1.2 — Process Enforcement v1 | River 🌊*
