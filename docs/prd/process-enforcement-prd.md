# Process Enforcement v1 — Brownfield Enhancement PRD

| Campo | Valor |
|-------|-------|
| **Versão** | 1.0 |
| **Data** | 2026-04-05 |
| **Autor** | @pm (Morgan) |
| **Status** | Aprovado — Mauro 2026-04-05 |
| **Épico** | Process Enforcement v1 |
| **Processo** | `docs/operations/sparkle-os-process-v2.md` |
| **PRD futuro** | Pipeline Dinâmico (paralelismo + agentes opcionais) |

---

## 1. Contexto e Objetivo

### Estado atual

O C2-B2 (Pipeline Enforcement) implementou enforcement básico de sequência de gates via `POST /pipeline/advance`, com rejeição HTTP 422 e notificação Friday. Funciona — mas cobre apenas Fase 2 (dev → qa → devops) com 5 steps fixos.

O processo v2.0 (`sparkle-os-process-v2.md`) define 7 gates cobrindo o ciclo completo (Fase 1 + Fase 2). Os 3 gaps entre o que existe e o que o processo exige causaram falhas operacionais nos últimos sprints:

| Gap | Problema observado |
|-----|--------------------|
| **Gap 1** | @pm e @architect sem enforcement — Fase 1 era bypassável |
| **Gap 2** | Agentes avançavam sem gravar estado no Supabase — sessões perdiam contexto |
| **Gap 3** | Handoffs sem campos obrigatórios — próximo agente começava sem contexto completo |

### Objetivo

Transformar as regras do `sparkle-os-process-v2.md` em código verificável, fechando os 3 gaps acima. O sistema passa a enforçar o processo — não apenas recomendá-lo.

### Fora do escopo

- Pipeline dinâmico (steps opcionais, paralelos, agentes como @ux em gates específicos) → PRD separado
- Mudanças no `/system/state` endpoint existente
- Novos agentes ou squads
- Portal/dashboard de visualização do pipeline

---

## 2. Análise do Sistema Existente

### Stack atual

| Componente | Localização | Estado |
|-----------|-------------|--------|
| Pipeline Enforcement | `runtime/workflows/pipeline_enforcement.py` | ✅ Funcional |
| Pipeline Router | `runtime/pipeline/router.py` | ✅ Funcional |
| System State | `runtime/system_router.py` | ✅ Funcional |
| workflow_runs table | Supabase | ✅ Com histórico |
| agent_work_items table | Supabase | ✅ Fonte de verdade |

### PIPELINE_STEPS atual (C2-B2)

```python
# Atual — 5 steps, cobre só Fase 2
{"step": 0, "name": "story_created",     "agent": "@architect/@pm"}
{"step": 1, "name": "dev_implementing",   "agent": "@dev"}
{"step": 2, "name": "qa_validating",      "agent": "@qa"}
{"step": 3, "name": "devops_deploying",   "agent": "@devops"}
{"step": 4, "name": "done",               "agent": "system"}
```

### Lacunas identificadas

1. **Fase 1 sem enforcement** — gates de @pm, @architect, @sm e @po não existem no pipeline
2. **State verification ausente** — `/pipeline/advance` não consulta `agent_work_items` antes de aceitar
3. **Handoff sem schema** — não há validação dos campos obrigatórios do bloco de handoff

---

## 3. Requisitos Funcionais

**FR1** — O sistema deve suportar os 7 gates do processo v2, incluindo Fase 1 (planejamento) e Fase 2 (execução), com step names explícitos para cada agente responsável.

**FR2** — O sistema deve verificar, antes de aceitar qualquer avanço de gate, se o estado foi persistido em `agent_work_items` com `verified: true` para o item correspondente. Avanço sem persistência deve retornar HTTP 422.

**FR3** — O sistema deve validar o schema do bloco de handoff antes de aceitar a transição. Handoffs com campos obrigatórios ausentes devem ser rejeitados com lista clara dos campos faltando.

**FR4** — Toda violação bloqueada (gate skip, state não persistido, handoff inválido) deve gerar notificação Friday e log em `runtime_tasks` para auditoria.

**FR5** — Items existentes em produção (workflow_runs com steps antigos 0-4) devem continuar funcionando após o deploy, via migration de mapeamento de compatibilidade.

---

## 4. Requisitos Não-Funcionais

**NFR1** — Nenhum endpoint existente quebra. Compatibilidade total com C2-B2 atual.

**NFR2** — Latência adicional do `/pipeline/advance` com as novas validações não deve exceder 200ms.

**NFR3** — Toda violação bloqueada gera exatamente 1 notificação Friday (sem spam — deduplicação por item+step dentro de 5 minutos).

**NFR4** — O sistema deve funcionar sem mudanças no cliente (agentes AIOS chamam os mesmos endpoints com os mesmos contratos).

---

## 5. Requisitos de Compatibilidade

**CR1** — `workflow_runs` com `current_step` 0-4 (steps antigos) são mapeados automaticamente para os novos steps equivalentes:
```
step 0 (story_created)   → step 2 (stories_ready)
step 1 (dev_implementing) → step 3 (dev_complete)
step 2 (qa_validating)   → step 4 (qa_approved)
step 3 (devops_deploying) → step 6 (devops_deployed)
step 4 (done)            → step 7 (done)
```

**CR2** — `POST /system/state` (agent_work_items) não muda — apenas passa a ser consultado pelo `/pipeline/advance`.

**CR3** — Notificações Friday de violação mantêm formato atual, com campos adicionais (tipo de violação: gate_skip | state_missing | handoff_invalid).

---

## 6. Epic e Stories

### Epic: Process Enforcement v1

**Goal:** Fechar os 3 gaps entre o processo v2 documentado e o que o sistema enforça em código.

**Sequência obrigatória:** Story 1.1 → 1.2 → 1.3 (cada uma depende da anterior).

---

### Story 1.1 — Estender Pipeline para 7 Gates

> Como agente do AIOS,
> quero que o sistema reconheça todos os 7 gates do processo v2,
> para que nenhum gate da Fase 1 (planejamento) seja ignorável.

**Acceptance Criteria:**

1. `PIPELINE_STEPS` atualizado com 8 entries (steps 0-7):
   ```
   0: prd_approved      (@pm)
   1: spec_approved     (@architect)
   2: stories_ready     (@sm)
   3: dev_complete      (@dev)
   4: qa_approved       (@qa)
   5: po_accepted       (@po)
   6: devops_deployed   (@devops)
   7: done              (sistema)
   ```
2. `POST /pipeline/advance` aceita e valida todos os novos step names
3. Migration de mapeamento aplicada — `workflow_runs` existentes com steps 0-4 continuam funcionando
4. `GET /pipeline/status` retorna os 8 steps com estado correto para items novos e existentes

**Integration Verifications:**

- IV1: `workflow_run` existente com `current_step: 2` (qa_validating antigo) não quebra após deploy
- IV2: `POST /pipeline/advance` com `target_step: "prd_approved"` em item novo retorna 200
- IV3: `POST /pipeline/advance` tentando pular de `prd_approved` para `dev_complete` retorna 422

---

### Story 1.2 — Gate Verification obrigatório

> Como sistema,
> quero verificar que o estado foi persistido no Supabase antes de aceitar qualquer avanço de gate,
> para que nenhum agente avance sem ter gravado o que fez.

**Acceptance Criteria:**

1. `POST /pipeline/advance` consulta `agent_work_items` antes de aceitar a transição
2. Se não há registro para o `sprint_item` → HTTP 422 + mensagem "Estado não persistido — execute POST /system/state antes de avançar"
3. Se registro existe mas `verified: false` → HTTP 422 com motivo "verified: false — confirme a entrega antes de avançar"
4. Agentes com `verified: true` em `agent_work_items` passam sem impacto de performance
5. Violação por state missing gera notificação Friday com tipo `state_missing` e log em `runtime_tasks`

**Integration Verifications:**

- IV1: Chamar `/pipeline/advance` sem `POST /system/state` prévio retorna 422 com mensagem clara
- IV2: Chamar `/pipeline/advance` após `POST /system/state` com `verified: true` avança normalmente
- IV3: Friday recebe notificação com tipo `state_missing` quando gate bloqueado por falta de persistência
- IV4: Agentes que já persistiram não percebem latência adicional > 200ms

---

### Story 1.3 — Handoff Schema Validation

> Como próximo agente na sequência,
> quero receber um handoff completo e validado,
> para que eu sempre tenha o contexto necessário para começar sem ambiguidade.

**Acceptance Criteria:**

1. Novo endpoint `POST /pipeline/validate-handoff` valida campos obrigatórios:
   - `gate_concluido` (string)
   - `status` (string)
   - `proximo` (string — agente)
   - `sprint_item` (string)
   - `entrega` (array — mínimo 1 item)
   - `supabase_atualizado` (boolean)
   - `prompt_para_proximo` (string — mínimo 100 chars)
2. Retorna `{ valid: true, handoff_validation_id: uuid }` quando completo
3. Retorna `{ valid: false, missing_fields: [...], errors: [...] }` quando incompleto
4. `POST /pipeline/advance` exige `handoff_validation_id` válido no body
5. Handoffs validados armazenados em `runtime_tasks` para auditoria
6. Violação por handoff inválido gera notificação Friday com tipo `handoff_invalid` e lista de campos faltando

**Integration Verifications:**

- IV1: Handoff com `prompt_para_proximo` ausente retorna 422 com `missing_fields: ["prompt_para_proximo"]`
- IV2: Handoff completo retorna `handoff_validation_id` e permite avanço do pipeline
- IV3: `GET /pipeline/status` mostra referência ao `handoff_validation_id` do último gate concluído
- IV4: Tentativa de reutilizar o mesmo `handoff_validation_id` em dois `/pipeline/advance` diferentes é rejeitada

---

## 7. Handoff para @architect

```
---
GATE_CONCLUÍDO: Gate 1 — PRD aprovado
STATUS: AGUARDANDO_ARCHITECT
PRÓXIMO: @architect
SPRINT_ITEM: PROC-ENF-V1

ENTREGA:
  - PRD: docs/prd/process-enforcement-prd.md
  - Processo base: docs/operations/sparkle-os-process-v2.md
  - C2-B2 existente: sparkle-runtime/runtime/workflows/pipeline_enforcement.py
  - Pipeline router: sparkle-runtime/runtime/pipeline/router.py

SUPABASE_ATUALIZADO: pendente (primeiro item do novo processo)

PROMPT_PARA_PRÓXIMO: |
  Você é @architect (Aria). Contexto direto.

  O QUE FOI FEITO:
  PRD aprovado para Process Enforcement v1. 3 stories sequenciais.
  C2-B2 existe em produção com 5 steps. Precisa ser estendido para 7 gates.
  Endpoints existentes: POST /pipeline/advance, GET /pipeline/status, GET /pipeline/violations.
  Tabelas existentes: workflow_runs (steps), agent_work_items (state), runtime_tasks (audit).

  SUA TAREFA:
  Criar design spec técnico para as 3 stories:
  1. Como estender PIPELINE_STEPS sem quebrar workflow_runs existentes (migration strategy)
  2. Onde e como inserir a verificação de agent_work_items no /pipeline/advance
  3. Schema do endpoint POST /pipeline/validate-handoff (request/response, storage)

  CRITÉRIOS DE SAÍDA DO SEU GATE:
  - [ ] Design spec salvo em docs/stories/sprint-enforcement/design-spec.md
  - [ ] Migration strategy para workflow_runs existentes documentada
  - [ ] Contrato de API dos 3 endpoints (request/response/errors) definido
  - [ ] Riscos técnicos identificados

  SE aprovado: STATUS = spec_approved, PRÓXIMO = @sm
  SE bloqueio técnico: STATUS = blocked, PRÓXIMO = @pm com razão clara
---
```

---

*Process Enforcement v1 PRD — aprovado para execução via pipeline AIOS.*
*Próximo: @architect cria design spec → @sm cria stories → @dev implementa → @qa valida → @po aceita → @devops deploya.*
