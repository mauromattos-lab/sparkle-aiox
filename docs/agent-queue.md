---
name: agent-queue
description: Kanban textual de handoff entre agentes — estado atual, bloqueios, responsável por item. Leia antes de qualquer sessão para saber ONDE estamos e quem tem a bola.
type: project
updated: 2026-03-30
---

# Agent Queue — Sparkle AIOX

> **REGRA ORION**: Este arquivo é a fonte de verdade sobre o que está EM EXECUÇÃO agora. Não consulte work_log para entender status de execução — work_log registra histórico, este arquivo registra fluxo ativo.

---

## Legenda de Status

| Status | Significado |
|--------|-------------|
| `PENDENTE` | Identificado, ainda não iniciado |
| `EM_EXECUCAO` | Agente com a bola agora |
| `AGUARDANDO_QA` | Entregue pelo dev, @qa precisa validar |
| `AGUARDANDO_MAURO` | Bloqueado por input/ação humana |
| `FUNCIONAL` | Implantado + testado + operacional em produção |
| `PARKED` | Suspenso por decisão estratégica — não bloqueia nada |
| `DEPRECATED` | Abordagem abandonada, substituída por outra |

---

## Sprint 8 — Em Andamento (2026-04-01)

### [SPRINT8-P1] Brain Separation — Runtime vs Produto
| Campo | Valor |
|-------|-------|
| **Status** | `FUNCIONAL` |
| **Responsável** | @dev (implementou) + @qa (aprovou 2026-04-01) |
| **Bloqueante** | — |
| **PRD** | `docs/sprints/sprint-8-prds.md` |
| **QA Report** | `docs/reviews/qa-p1-brain-separation.md` |
| **Nota** | 101 registros migrados, isolamento confirmado, pytest 10/10. Tech-debt: text search multi-palavra — resolve em P3 (embeddings). |

---

### [SPRINT8-P2] Friday Autônoma — Alertas + Handoff
| Campo | Valor |
|-------|-------|
| **Status** | `FUNCIONAL` |
| **Responsável** | @dev (implementou) + Orion (ativou crons 2026-04-01) |
| **Bloqueante** | — |
| **PRD** | `docs/sprints/sprint-8-prds.md` |

**Decisão Mauro (2026-04-01):** Cliente piloto = **Mauro** (número próprio). Mensagens de teste = Orion decide sem consultar Mauro.

**FUNCIONAL (2026-04-01):** 3 crons ativos no scheduler.py: risk_alert (09:30), billing_risk (08:45), upsell_opportunity (seg 07:30). Teste real: 6 alertas enviados no WhatsApp do Mauro ✅. Anti-spam validado: segunda execução = 0 enviados, 6 skipped_spam ✅. Serviço reiniciado: `systemctl restart sparkle-runtime` → active.

---

### [SPRINT8-P3] Embeddings + Busca Semântica Brain
| Campo | Valor |
|-------|-------|
| **Status** | `FUNCIONAL` |
| **Responsável** | @dev (implementou + fixes) + @qa (aprovou 2026-04-01) |
| **Bloqueante** | — |
| **QA** | APROVADO (2026-04-01) — AC-2 PASS, AC-3 PASS (threshold adaptativo 0.50→0.40), AC-6 PASS |
| **PO** | APROVADO — valor de negócio confirmado, sem riscos |
| **Nota** | OPENAI_API_KEY configurada na VPS. BRAIN_EMBEDDINGS_ENABLED=true. Backfill 101/101 chunks ($0.000172). Endpoint POST /brain/search em produção. Threshold adaptativo implementado. |

---

### [SPRINT8-P4] Lore — Zenya + Personagens
| Campo | Valor |
|-------|-------|
| **Status** | `AGUARDANDO_MAURO` |
| **Responsável** | Mauro (sessão noturna) → @dev |
| **Bloqueante** | Sessão de lore — Mauro disponível à noite (2026-04-01) |

---

### [SPRINT8-P5] Instagram DM Pilot
| Campo | Valor |
|-------|-------|
| **Status** | `PENDENTE` |
| **Responsável** | @devops (iniciar processo Meta app review) |
| **Bloqueante** | Aprovação Meta app (5-10 dias) |

**Decisão Mauro (2026-04-01):** Cliente piloto = **Mauro** (conta própria para todos os testes).

---

### [SPRINT8-P6] Mission Control — Painel de Implementação
| Campo | Valor |
|-------|-------|
| **Status** | `FUNCIONAL` |
| **Responsável** | @dev (implementou) + Orion (deploy 2026-04-01) |
| **Bloqueante** | — |

**Decisão Mauro (2026-04-01):** Mission Control vai no **Portal** (interface visual). WhatsApp descartado — sem capacidade visual. Modelo MCU: fases com estado por item, não barra de progresso.

**FUNCIONAL (2026-04-01):** `portal/app/mission-control/page.tsx` + `useAgentWorkItems.ts` + `AgentCard.tsx` deployed. Acessível em https://portal.sparkleai.tech/mission-control ✅. Supabase Realtime WebSocket ativo. 5 estados visuais (idle/active/blocked/done/error). Traefik config file-based em `/traefik/dynamic/portal.yml` no coolify-proxy.

---

### [SPRINT8-TECH] Supabase Connection Pool sob Carga
| Campo | Valor |
|-------|-------|
| **Status** | `PENDENTE` |
| **Responsável** | @architect |
| **Contexto** | QA identificou 502s "Server disconnected" em 7+ chamadas paralelas ao Supabase. Causa raiz: pool de conexões sem limite. Não bloqueia Sprint 8, mas precisa fix antes de carga real de clientes. |

---

## Itens em Execução

### ~~[ITEM-01] Script Auto-Clonagem v3~~ — FUNCIONAL ✅

Validado por Orion em 2026-03-30. Script clona os 4 workflows corretos (00, 01, 05, 07) — mínimo por cliente. Os 13 do material são recursos disponíveis, não todos obrigatórios. `system_prompt_id` não é parâmetro CLI — é o ID gerado após clone, usado em PUT separado. Script em `scripts/clone-zenya-client.py`.

---

### ~~[ITEM-02] Weekly Report V2~~ — AGUARDANDO ATIVAÇÃO ✅

PUT executado por Orion em 2026-03-30 (06:41 UTC). Workflow `U68uGoBZsRxXSARL` atualizado no n8n (12 nodes). **Pendente**: Mauro ativar manualmente no n8n UI (bug de webhook impede ativação via API). Após ativação → marcar FUNCIONAL.

---

### ~~[ITEM-03] Squads C-01/C-02 — Fix~~ — FUNCIONAL ✅

Validado por Orion em 2026-03-30. C-01 e C-02 corretos. Todos os fixes de @dev aplicados e documentados nos headers v1.1.0.

---

### [ITEM-04] Contract Generator — QA + Fix

| Campo | Valor |
|-------|-------|
| **Status** | `AGUARDANDO_MAURO` |
| **Responsável** | Mauro |
| **Bloqueante** | Obter `AUTENTIQUE_TOKEN` do painel Autentique e criar `contract-generator/.env` |
| **Próximo agente** | Pronto para uso após token configurado |
| **Tipo** | [ARTEFATO] — aprovado para go-live, fixes prioritários aplicados |

**QA concluído por @qa em 2026-03-30 — aprovado sem bloqueadores críticos.**

Fixes já aplicados por Orion:
- `contract-generator/.env.example` criado
- Campo valor: `step="any"` → `step="1"` (evita divergência valor/extenso no PDF)

Fixes menores pendentes (baixa prioridade — não bloqueiam uso):
- Validação matemática CPF/CNPJ (issue #6 do relatório)
- `btn-back-bottom` binding mover para `bindEvents()` (manutenibilidade)
- `updateFieldsForType` chamar no `DOMContentLoaded` (hardening)

**Ação Mauro**: Painel Autentique → Configurações → API → copiar token → criar `contract-generator/.env` com o token. Depois: `pip install -r requirements.txt && python contract-generator/server.py` → abrir `index.html`.

---

### ~~[ITEM-05] Cleanup Root~~ — FUNCIONAL ✅

Arquivos `tmp_*.py` removidos da raiz. 2026-03-29.

---

---

### ~~[ITEM-05] Bootstrap Files — 8 Agentes~~ — FUNCIONAL ✅

Criados por @architect em 2026-03-30: architect.md, devops.md, po.md, pm.md, sm.md, ux.md, data-engineer.md, squad-creator.md. Todos em `docs/operations/agent-bootstrap/`.

---

### ~~[ITEM-06] Fase 0.5 — Sparkle Brain~~ — FUNCIONAL ✅

| Campo | Valor |
|-------|-------|
| **Status** | `FUNCIONAL` |
| **Responsável** | @dev |
| **Bloqueante** | — |
| **Data** | 2026-04-01 |
| **Tipo** | brain_query + brain_ingest implementados no Runtime |

**Decisão 2026-04-01:** N8n não entra em desenvolvimento novo. Os 5 workflows JSON existentes em `n8n-workflows/` servem como **referência de lógica** para @dev reconstruir no Runtime (FastAPI + ARQ + Redis). Não serão importados no n8n.

**Schema Supabase já executado** ✅ (6 tabelas + 2 views + RLS + ivfflat index + função RPC `match_brain_chunks`)

**Referência de lógica** (não importar — usar como spec para Runtime):
- `brain-ingest-especialista.json` — ingesta conteúdo de especialista
- `brain-search.json` — busca vetorial + síntese Claude
- `brain-extract-dna.json` — extração das 6 camadas DNA via Opus
- `brain-detect-cargo-threshold.json` — geração automática de Cargo Agents
- `brain-ingest-cliente.json` — pipeline isolado por cliente

**Ação @dev**: Implementar os 5 handlers equivalentes no Runtime. Brain Fase A primeiro (endpoint de consulta simples via Friday — 3-5 dias).

---

### ~~[ITEM-07] Processos — Atualização AGENT_CONTEXT.md~~ — FUNCIONAL ✅

Executado por @architect em 2026-03-30.

---

## Bloqueados — Aguardando Mauro

### [BLOCK-01] Confeitaria Alexsandro — Go-live

| Campo | Valor |
|-------|-------|
| **Status** | `AGUARDANDO_MAURO` |
| **Responsável** | Mauro |
| **Bloqueante** | Conectar WhatsApp +5511976908238 na instância Z-API criada (QR code), mas ANTES precisa do fluxo completo da Gê |
| **Próximo agente** | @dev (criar Chatwoot inbox + ativar workflows + configurar fluxo) |

**Update 2026-03-31**: Instância Z-API criada. Fluxos n8n já existem (clonados). Falta: criar Chatwoot inbox, configurar id_conversa_alerta e número de escalonamento, ativar workflows n8n — conectar WhatsApp só depois disso.

**O que está FUNCIONAL**:
- System prompt no n8n (ID: `u7BDmAvPE4Sm6NXd`) configurado via PUT
- KB 193 registros no Supabase `zenya_knowledge_base`

**O que ainda é ARTEFATO (não funcional)**:
- Chatwoot inbox: NÃO criado (depende de instância Z-API)
- Workflows n8n: clonados mas INATIVOS
- `id_conversa_alerta`: placeholder, precisa ID real pós-inbox

**Ação Mauro**: Acessar painel Z-API → criar nova instância → copiar token + instance_id → passar para @dev.

---

### [BLOCK-02] Ensinaja Douglas — Go-live

| Campo | Valor |
|-------|-------|
| **Status** | `AGUARDANDO_MAURO` |
| **Responsável** | Mauro |
| **Bloqueante** | Resposta do Douglas (valores cursos, horários) — mensagem enviada |
| **Próximo agente** | @dev (atualizar KB + ativar workflows quando Douglas responder) |

**O que está FUNCIONAL**:
- System prompt no n8n (ID: `agEnqd5797ugaxEp`) configurado
- KB 35 registros no Supabase
- Fluxos n8n já existem (clonados, só ativar)

**O que ainda é ARTEFATO (não funcional)**:
- Workflows n8n: clonados mas INATIVOS (aguardam configuração final)
- Google Sheets `ensina_leads`: não criado
- Número do Douglas no escalar humano: placeholder

**Update 2026-03-31**: Mensagem para Douglas enviada. Aguardando resposta para completar KB + ativar.

---

### [BLOCK-03] Fun Personalize Julia — Go-live

| Campo | Valor |
|-------|-------|
| **Status** | `PENDENTE` |
| **Responsável** | @dev |
| **Bloqueante** | — |
| **Próximo agente** | @dev (integração Loja Integrada no Runtime, não no n8n) |

**Update 2026-04-01**: API key da Julia JÁ recebida. Integração Loja Integrada vai no **Runtime** (decisão: n8n apenas para clientes existentes já configurados — nada novo). @dev implementa handler no Runtime para consultar pedidos via API Loja Integrada.

---

### [BLOCK-04] Friday — End-to-end (Runtime)

| Campo | Valor |
|-------|-------|
| **Status** | `FUNCIONAL` |
| **Responsável** | — |
| **Bloqueante** | — |
| **Nota** | Z-API já aponta para Runtime desde 2026-03-31. Confirmado via logs: POST /friday/message recebidos. |

---

### [BLOCK-05] Gabriela — Campanha Meta Ads

| Campo | Valor |
|-------|-------|
| **Status** | `AGUARDANDO_MAURO` |
| **Bloqueante** | Adicionar saldo na conta de anúncios + enviar vídeos/criativos |
| **Próximo agente** | squad trafego-pago (ativar ad sets + adicionar criativos) |

**O que está CRIADO (2026-03-31)**:
- Campanha 1: Consórcio Imóvel — `act_1273799064911268`, PAUSED
- Campanha 2: Consórcio Veículo — `act_1273799064911268`, PAUSED
- 4 ad sets criados com public Advantage+ desabilitado, segmentação manual: Financiamento, Real Estate, Automóveis, Setor automotivo
- PAGE_ID: `456788517514349`, sem pixel, sem Instagram conectado via API

**Pendente para ir ao ar**:
- Adicionar saldo na conta da Gabriela
- Gabriela enviar vídeos/imagens para criativos
- Retargeting (Campanha 3): precisa de Instagram @handle para obter IG Account ID
- Considerar mudar objetivo para MESSAGES/OUTCOME_ENGAGEMENT (análise histórica: objetivo original era MESSAGES, R$6,74/conversa benchmark)

**Análise histórica CSV executada**: objetivo original era MESSAGES (não LEADS), frequência 4,96 (saturado), criativo de vídeo com 23% completion rate — base boa para recriar.

**Ação Mauro**: Adicionar saldo + enviar materiais de criativo para Gabriela.

---

### [BLOCK-06] Vitalis — Inteligência de Conversas

| Campo | Valor |
|-------|-------|
| **Status** | `AGUARDANDO_MAURO` |
| **Bloqueante** | Enviar mensagem para João Lúcio + conectar número WhatsApp na Z-API (QR code) |
| **Próximo agente** | @dev (lógica no Runtime — não importar blueprints n8n) |

**Decisão 2026-04-01:** Os 3 blueprints JSON não são importados no n8n. Servem como referência de lógica para implementação no Runtime.

**O que ainda é necessário**:
- Mauro: enviar mensagem para João + conectar WhatsApp Z-API (QR code)
- @dev: executar `docs/stories/vitalis-supabase-setup.sql` + implementar handlers no Runtime
- Classifier prompt em `squads/trafego-pago/` — referência para @dev

---

---

## PARKED

### Friday Gateway — Webhook 404

| Campo | Valor |
|-------|-------|
| **Status** | `PARKED` |
| **Decisão** | Mauro: "vamos resolver depois que tiver mais estruturados" |
| **Contexto** | `/webhook/gateway` retorna 404 persistentemente. Causa raiz: registro de webhook corrompido após múltiplos PUTs. Não bloqueia nenhum go-live de cliente. |

---

## DEPRECATED

### Master Workflow Parametrizado

| Campo | Valor |
|-------|-------|
| **Status** | `DEPRECATED` |
| **Motivo** | Substituído pelo modelo v3 clone + delta. Secretária v3 (97 nodes) é superior — agentes só clonam e aplicam delta por cliente. |

---

## Itens FUNCIONAIS (referência — não repetir)

| Item | Status | Data |
|------|--------|------|
| Plaka — system prompt enxuto (4.935 chars) no n8n | FUNCIONAL | 2026-03-27 |
| Plaka — Google Sheets KB (52 scripts / 5 abas) | FUNCIONAL | 2026-03-27 |
| Plaka — Workflow rastrear pedido (ID: `jag4nERPiqJBalYm`) ativado | FUNCIONAL | 2026-03-27 |
| Vitalis — dados Meta Ads coletados no Supabase (77 dias) | FUNCIONAL | 2026-03-26 |
| Vitalis — relatório Score 55/100 no Supabase | FUNCIONAL | 2026-03-27 |
| Gabriela — partner assignment BM configurado | FUNCIONAL | 2026-03-27 |
| Sparkle ZApi Router (ID: `LMcmB2oYX5RGnFxc`) | FUNCIONAL (ativo, routing correto, aguarda Z-API redirect) | 2026-03-29 |
| Friday Brain (ID: `Izoupz82zVf6kZRQ`) | FUNCIONAL (ativo, aguarda Z-API redirect para testar e2e) | 2026-03-28 |
| Friday Notifier (ID: `zxznYpW2PBhJrGjV`) | FUNCIONAL (ativo, aguarda e2e) | 2026-03-28 |
| Sparkle Gateway (ID: `hCukbZX875Y18ThZ`) | FUNCIONAL (ativo, 16 nodes, aguarda e2e) | 2026-03-29 |
| Confeitaria — system prompt no n8n (ID: `u7BDmAvPE4Sm6NXd`) | FUNCIONAL | 2026-03-29 |
| Confeitaria — KB 193 registros Supabase | FUNCIONAL | 2026-03-29 |
| Ensinaja — system prompt no n8n (ID: `agEnqd5797ugaxEp`) | FUNCIONAL | 2026-03-27 |
| Ensinaja — KB 35 registros Supabase | FUNCIONAL | 2026-03-27 |
| AGENT_CONTEXT.md — contexto obrigatório para todos os agentes | FUNCIONAL (desatualizado — ITEM-07 pendente) | 2026-03-29 |
| sparkle-os-processes.md — 6 processos definidos | FUNCIONAL | 2026-03-29 |
| Landing pages nicho (confeitaria/escola/ecommerce/consorcio) | DEPLOYED | 2026-03-29 |
| Portal logout fix (httpOnly cookie server-side) | FUNCIONAL | 2026-03-29 |
| Supabase: friday_tasks + 4 views Friday | EXISTEM | 2026-03-29 |
| Cleanup root tmp_*.py (16 arquivos) | FUNCIONAL | 2026-03-29 |
| Supabase: tabela `agent_queue` + view `v_agent_queue_active` (esteira da fábrica) | FUNCIONAL | 2026-03-29 |
| Bootstrap por agente: `docs/operations/agent-bootstrap/` (@dev, @qa, @analyst) | FUNCIONAL | 2026-03-29 |
| Plaka delta-v3.md — spec técnica deltas (agente-off gate + Google Sheets KB) | FUNCIONAL | 2026-03-29 |
| Plaka agente-off gate — node `Check Agente-Off Gate` no workflow 371QcYGrXmZ1n8bV | FUNCIONAL | 2026-03-29 |
| Weekly Report V2 (ID: U68uGoBZsRxXSARL, 12 nodes) — ativo no n8n, segunda 9h | FUNCIONAL | 2026-03-30 |
| scripts/clone-zenya-client.py — clona 4 workflows core (00,01,05,07), validado | FUNCIONAL | 2026-03-30 |
| SOUL.md v1.1 — alma universal da Zenya em docs/zenya/SOUL.md | FUNCIONAL | 2026-03-29 |
| Contract generator Autentique — server.py + script.js + index.html | ARTEFATO (QA em execução) | 2026-03-30 |
| Supabase RLS — 8 políticas aplicadas (vitalis, prospects, friday_tasks) | FUNCIONAL | 2026-03-29 |
| Bootstrap files — 8 agentes (architect, devops, po, pm, sm, ux, data-engineer, squad-creator) | FUNCIONAL | 2026-03-30 |
| Constitution v1.1 — Princípio 8 (colaboração proativa) + agent-toolkit-standard atualizado | FUNCIONAL | 2026-03-30 |
| Fase 0.5 brief — docs/architecture/aios-v2/fase-0.5-megabrain-dev-brief.md | FUNCIONAL | 2026-03-30 |
| 02-data-schema.sql — 4 bugs corrigidos, SQL executado com sucesso no Supabase | FUNCIONAL | 2026-03-30 |
| AGENT_CONTEXT.md — atualizado com Princípio 8, 11 agentes, Sparkle Brain section | FUNCIONAL | 2026-03-30 |
| Plaka workflow 371QcYGrXmZ1n8bV — corrigido (model gpt-4.1-mini) + reativado | FUNCIONAL | 2026-03-31 |
| Sprint 8 Runtime — onboarding autônomo (scrape → KB → Supabase → clone n8n) | FUNCIONAL | 2026-03-31 |
| Gabriela — 2 campanhas + 4 ad sets criados via Meta API (PAUSED, aguardando saldo) | ARTEFATO | 2026-03-31 |
| brain_query + brain_ingest (Runtime) | FUNCIONAL | 2026-04-01 |
| S2-01 loja_integrada_query handler | FUNCIONAL (aguarda API key Julia) | 2026-04-01 |
| S3-01/S3-02 crons daily/weekly briefing | FUNCIONAL | 2026-04-01 |
| S3-03 /agent/invoke endpoint | FUNCIONAL | 2026-04-01 |
| S4-01 Observer Pattern /zenya/learn | FUNCIONAL | 2026-04-01 |
| S4-02 Gap Report cron segunda 8h | FUNCIONAL | 2026-04-01 |
| scheduler.py bug fix — async/await corrigido (coroutine não era descartada) | FUNCIONAL | 2026-04-01 |
