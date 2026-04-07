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
                               ✅ SYS-4 DNA funcional
                               ✅ Brain curadoria 3x/dia (02h/10h/18h)
                               ✅ Content fallback billing
                               ✅ Onboarding pipeline fix (brain_owner + template)
                               ✅ Friday triggers de negócio (3 novos)
                               ✅ Sentry error tracking (aguarda DSN)
                               ✅ Cron logging (17 crons monitorados)
                               ✅ Relatório mensal honesto
                               ✅ .env permissions hardened
     
PLANO PONTE: Semana 0 ✅ | Semana 1 ✅ | Semana 2 ✅ | Camada 2 ✅
                               
CAMADA 2 CONSOLIDADA (2026-04-05):
  ✅ C2-B1: 3 namespaces (mauro-personal 82, sparkle-lore 50, sparkle-ops 55)
  ✅ C2-B1: Friday auto-ingere áudios do Mauro
  ✅ C2-B2: Pipeline enforcement com gates (HTTP 422 + Friday notification)
  ✅ C2-B3: Consulta prioritária (Friday, agentes, Zenya)

PRÓXIMO: Camada 3 — Órgãos (Conteúdo = trabalho dedicado)
```

---

## Sprint SECURITY — Consolidação Pós-Auditoria

### [SEC-1] P0 Security Fixes — Brownfield Audit

| Campo | Valor |
|-------|-------|
| **Status** | `FUNCIONAL` |
| **Responsável** | @architect (spec) → @dev (impl) → @qa (review + smoke) → @devops (deploy) |
| **Pipeline** | Processo 3 completo — AIOS pipeline enforced |
| **Impacto** | 5 vulnerabilidades P0 corrigidas: auth fail-closed, Asaas webhook token, GETs protegidos, rate limit trusted proxy, handler registry clarificado |
| **Arquivos** | `middleware/auth.py`, `middleware/rate_limit.py`, `billing/router.py`, `config.py`, `tasks/registry.py` |
| **Story** | `docs/stories/sprint-core/sec-1-p0-security-fixes.md` |
| **QA Plan** | `docs/stories/sprint-core/sec-1-qa-validation-plan.md` |
| **Nota** | Bug de schema `payments.billing_type` detectado durante smoke test — item P1 separado |

---

### [SEC-2] P1 Code Quality Fixes — Brownfield Audit

| Campo | Valor |
|-------|-------|
| **Status** | `FUNCIONAL` |
| **Responsável** | @architect (spec) → @dev (3 batches) → @qa (7/7 PASS) → @devops (deploy) |
| **Pipeline** | Processo 3 completo — AIOS pipeline enforced |
| **Impacto** | 7 bugs P1: billing blocking/alert, embedding centralizado, brain RPC, CORS, ARQ crons, atomic dedup |
| **Migrations** | `brain_namespace_stats()` RPC + `increment_confirmation_count()` RPC — aplicadas via MCP |
| **Story** | `docs/stories/sprint-core/sec-2-p1-code-quality-fixes.md` |

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
| **Status** | `FUNCIONAL` |
| **Responsável** | @dev |
| **Impacto** | Cada cliente tem DNA extraído automaticamente (tom, persona, regras, diferenciais). Zenya nasce mais inteligente. Onboarding semi-autônomo. |
| **Implementação** | 8 categorias DNA (tom, persona, regras, diferenciais, publico_alvo, produtos, objecoes, faq). Extração via Haiku. Auto-trigger no pipeline de ingestão. Cron semanal (seg 4h BRT). Batch endpoint para todos os clientes. |
| **Arquivos** | `runtime/tasks/handlers/extract_client_dna.py`, `runtime/brain/dna_router.py` |
| **API** | GET /brain/client-dna/{id}, POST /brain/extract-dna/{id}, POST /brain/extract-dna-all |

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
| **Status** | `FUNCIONAL` — Portal conectado ao Runtime (verificado 2026-04-07) |
| **Responsável** | @dev (concluído) |
| **Impacto** | Mauro pilota o sistema visualmente. Não é dashboard — é experiência de comando. |
| **Stack** | Next.js (portal/ já existe), Supabase Realtime WebSocket, portal.sparkleai.tech |
| **Implementação** | TIER 1 (Friday WhatsApp): cockpit_summary diário 08h BRT funcional. TIER 2 API: 4 endpoints (overview, clients, agents, activity) respondendo 200 com dados reais. Portal proxy routes configurados e RUNTIME_API_KEY no portal/.env da VPS. |
| **API** | GET /cockpit/overview (MRR R$5.491, 7 clientes, 398 tasks/24h) ✅ |

---

## Sprint VERTICAL — Migração Clientes n8n → Runtime

### [VERT1-F0] Fase 0 — Pré-requisitos do Sistema

| Campo | Valor |
|-------|-------|
| **Status** | `FUNCIONAL` |
| **Responsável** | @dev |
| **Impacto** | 5 ações de sistema concluídas: client_id padronizado UUID, registros zenya_clients criados (Douglas/Plaka), DNA extraído (Alexsandro 24 items/6 cats, Douglas 51 items/8 cats), brain_chunks órfãos atribuídos (513), conversation_history órfãos atribuídos (146) |
| **Story** | `docs/stories/sprint-core/vert1-fase0-system-prerequisites.md` |
| **Fixes** | Constraint `client_dna_dna_type_check` duplicada removida, max_tokens DNA extraction 4096→8192, KB fallback em `_get_client_chunks` |

---

### [VERT1-W1] Wave 1 — Migração Clientes n8n → Runtime

| Campo | Valor |
|-------|-------|
| **Status** | `PARKED` — decisão Mauro 2026-04-05 |
| **Motivo** | Clientes funcionam no n8n. Migração exige mapear lógica dos workflows n8n e comparar com Runtime. Há prioridades maiores. |
| **Pré-requisito** | Mapear gaps workflow n8n vs handler Runtime antes de qualquer migração |

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
| **Status** | `FUNCIONAL` |
| **Responsável** | @devops |
| **Implementação** | Renomeado `/opt/sparkle-runtime/` → `/opt/sparkle-aiox/`. Systemd services, deploy scripts (GitHub Actions), shebangs .venv corrigidos. 3 diretórios STALE removidos. Health check OK. |

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

## Sprint SUBSTÂNCIA — Engrossar o que existe (auditoria brownfield)

### [SUB-1] Brain Curadoria Acelerada (Gap 1)

| Campo | Valor |
|-------|-------|
| **Status** | `FUNCIONAL` |
| **Responsável** | @architect → @dev → @qa → @devops |
| **Impacto** | Curadoria 150 chunks/dia (antes 20). Backlog 487 limpo em ~3 dias. Semaphore(5) paralelo. Embedding obrigatório antes de aprovação. |
| **Arquivos** | `brain_curate.py`, `scheduler.py` |

---

### [SUB-2] Content Engine Resilience (Gap 2)

| Campo | Valor |
|-------|-------|
| **Status** | `FUNCIONAL` |
| **Responsável** | @architect → @dev → @qa → @devops |
| **Impacto** | Fallback Haiku quando billing Sonnet falha. quality_tier degraded para rastreabilidade. Setting ANTHROPIC_BILLING_FALLBACK controlável. |
| **Arquivos** | `llm.py`, `config.py`, `generate_content.py` |

---

### [SUB-3] Onboarding Pipeline Fix (Gap 3)

| Campo | Valor |
|-------|-------|
| **Status** | `FUNCIONAL` |
| **Responsável** | @architect → @dev → @qa → @devops |
| **Impacto** | Fix cascade on_failure (current_step não avança em falha bloqueante). Validação inputs obrigatórios (client_id, site_url, business_name). 2 camadas de proteção (endpoint + engine). |
| **Arquivos** | `workflow_step.py`, `friday/router.py`, `workflow/router.py`, `templates.py` |

---

### [SUB-4] Friday Triggers de Negócio (Gap 4)

| Campo | Valor |
|-------|-------|
| **Status** | `FUNCIONAL` |
| **Responsável** | @architect → @dev → @qa (reprovou 3 P1s) → @dev fix → @qa re-aprovação → @devops |
| **Impacto** | 3 novos triggers (billing_blocked, content_failure_streak, client_vencimento) + morning_checkin enriquecido com draft count. Anti-spam mantido. |
| **Arquivos** | `friday/proactive.py` |

---

### [SUB-5] Relatório Mensal Honesto

| Campo | Valor |
|-------|-------|
| **Status** | `FUNCIONAL` |
| **Responsável** | @architect → @dev → @qa → @devops |
| **Impacto** | 3 templates texto (Zenya com dados, Zenya sem dados, tráfego-only). Métricas honestas sem inventar números. Dry-run via `?send=false`. Fix bug `sent` em bulk. |
| **Arquivos** | `client_report.py`, `reports/router.py` |

---

### [SUB-6] Onboarding E2E Fix

| Campo | Valor |
|-------|-------|
| **Status** | `FUNCIONAL` |
| **Responsável** | @architect → @dev → @qa → @devops |
| **Impacto** | Fix brain_owner bug (pipeline usava "brain_pipeline" em vez de client_id real). Fix template resolution (client_id injetado no context antes de salvar). |
| **Arquivos** | `brain_ingest_pipeline.py`, `workflow/router.py` |

---

### [SUB-7] Sentry Error Tracking

| Campo | Valor |
|-------|-------|
| **Status** | `FUNCIONAL` |
| **Responsável** | @architect → @dev → @qa → @devops |
| **Impacto** | sentry-sdk[fastapi] instalado. Init antes do FastAPI. send_default_pii=False. No-op quando DSN vazio (Mauro precisa criar conta Sentry e adicionar DSN). |
| **Arquivos** | `main.py`, `config.py`, `requirements.txt` |
| **Pendente** | Mauro criar conta Sentry e fornecer SENTRY_DSN |

---

### [SUB-8] Cron Logging Estruturado

| Campo | Valor |
|-------|-------|
| **Status** | `FUNCIONAL` |
| **Responsável** | @architect → @dev → @qa → @devops |
| **Impacto** | Decorator log_cron() em todos os 17 crons. Tabela cron_executions com 3 indexes. Endpoint GET /system/crons. brain_curate split em 3 horários (02h, 10h, 18h). Logging nunca bloqueia execução. |
| **Arquivos** | `cron_logger.py` (novo), `scheduler.py`, `system_router.py` |
| **Migration** | `013_cron_executions.sql` aplicada |

---

### [SUB-9] .env Permissions Hardening

| Campo | Valor |
|-------|-------|
| **Status** | `FUNCIONAL` |
| **Responsável** | @devops |
| **Impacto** | chmod 600 em todos os .env na VPS. Deploy script hardened com step 2.5/5 automático. |
| **Arquivos** | `.github/workflows/deploy-runtime.yml` |

---

## Sprint CAMADA 2 — Brain como Memória do Sistema

### [C2-B1] Brain Namespaces + Auto-Ingestão Friday

| Campo | Valor |
|-------|-------|
| **Status** | `FUNCIONAL` |
| **Responsável** | @architect → @dev → @qa → @devops |
| **Impacto** | 3 namespaces: mauro-personal (82 chunks), sparkle-lore (50 chunks), sparkle-ops (55 chunks). Friday auto-ingere áudios do Mauro com metadata. Seed idempotente. Noise filter. |
| **Arquivos** | `brain/isolation.py`, `brain/seed.py` (novo), `friday/dispatcher.py`, `brain_ingest.py` |

---

### [C2-B2] Pipeline Enforcement no Runtime

| Campo | Valor |
|-------|-------|
| **Status** | `FUNCIONAL` |
| **Responsável** | @architect → @dev → @qa → @devops |
| **Impacto** | Template aios_pipeline 5 steps. Gate enforcement HTTP 422. Friday notifica violações. Worker bloqueia tasks sem pipeline_target_step. 35 testes. |
| **Arquivos** | `workflows/pipeline_enforcement.py` (novo), `pipeline/router.py` (novo), `workflows/templates.py`, `tasks/worker.py`, `main.py` |

---

### [C2-B3] Consulta Prioritária por Namespace

| Campo | Valor |
|-------|-------|
| **Status** | `FUNCIONAL` |
| **Responsável** | @architect → @dev → @qa → @devops |
| **Impacto** | Friday consulta mauro-personal antes de responder. Agentes recebem sparkle-ops no bootstrap. Zenya recebe sparkle-lore no prompt. Budget 2000 tokens. Graceful degradation. |
| **Arquivos** | `brain/namespace_context.py` (novo), `tasks/handlers/chat.py`, `tasks/handlers/activate_agent.py`, `tasks/handlers/send_character_message.py` |

---

## Sprint PIPELINE COMERCIAL — Funil de Vendas Zenya

> PRD aprovado 2026-04-05. Caminho C: Zenya no n8n WF01, dados no Supabase `leads`.

### [PC-1.1] Zenya Vendedora — Instância + Soul Prompt

| Campo | Valor |
|-------|-------|
| **Status** | `FUNCIONAL` — smoke test 10/10 PASS @qa 2026-04-05 |
| **Implementado** | WF01 ativo com soul prompt Zenya Vendedora. Z-API +5512982201239 exclusivo. 10 cenários aprovados: identidade IA, nichos âncora + fora âncora, BANT fluindo, preço padrão, handoff, sem overpromise, Calendly, não-ICP elegante. |
| **Story** | `docs/stories/sprint-pipeline/pc-1.1-zenya-vendedora.md` |
| **Bug não-bloqueante** | "Output inválido" na extração BANT pós-resposta — issue para @dev |

---

### EPIC-ONBOARDING — FUNCIONAL ✅ (2026-04-06)

| Story | Status | Entregável |
|-------|--------|-----------|
| ONB-S0.1/S0.2 | `FUNCIONAL` | Spike clone n8n + pipeline E2E |
| ONB-1.1 | `FUNCIONAL` | Modelo de dados (migration 014) |
| ONB-1.2 | `FUNCIONAL` | Contrato Autentique — generate + sign + webhook |
| ONB-1.4 | `FUNCIONAL` | Intake / Brain DNA / onboard_client orquestrador 8 fases |
| ONB-1.5a | `FUNCIONAL` | Clone n8n por tier, Chatwoot inbox, Z-API gate manual, qr-confirmed |
| ONB-1.5b | `FUNCIONAL` | Google Drive + Calendar via webhooks n8n, Loja Integrada + Nuvemshop |
| ONB-1.6 | `FUNCIONAL` | Teste interno QA — 10 perguntas, threshold 80% |
| ONB-1.7 | `FUNCIONAL` | Teste com cliente |
| ONB-1.8 | `FUNCIONAL` | Go-live execution |
| ONB-1.9 | `FUNCIONAL` | Pós go-live health monitoring |

**IDs críticos:**
- Workflows Essencial n8n: `7UnYBYZzzPSpEdl3` (Config), `IY9g1qHAv1FV8I5D` (Secretária), `cdqNUH8xoJCT` (Escalar), `X2QGanrmQ94sjmWk` (Quebrar)
- Drive webhook: `7w4uDx1h3Vf0feUP` | Calendar webhook: `AVbmzj48oOeMeKDi`
- Commit final: `dd98c1d` | Pipeline completo: @dev→@qa→@po→@devops

---

### Sprint PIPELINE COMERCIAL — FUNCIONAL ✅

| Story | Status | Entregável |
|-------|--------|-----------|
| PC-1.1 | `FUNCIONAL` | Zenya Vendedora — WF01 + soul prompt + Z-API +1239. 10/10 QA PASS |
| PC-1.2 | `FUNCIONAL` | BANT extração → Supabase `leads`. Branch paralelo, normalização defensiva |
| PC-1.3 | `FUNCIONAL` | Showcase dinâmico via soul prompt |
| PC-1.4 | `FUNCIONAL` | Notificação Friday score Alto. WF05 template BANT. Dedup via `notes` |
| PC-1.5 | `FUNCIONAL` | Playbook Canal B + B2. Aprovado Mauro. WA Business: Mauro configura quando puder |
| PC-1.5b | `FUNCIONAL` | Template proposta D0 R$497. Aprovado Mauro |
| PC-1.6 | `FUNCIONAL` | Follow-up D0→D+7. WF `ui80HRvfgrYLQXbR`. Webhooks trigger + stop |
| PC-1.7 | `FUNCIONAL` | View `pipeline_view`. GET /cockpit/pipeline. Friday responde consultas. Trigger fechamento |

**Ressalvas abertas (não bloqueantes):**
- PC-1.2: latência e2e medir com mensagem real quando houver número disponível
- PC-1.6: validar escrita `notes` com lead real com `demo_completed_at` preenchido
- WF01: verificar que `channel` enviado é `"zenya"` e não `"A"` (correção minor @dev)
- FR7: Calendly link ativo, integração real com calendário → sprint futura
- FR3: routing explícito Médio/Baixo → sprint futura

---

## Sprint CONTENT WAVE 2

### [CONTENT-2.4] Bucket Storage Público

| Campo | Valor |
|-------|-------|
| **Status** | `FUNCIONAL` — QA PASS 2026-04-07 |
| **Impacto** | Bucket `content-assets` público confirmado via MCP Supabase. URLs permanentes (`get_public_url`) em `image_generator.py` e `video_generator.py`. `BOUNDARY.md` documentado com nota obrigatória sobre requisito Instagram Graph API. |
| **Story** | `docs/stories/sprint-content/content-2-4-bucket-storage-publico.md` |
| **Unblocks** | CONTENT-2.1, CONTENT-2.5 |

---

### [CONTENT-2.2] Resiliência Cron — Stuck Pieces

| Campo | Valor |
|-------|-------|
| **Status** | `FUNCIONAL` — QA PASS com CONCERNS 2026-04-07 |
| **Impacto** | Migration `015_content_pieces_resilience.sql` aplicada (`retry_count`, `failed_permanent`, `error_reason` + índice). Job `content_stuck_check` (30 min) com optimistic lock. Timeout configurável via `PIPELINE_TIMEOUT_MINUTES` (default 20). Notificação Friday no fail-permanent. |
| **Story** | `docs/stories/sprint-content/content-2-2-cron-resilience.md` |
| **Concern** | Assimetria optimistic lock: retry path tem lock (`.eq("status")`), fail-permanent path não. Risco baixo, não bloqueante. Sugestão: adicionar `.eq("status", current_status)` ao UPDATE de falha permanente em iteração futura. |
| **Unblocks** | CONTENT-2.5 |

---

### [CONTENT-2.1] Publisher fix + Token Manager

| Campo | Valor |
|-------|-------|
| **Status** | `AGUARDANDO_MAURO` — credenciais Instagram |
| **Bloqueante** | `INSTAGRAM_ACCESS_TOKEN` + `INSTAGRAM_USER_ID` não configurados na VPS |

---

### [CONTENT-2.3] URL Absoluta Friday

| Campo | Valor |
|-------|-------|
| **Status** | `FUNCIONAL — QA PASS 2026-04-07` |
| **Responsável** | @qa |

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

### Sprint PIPELINE COMERCIAL v1 (2026-04-05)

| Item | O que faz | QA | Data |
|------|-----------|-----|------|
| PC-1.1 Zenya Vendedora | WF01 + soul prompt + Z-API +5512982201239. Qualifica leads ao vivo | 10/10 PASS | 2026-04-05 |
| PC-1.2 BANT → Supabase | Extração BANT via gpt-4o-mini + upsert `leads` (branch paralelo, sem atraso) | APROVADO | 2026-04-05 |
| PC-1.3 Showcase Dinâmico | Soul prompt com exemplos âncora + convite teste ao vivo + Calendly | APROVADO | 2026-04-05 |
| PC-1.4 Notificação Friday | WF05 template BANT. Trigger score=alto com deduplicação via `notes` | APROVADO | 2026-04-05 |
| PC-1.5 Script Mauro | Playbook Canal B + B2. 8 respostas rápidas. Aprovado Mauro | APROVADO | 2026-04-05 |
| PC-1.5b Template Proposta | D0 R$497 no playbook. Placeholders para personalização automática | APROVADO | 2026-04-05 |
| PC-1.6 Follow-up D0→D+7 | WF `ui80HRvfgrYLQXbR`. 4 ângulos via OpenAI. Stop por resposta | APROVADO | 2026-04-05 |
| PC-1.7 CRM + Friday | `pipeline_view` + GET /cockpit/pipeline + handler 5 queries + trigger fechamento | APROVADO | 2026-04-05 |

**Devops:** Runtime ativo (10e486c), n8n WF01 + WF PC-1.6 ativos, todos os health checks OK.
**Pendente sem bloqueio:** latência e2e real (aguarda número Z-API), WA Business etiquetas (Mauro), FR7 Calendly integrado + FR3 routing Médio/Baixo → sprint futura.

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
