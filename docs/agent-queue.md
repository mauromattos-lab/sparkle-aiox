---
name: agent-queue
description: Kanban textual de handoff entre agentes — estado atual, bloqueios, responsável por item. Leia antes de qualquer sessão para saber ONDE estamos e quem tem a bola.
type: project
updated: 2026-04-04
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

## Visão do Sistema — Onde Estamos

```
AIOS (sistema nervoso)  +  Mega Brain (cérebro)  +  Runtime (corpo)  =  SISTEMA
     ✅ documentado            ✅ pipeline no Runtime   ✅ rodando
     ⚠️ vive em sessões       ✅ SYS-1 ingestão        ✅ produção
                               ⚠️ SYS-4 DNA pendente
     
PRÓXIMO PASSO: SYS-4 (DNA Schema) + SYS-6 (Painel de Comando) — ambos desbloqueados
```

---

## Sprint SYSTEM — Fechar o Sistema (próximo)

### [SYS-1] Pipeline de Ingestão Mega Brain no Runtime

| Campo | Valor |
|-------|-------|
| **Status** | `FUNCIONAL` |
| **Responsável** | @dev |
| **Impacto** | Brain aprende de qualquer fonte (PDFs, transcrições, cursos, vídeos). Fecha o ciclo Brain como cérebro coletivo. |
| **Referências** | `docs/brain/dna-finch-mechanism.md`, `docs/architecture/mega-brain-analysis.md`, `docs/strategy/mega-brain-evaluation.md` |
| **Implementação** | Pipeline 6 fases: raw → chunking → canonicalização → insight extraction → narrative synthesis → vetorização. YouTube + URL + direct input funcionando. Apify fallback para transcrições YouTube. |
| **Arquivos** | `runtime/tasks/handlers/brain_ingest_pipeline.py`, `extract_insights.py`, `cross_source_synthesis.py`, `narrative_synthesis.py` |

---

### [SYS-2] Agent Context Persistente — Regra 1 do Sparkle OS

| Campo | Valor |
|-------|-------|
| **Status** | `FUNCIONAL` |
| **Responsável** | @dev |
| **Impacto** | Todo agente ativado pelo Runtime já nasce sabendo: ferramentas, outros agentes, recursos, processos. Não depende de sessão Claude Code. |
| **Implementação** | 16 blocos de contexto populados (5 global system + 5 process + 6 agent bootstraps). Assembler com 4 camadas e budget de 4000 tokens. |
| **Arquivos** | `runtime/context/assembler.py`, `runtime/context/seed_blocks.py` |

---

### [SYS-3] Handoff Automático entre Agentes — Regra 2 do Sparkle OS

| Campo | Valor |
|-------|-------|
| **Status** | `FUNCIONAL` |
| **Responsável** | @dev |
| **Impacto** | Agente A termina → dispara agente B automaticamente via workflow engine. Sem Orion no meio. Sem Mauro no meio. |
| **Implementação** | Workflow engine com 3 templates (onboarding_zenya, content_production, brain_learning). Encadeamento automático via _steps em context JSONB. |
| **Arquivos** | `runtime/workflows/templates.py`, `runtime/workflow/router.py` |

---

### [SYS-4] DNA Schema por Cliente — Brain Estruturado

| Campo | Valor |
|-------|-------|
| **Status** | `PENDENTE` |
| **Responsável** | @architect (design) → @dev (implementação) |
| **Bloqueante** | SYS-1 ✅ FUNCIONAL — pode começar |
| **Impacto** | Cada cliente tem DNA extraído automaticamente (tom, persona, regras, diferenciais). Zenya nasce mais inteligente. Onboarding semi-autônomo. |
| **Referências** | `docs/archive/reviews/architect-megabrain-review.md` (schema `zenya_config` proposto) |

---

### [SYS-5] Observer Pattern Real — Auto-evolução Estágio 1

| Campo | Valor |
|-------|-------|
| **Status** | `FUNCIONAL` |
| **Responsável** | @dev |
| **Impacto** | Agentes detectam lacunas e reportam. Sistema auto-implementa gaps aprovados. |
| **Implementação** | auto_implement_gap completo (4 tipos: knowledge, capability, handler, agent). API: /observer/gaps, /observer/summary. 33 E2E tests validados. |
| **Arquivos** | `runtime/tasks/handlers/auto_implement_gap.py`, `runtime/observer/router.py` |

---

### [SYS-6] Painel de Comando — Interface do Mauro com o Sistema

| Campo | Valor |
|-------|-------|
| **Status** | `PENDENTE` |
| **Responsável** | @architect (design) → @ux + @dev (implementação) |
| **Bloqueante** | SYS-1/2/3 ✅ todos FUNCIONAL — pode começar |
| **Impacto** | Mauro pilota o sistema visualmente. Não é dashboard — é experiência de comando. |
| **Stack** | Next.js (portal/ já existe), Supabase Realtime WebSocket, portal.sparkleai.tech |
| **Lei 15** | "Se parece com Notion ou Trello, está errado. Se parece com Overwatch ou Final Fantasy, está no caminho certo." |
| **Evolução** | SYS-1→Brain ao vivo. SYS-2→Agentes e skills visíveis. SYS-3→Workflows ao vivo. SYS-4→DNA sendo extraído. SYS-5→Gaps e novos agentes propostos. |

---

## Sprint OPS — Clientes (em andamento)

### [OPS-3] Zenya Ensinaja — Go-Live

| Campo | Valor |
|-------|-------|
| **Status** | `PENDENTE` — segunda-feira |
| **Responsável** | @dev |
| **Bloqueante** | Feriado (02/04). Dados do Douglas já extraídos (10 cursos). |
| **Story** | `docs/stories/sprint-ops/ops-3.story.md` |
| **Impacto** | R$650/mês desbloqueado |
| **Nota** | WhatsApp: (12) 98197-4622. Endereço: Rua Comendador Custódio Vieira, 198 — Lorena. KB para ingerir com dados completos. |

---

### [OPS-5] Instagram DM Pilot

| Campo | Valor |
|-------|-------|
| **Status** | `AGUARDANDO_MAURO` |
| **Responsável** | Mauro (~45 min) → @dev |
| **Bloqueante** | Mauro criar app no Meta for Developers |
| **Guia** | `docs/operations/meta-instagram-app-setup.md` |
| **Nota** | Verify token já configurado na VPS. Mauro precisa: (1) verificar conta Instagram Professional, (2) criar app tipo Business, (3) gerar System User Token. |

---

### [OPS-6] VPS Path Unification

| Campo | Valor |
|-------|-------|
| **Status** | `PENDENTE` |
| **Responsável** | @devops |
| **Bloqueante** | — |
| **Impacto** | Eliminar confusão `/opt/sparkle-runtime/` vs `/opt/sparkle-runtime/sparkle-runtime/`. Unificar em um só path. Adicionar `.venv/` ao .gitignore. |

---

## Bloqueados — Aguardando Mauro

### [BLOCK-03] Fun Personalize Julia — Go-live

| Campo | Valor |
|-------|-------|
| **Status** | `AGUARDANDO_CREDENCIAIS` |
| **Responsável** | Mauro (cobrar API key Julia + criar Z-API instance) → @qa (validação e2e) |
| **Bloqueante** | API key Loja Integrada (Julia não enviou) + Z-API instance para Julia |
| **Nota** | Código PRONTO: handler `send_character_message` + integração Loja Integrada + intent detection. Bug crítico corrigido: handler não existia no registry (afetaria todos os clientes Zenya multi-tenant). Falta: deploy VPS + credenciais + QA. |

---

### [BLOCK-04] Lore — Zenya + Personagens

| Campo | Valor |
|-------|-------|
| **Status** | `AGUARDANDO_MAURO` |
| **Responsável** | Mauro (sessão) → @dev (popular `character_lore` no banco) |
| **Bloqueante** | Sessão de lore com Mauro |
| **Nota** | Lore canônico já aprovado (`docs/zenya/zenya-lore-canonical.md`). Open questions: awakening event, Juno, ensemble characters, relação Zenya-Brain, formato YouTube. |

---

### [BLOCK-05] Gabriela — Campanha Meta Ads

| Campo | Valor |
|-------|-------|
| **Status** | `AGUARDANDO_MAURO` |
| **Bloqueante** | Adicionar saldo + enviar criativos |
| **Nota** | 2 campanhas + 4 ad sets criados (PAUSED). Aguardando saldo e vídeos/imagens. |

---

### [BLOCK-06] Vitalis — Inteligência de Conversas

| Campo | Valor |
|-------|-------|
| **Status** | `AGUARDANDO_MAURO` |
| **Bloqueante** | Mensagem para João Lúcio + conectar WhatsApp na Z-API |
| **Nota** | SQL pronto. Implementação vai no Runtime. |

---

### [BLOCK-07] Contract Generator — Token Autentique

| Campo | Valor |
|-------|-------|
| **Status** | `AGUARDANDO_MAURO` |
| **Bloqueante** | Obter `AUTENTIQUE_TOKEN` do painel |
| **Nota** | QA aprovado. Fixes aplicados. Pronto para uso após token. |

---

### [BLOCK-08] Supabase Connection Pool

| Campo | Valor |
|-------|-------|
| **Status** | `FUNCIONAL` |
| **Responsável** | @dev |
| **Implementação** | Thread-local Supabase client proxy. Fix para 502s em chamadas paralelas. |
| **Arquivos** | `runtime/db.py` |

---

## PARKED

### Friday Gateway — Webhook 404
| **Status** | `PARKED` — Mauro: "vamos resolver depois que tiver mais estruturados" |

---

## DEPRECATED

### Master Workflow Parametrizado
| **Status** | `DEPRECATED` — Substituído por clone + delta v3 |

---

## Itens FUNCIONAIS — Concluídos (referência)

### Sprint SYSTEM + Infra (2026-04-04)

| Item | O que faz | Data |
|------|-----------|------|
| SYS-1 Brain Pipeline | Pipeline 6 fases (raw→chunking→canonicalização→insights→narrative→vetorização). YouTube + URL + direct input | 2026-04-04 |
| SYS-2 Agent Context | 16 blocos de contexto, assembler 4 camadas, budget 4000 tokens | 2026-04-04 |
| SYS-3 Handoff Workflows | 3 templates (onboarding_zenya, content_production, brain_learning) | 2026-04-04 |
| SYS-5 Observer | auto_implement_gap (4 tipos), /observer/gaps, /observer/summary, 33 E2E tests | 2026-04-04 |
| BLOCK-08 Connection Pool | Thread-local Supabase proxy, fix 502s paralelas | 2026-04-04 |

### Sprint OPS + Core + Brain (2026-04-02)

| Item | O que faz | Data |
|------|-----------|------|
| OPS-1 Registry Fix | 15 intents no dispatcher, 6 handlers órfãos registrados, db_execute() adicionado | 2026-04-02 |
| OPS-2 Zenya Alexsandro | Go-live formalizado. 729 mensagens, 99.86% sucesso | 2026-04-02 |
| OPS-4 Friday Proativa | 8 crons: billing_risk 08:45, risk_alert 09:30, upsell_opportunity seg 07:30. Anti-spam validado | 2026-04-02 |
| CORE-1 Workflow Engine | Tabela workflow_runs + encadeamento automático via _steps em context JSONB | 2026-04-02 |
| CORE-2 activate_agent | @analyst real com 4 tools (brain_query, supabase_read, web_search, calculate). Tool_use loop. 7 camadas segurança | 2026-04-02 |
| BRAIN-1 Auto-ingestão | Brain aprende das conversas automaticamente. Score relevância > 0.6. Isolamento Friday/Zenya | 2026-04-02 |

### Sprint 8 (2026-04-01)

| Item | O que faz | Data |
|------|-----------|------|
| S8-P1 Brain Separation | 101 registros migrados, isolamento confirmado, pytest 10/10 | 2026-04-01 |
| S8-P2 Friday Autônoma | 3 crons ativos, 6 alertas enviados, anti-spam validado | 2026-04-01 |
| S8-P3 Embeddings Brain | OpenAI embeddings, threshold adaptativo 0.40, backfill 101 chunks | 2026-04-01 |
| S8-P6 Mission Control | Portal com Realtime WebSocket, 5 estados visuais, Traefik config | 2026-04-01 |

### Infraestrutura anterior

| Item | Data |
|------|------|
| Plaka system prompt + KB 52 scripts + workflow rastrear pedido | 2026-03-27 |
| Vitalis dados Meta Ads 77 dias + relatório Score 55/100 | 2026-03-27 |
| Sparkle ZApi Router + Friday Brain + Friday Notifier + Gateway | 2026-03-29 |
| sparkle-os-processes.md — 6 processos definidos | 2026-03-29 |
| Landing pages nicho (confeitaria/escola/ecommerce/consorcio) | 2026-03-29 |
| scripts/clone-zenya-client.py | 2026-03-30 |
| SOUL.md v1.1 — alma universal Zenya | 2026-03-29 |
| Bootstrap 8 agentes + Constitution v1.1 | 2026-03-30 |
| Supabase schema completo (6 tabelas + RLS + pgvector) | 2026-03-30 |
| brain_query + brain_ingest Runtime | 2026-04-01 |
| loja_integrada_query handler | 2026-04-01 |
| Observer Pattern /zenya/learn + Gap Report cron | 2026-04-01 |
| scheduler.py async bug fix | 2026-04-01 |
| Weekly Report V2 n8n | 2026-03-30 |
