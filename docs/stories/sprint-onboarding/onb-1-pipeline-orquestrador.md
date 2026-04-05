---
epic: EPIC-ONBOARDING — Zenya Atendente Onboarding Pipeline
story: ONB-1
title: Pipeline Orquestrador de Onboarding
status: Draft
priority: P0 — Bloqueador (todas as outras stories dependem deste)
executor: @dev (implementacao)
sprint: Sprint 9 (2026-04-07+)
architecture: docs/architecture/zenya-onboarding-architecture.md
depends_on: []
unblocks: [ONB-3, ONB-5]
estimated_effort: 10-14h @dev
---

# Story ONB-1 — Pipeline Orquestrador de Onboarding

## Story

**Como** sistema Sparkle Runtime,
**Quero** ter um pipeline de onboarding multi-fase com tracking de estado, gates entre fases, e alertas de timeout,
**Para que** cada novo cliente siga um caminho previsivel do "Mauro disse sim" ate "Zenya ao vivo", com visibilidade total e sem intervencao manual entre etapas.

---

## Contexto Tecnico

**Por que agora:** O onboarding atual e manual e invisivel. O Mauro configura cada cliente em sessoes ad-hoc de 45-90 min. Com 6 clientes e trabalhoso; com 15 e impossivel. O pipeline `onboarding_zenya` existe no Runtime (template v2) mas nunca completou com sucesso (8 tentativas falharam — ver SUB-6). Esta story cria a camada de orquestracao que faltava.

**O que ja existe:**
- Workflow engine (`workflow_instances`, `workflow_step` handler) — funcional apos SUB-3 fixes
- Template `onboarding_zenya` v2 — ativo no banco
- Handlers individuais: `brain_ingest`, `extract_client_dna`, `onboard_client`, `create_subscription`

**O que falta (escopo desta story):**
1. Tabela `onboarding_workflows` para tracking granular por fase
2. Task type `gate_check` para validar condicoes entre fases
3. Polling cron para eventos de longa duracao (pagamento, contrato, resposta cliente)
4. Alertas Friday para timeouts
5. Comunicacao proativa com cliente via WhatsApp em cada transicao de fase
6. Endpoint `/onboarding/start` que orquestra o pipeline completo

**Decisao de PM:** Nao implementar `webhook_wait` real. Usar polling cron (check a cada hora) para eventos de longa duracao. Webhook real e Fase 2.

**Decisao de PM:** Contrato via n8n (workflow 20 Autentique ja ativo). Nao automatizar contrato no Runtime na Fase 1.

---

## Criterios de Aceitacao

### Tabela e modelo de dados

- [x] **AC-1.1:** Tabela `onboarding_workflows` criada no Supabase com colunas: `id` (UUID PK), `client_id` (FK clients), `phase` (TEXT), `status` (TEXT default 'pending'), `started_at`, `completed_at`, `gate_passed` (BOOLEAN), `gate_details` (JSONB), `error_log`, `created_at`
- [x] **AC-1.2:** Indice em `onboarding_workflows(client_id, phase)` para queries rapidas
- [x] **AC-1.3:** Campo `testing_mode` (TEXT ENUM: 'off'/'internal_testing'/'client_testing'/'live') adicionado a `zenya_clients` — Aria rec: ENUM nao BOOLEAN

### Endpoint de inicio

- [x] **AC-2.1:** `POST /onboarding/start` aceita payload: `{ client_name, business_type, site_url, phone, plan, mrr_value }` e retorna `{ onboarding_id, client_id, status: "contract_pending" }`
- [x] **AC-2.2:** O endpoint cria automaticamente: registro em `clients` (status=onboarding), registro em `zenya_clients` (active=false, testing_mode='off'), e 7 registros em `onboarding_workflows` (um por fase: contract, intake, config, test_internal, test_client, go_live, post_go_live)
- [x] **AC-2.3:** O endpoint retorna HTTP 422 se `client_name` ou `business_type` estiverem ausentes
- [x] **AC-2.4:** O endpoint e idempotente — chamar 2x com mesmo `client_name + phone` retorna o onboarding existente, nao cria duplicata

### Gate check

- [x] **AC-3.1:** Task type `gate_check` registrado no task registry
- [x] **AC-3.2:** `gate_check` com payload `{ client_id, phase: "contract", conditions: ["contract_signed", "payment_confirmed"] }` verifica se ambas as flags estao true em `gate_details` JSONB. Se sim: marca phase como completed, avanca para proxima. Se nao: retorna `{ passed: false, missing: ["payment_confirmed"] }`
- [x] **AC-3.3:** Gate check para fase `intake` verifica: `{ conditions: ["intake_complete"] }` (default via PHASE_CONDITIONS)
- [x] **AC-3.4:** Gate check para fase `config` verifica: `{ conditions: ["brain_ready", "soul_prompt_ready", "kb_ready"] }` (default via PHASE_CONDITIONS)

### Polling cron para eventos de longa duracao

- [x] **AC-4.1:** Cron `onboarding_check_gates` roda a cada 1 hora
- [x] **AC-4.2:** O cron consulta todos os `onboarding_workflows` com status `in_progress` e verifica condicoes do gate
- [x] **AC-4.3:** Se gate satisfeito, cron avanca automaticamente para proxima fase via _advance_to_phase()
- [x] **AC-4.4:** Se fase in_progress > 72h: alerta Friday. Se > 5 dias (120h): marca stale + alerta Friday

### Comunicacao proativa com cliente

- [x] **AC-5.1:** Quando fase `contract` inicia, cliente recebe via WhatsApp (mensagem configurada em PHASE_MESSAGES)
- [x] **AC-5.2:** Quando fase `intake` inicia (gate passou), cliente recebe mensagem via _advance_to_phase()
- [x] **AC-5.3:** Quando fase `config` inicia, cliente recebe mensagem via _advance_to_phase()
- [x] **AC-5.4:** Quando fase `test_client` inicia, cliente recebe mensagem via _advance_to_phase()
- [x] **AC-5.5:** _send_whatsapp() pula silenciosamente se phone e None (log warning)

### Friday alerts

- [ ] **AC-6.1:** Se contrato nao assinado em 48h apos inicio, Friday alerta Mauro (pendente: requer cron com timeout especifico por condicao)
- [ ] **AC-6.2:** Se pagamento nao confirmado em 72h apos inicio, Friday alerta Mauro (pendente: mesma razao AC-6.1)
- [ ] **AC-6.3:** Se cliente nao responde intake em 48h, lembrete automatico via WhatsApp (pendente: ONB-2)
- [x] **AC-6.4:** Se qualquer fase fica `in_progress` por mais de 5 dias (120h), status muda para `stale` e Friday alerta Mauro (implementado no cron)

---

## Definition of Done

1. Todas as ACs de 1 a 6 marcadas como `[x]`
2. Teste e2e com cliente sintetico: `POST /onboarding/start` cria pipeline completo, gate_check funciona para fase contract
3. Cron `onboarding_check_gates` roda sem erro (pode nao encontrar gates para passar — so confirmar que nao crasha)
4. Nenhum dado de cliente real foi modificado
5. @qa validou via queries no Supabase

---

## O que NAO esta no escopo

- Automacao de contrato (n8n ja faz isso)
- Automacao de pagamento Asaas (existe, sera integrado na ONB-3)
- Intake de dados (ONB-2)
- Configuracao da Zenya (ONB-3)
- Smoke tests (ONB-5)
- Webhook_wait real (Fase 2 — usar polling)

---

## Arquivos Afetados

| Arquivo | Operacao |
|---------|----------|
| Supabase migration (nova) | CREATE TABLE `onboarding_workflows` + ALTER `zenya_clients` ADD `testing_mode` |
| `sparkle-runtime/runtime/onboarding/router.py` (NOVO) | Endpoint `/onboarding/start` |
| `sparkle-runtime/runtime/onboarding/service.py` (NOVO) | Logica de orquestracao |
| `sparkle-runtime/runtime/tasks/handlers/gate_check.py` (NOVO) | Handler gate_check |
| `sparkle-runtime/runtime/tasks/registry.py` | Registrar `gate_check` |
| `sparkle-runtime/runtime/scheduler.py` | Adicionar cron `onboarding_check_gates` |
| `sparkle-runtime/main.py` | Registrar router `/onboarding` |

---

## Tabelas Afetadas

| Tabela | Operacao |
|--------|----------|
| `onboarding_workflows` (NOVA) | CREATE |
| `zenya_clients` | ALTER ADD `testing_mode` |
| `clients` | INSERT (via endpoint) |
| `zenya_clients` | INSERT (via endpoint) |
| `runtime_tasks` | INSERT (gate_check tasks) |

---

*Story criada por Morgan (@pm) em 2026-04-05. Fonte: arquitetura Aria + benchmark analyst + review PM.*
