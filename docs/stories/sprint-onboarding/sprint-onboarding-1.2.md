---
epic: EPIC-ONBOARDING — Zenya Atendente Onboarding Pipeline
story: 1.2
title: Fase 1 — Contrato Automatizado via Autentique
status: Implemented — aguardando @qa
priority: P1 — Gate 1 depende desta story e de 1.3 (paralelas)
executor: "@dev (implementacao) -> @qa (validacao)"
sprint: Sprint 1 (semana 2-3, paralelo com 1.3)
depends_on: [sprint-onboarding-1.1]
unblocks: [Gate 1 — contrato + pagamento]
estimated_effort: M — 3-4 dias @dev
paralelo_com: [sprint-onboarding-1.3]
prd_ref: Story 1.2 (FR2, FR8, FR9)
---

# Story 1.2 — Fase 1: Contrato Automatizado via Autentique

## Story

**Como** Mauro,
**Quero** que ao registrar um novo cliente no sistema, o contrato seja gerado automaticamente e enviado para assinatura digital,
**Para que** o processo juridico nao seja um gargalo manual e o cliente receba o contrato em minutos, nao horas.

---

## Contexto Tecnico

**Por que agora:** Contrato e o primeiro gate do onboarding (Gate 1 = contrato assinado + pagamento confirmado). Sem automacao, Mauro precisa gerar o contrato manualmente em cada cliente novo. Com 20 clientes, isso e inviavel.

**O que ja existe:**
- Token Autentique disponivel no `.env` (credencial configurada)
- Workflow n8n 20 (Autentique) existente para uso manual — mas nao integrado ao pipeline Runtime
- Endpoint `POST /webhooks/autentique` criado na ONB-4 (recebe evento document_signed)
- Handler de onboarding orquestrador (ONB-1) ja cria `onboarding_workflows` com fase `contract` como `pending`

**O que falta (escopo desta story):**
1. Handler `generate_contract` que chama API Autentique para criar documento a partir de template
2. Template de contrato parametrizado (nome, tier, valor, data de inicio)
3. Envio por email + link WhatsApp para o cliente
4. Webhook Autentique marca `gates_passed.contract = true`
5. Fallback: upload manual de contrato assinado

**Decisao de PM:** Autentique e o caminho principal. Fallback de upload manual e obrigatorio para Fase 1 (nem sempre o cliente vai assinar digitalmente).

---

## Template de Contrato

O template deve ter os seguintes placeholders:

| Placeholder | Fonte |
|-------------|-------|
| `{empresa}` | `client_name` |
| `{cnpj_cpf}` | intake_data (opcional na Fase 1) |
| `{valor_mensal}` | `mrr_value` |
| `{plano}` | `plan` (Essencial/Profissional/Premium) |
| `{escopo}` | descricao por tier (hardcoded por plano) |
| `{data_inicio}` | data atual + 5 dias uteis |
| `{signatario_nome}` | coletado no payload de registro |
| `{signatario_email}` | coletado no payload de registro |

**Escopo por tier:**
- Essencial: "Chat IA 24h (texto e audio), persona personalizada, escalacao para humano, Brain DNA"
- Profissional: "Essencial + Agendamento, lembretes, cobranca PIX, recuperacao de leads"
- Premium: "Profissional + Assistente interno, voz (Retell), multi-alerta, setup prioritario"

---

## Criterios de Aceitacao

### Template e Geracao do Documento

- [x] **AC-1.1:** Template de contrato salvo em `sparkle-runtime/runtime/onboarding/templates/contract_template.md` (Markdown formatado com placeholders)
- [x] **AC-1.2:** Handler `generate_contract` preenche todos os placeholders com dados do contexto do onboarding
- [x] **AC-1.3:** Documento criado via `POST https://api.autentique.com.br/v2/graphql` (GraphQL createDocument) com: titulo (`"Contrato Zenya — {empresa}"`), conteudo preenchido, signatario (email + nome)
- [x] **AC-1.4:** Document ID retornado pela Autentique e salvo em `onboarding_workflows.gate_details` (campo `autentique_document_id`)

### Envio ao Cliente

- [x] **AC-2.1:** Apos criacao do documento, sistema envia email automaticamente (via Autentique — a propria API envia o link de assinatura)
- [x] **AC-2.2:** Se `phone` do cliente esta preenchido, sistema envia link de assinatura via WhatsApp (Z-API): "Oi [nome]! Aqui esta o contrato da sua Zenya para assinar: [link_autentique]"
- [x] **AC-2.3:** Se `phone` esta vazio, envio por email e suficiente (log info — nao falha)

### Webhook e Gate

- [x] **AC-3.1:** Quando Autentique dispara webhook `document_signed`, endpoint `POST /webhooks/autentique` (criado em ONB-4) recebe e processa
- [x] **AC-3.2:** O processamento do webhook identifica o `onboarding_workflows` correto via `autentique_document_id` no `gate_details`
- [x] **AC-3.3:** Campo `gates_passed.contract = true` e atualizado em `onboarding_workflows` para a fase `contract`
- [x] **AC-3.4:** Evento registrado em `onboarding_events` (tabela de auditoria — da Story 1.1): `{ client_id, phase: "contract", event: "contract_signed", timestamp }`
- [x] **AC-3.5:** Friday notificada: "Contrato de [cliente] assinado. Aguardando pagamento para Gate 1."

### Fallback Manual

- [x] **AC-4.1:** Task type `mark_contract_signed` registrado — permite marcar manualmente `gates_passed.contract = true` para casos onde cliente nao assina digitalmente
- [ ] **AC-4.2:** SOP de fallback documentado no `docs/operations/sop-contrato-onboarding.md` (criado pela ONB-4) inclui instrucao de como usar esta task manualmente

### Idempotencia e Seguranca

- [x] **AC-5.1:** Se `generate_contract` e chamado 2x para o mesmo client_id, nao cria 2 documentos — verifica se `autentique_document_id` ja existe em `gate_details`
- [ ] **AC-5.2:** Webhook Autentique valida assinatura/token de autenticidade antes de processar (nao aceita qualquer POST)
- [x] **AC-5.3:** Handler nao e ativado para clientes com `testing_mode = live` (producao) que nao estao em onboarding

---

## Integration Verification

- **IV1:** Integracao nova — nenhum fluxo existente e afetado
- **IV2:** Webhook Autentique usa endpoint criado na ONB-4 — confirmar que endpoint responde antes de testar
- **IV3:** Envio WhatsApp usa a instancia Z-API da Sparkle (nao a do cliente) — confirmar que instancia esta ativa
- **IV4:** Clientes ativos (Alexsandro, Ensinaja, Plaka, Fun Personalize) nao recebem nenhuma mensagem

---

## Definition of Done

1. Todas as ACs de 1 a 5 marcadas como `[x]`
2. Teste com cliente ficticio: documento criado na Autentique, link enviado (verificar no dashboard Autentique), webhook simulado com curl marca contract=true
3. @qa validou via Supabase que evento esta em `onboarding_events`
4. @qa confirmou que nenhum dado de cliente real foi modificado
5. Fallback manual testado: `mark_contract_signed` funciona via chamada direta

---

## O que NAO esta no escopo

- Assinatura de contrato no portal web (Fase 2)
- PDF gerado localmente (Autentique gera — nao precisamos de PDF local)
- Multi-signatarios (Fase 2)
- Contratos de rescisao (Fase 2)
- Migrations de schema (feitas na Story 1.1)

---

## Arquivos Afetados

| Arquivo | Operacao |
|---------|----------|
| `sparkle-runtime/runtime/tasks/handlers/generate_contract.py` (NOVO) | Handler de geracao de contrato |
| `sparkle-runtime/runtime/tasks/handlers/mark_contract_signed.py` (NOVO) | Handler de fallback manual |
| `sparkle-runtime/runtime/onboarding/templates/contract_template.md` (NOVO) | Template de contrato |
| `sparkle-runtime/runtime/onboarding/contract_filler.py` (NOVO) | Preenchimento de placeholders |
| `sparkle-runtime/runtime/tasks/registry.py` | Registrar `generate_contract`, `mark_contract_signed` |
| `sparkle-runtime/runtime/webhooks/handlers.py` | Adicionar logica de processamento do evento `document_signed` |

---

## Tabelas Afetadas

| Tabela | Operacao |
|--------|----------|
| `onboarding_workflows` | UPDATE (gate_details com autentique_document_id, gates_passed.contract) |
| `onboarding_events` | INSERT (eventos contract_sent, contract_signed) |
| `runtime_tasks` | INSERT (task generate_contract) |

---

## Pipeline AIOS

| Etapa | Agente | Entrega |
|-------|--------|---------|
| Implementacao | @dev | Handler generate_contract, template, webhook handler |
| Validacao | @qa | Smoke test com cliente ficticio + verificacao Supabase |
| Deploy | @devops | Deploy VPS + restart Runtime |

---

*Story criada por River (@sm) em 2026-04-05. Fonte: PRD Zenya Onboarding System E2E (Story 1.2, FR2, FR8, FR9).*
