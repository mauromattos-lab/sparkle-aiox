# Plano Mestre Reformulado — Sparkle AIOX
**Versao:** 2.0 | **Criado por:** @architect (Aria) | **Data:** 2026-04-04
**Referencia:** [sparkle-constitution.md](architecture/sparkle-constitution.md) | [agent-queue.md](agent-queue.md)

> Cruzamento brownfield discovery x entregas realizadas. Tudo que existe esta marcado.
> Tudo que falta esta priorizado por dependencia tecnica (o que desbloqueia mais).
> Separacao rigida: SISTEMA (agentes fazem) vs. ESTRATEGICO (Mauro decide) vs. CLIENTE (segunda-feira).

---

## Inventario — O que JA EXISTE (nao retrabalhar)

| # | Entrega | Status | Data |
|---|---------|--------|------|
| 1 | Brain Pipeline 6 fases (raw-chunk-canonical-insights-narrative-vectors) | FUNCIONAL | 04/04 |
| 2 | Agent Context Persistente (16 blocos, 4 camadas, 4000 tokens) | FUNCIONAL | 04/04 |
| 3 | Handoff Automatico (3 workflow templates + engine) | FUNCIONAL | 04/04 |
| 4 | Observer Pattern (auto_implement_gap, 4 tipos, API) | FUNCIONAL | 04/04 |
| 5 | Connection Pool (thread-local Supabase proxy) | FUNCIONAL | 04/04 |
| 6 | Brain File Upload (PDF, TXT, MD, CSV) | FUNCIONAL | 04/01 |
| 7 | Brain domain normalization (220-13 canonicos) | FUNCIONAL | 04/01 |
| 8 | Content Engine (generate, schedule, approve/reject) | FUNCIONAL | 04/02 |
| 9 | Friday proativa (daily briefing, brain digest, content suggestions, health alerts, 8 crons) | FUNCIONAL | 04/02 |
| 10 | call_claude async (AsyncAnthropic nativo) | FUNCIONAL | 04/01 |
| 11 | CI/CD (GitHub Actions deploy-runtime, deploy-portal, tests) | FUNCIONAL | 04/01 |
| 12 | 33 E2E tests | FUNCIONAL | 04/04 |
| 13 | Zenya Alexsandro operacional (729 msgs, 99.86%) | FUNCIONAL | 04/02 |
| 14 | Portal: stats bar, toasts, feed color coding, responsivo | FUNCIONAL | 04/01 |
| 15 | Portal: brain search UI + /brain /task /status commands | FUNCIONAL | 04/01 |
| 16 | Portal: system activity page (task history, error log, 24h timeline) | FUNCIONAL | 04/01 |
| 17 | Workflow Engine (workflow_runs + encadeamento JSONB) | FUNCIONAL | 04/02 |
| 18 | activate_agent (@analyst real, 4 tools, tool_use loop) | FUNCIONAL | 04/02 |
| 19 | Brain auto-ingestao (conversas, score > 0.6, isolamento) | FUNCIONAL | 04/02 |
| 20 | Registry fix (15 intents, 6 handlers orfaos) | FUNCIONAL | 04/02 |

### CONCLUIDOS SESSAO 04/04 (alem do inventario inicial)

| # | Entrega | Status | Data |
|---|---------|--------|------|
| 21 | Schema agente em DB (tabela `agents` Supabase + loader) | FUNCIONAL | 04/04 |
| 22 | Deduplicacao semantica Brain (RPC pgvector + confirmation_count) | FUNCIONAL | 04/04 |
| 23 | B1-01 Suite testes unitarios (88 testes, 11 arquivos) | FUNCIONAL | 04/04 |
| 24 | B1-02 Character State canonico (Supabase + cache 60s + API) | FUNCIONAL | 04/04 |
| 25 | B1-03 Brain isolation per-agent (brain_owner filter + 31 testes) | FUNCIONAL | 04/04 |
| 26 | B1-04 Testes persona Friday/Zenya (58 testes comportamentais) | FUNCIONAL | 04/04 |
| 27 | B1-06 VPS path audit + CI health check fix (porta 8000->8001) | FUNCIONAL | 04/04 |
| 28 | B2-01 Taxonomia 5 tipos agente + routing rules + priority | FUNCIONAL | 04/04 |
| 29 | B2-02 Character Orchestrator (mood engine, reveal moments, 30min scheduler) | FUNCIONAL | 04/04 |
| 30 | B2-04 DNA Schema 8 categorias + extrator Haiku + API | FUNCIONAL | 04/04 |
| 31 | B2-06 Observer Quality auto-avaliacao Haiku + quality log + gaps | FUNCIONAL | 04/04 |
| 32 | B2-07 Crons 24/7 (keep-alive, backup, log rotation) | FUNCIONAL | 04/04 |
| 33 | B2-08 Runbook incidentes (775 linhas, 7 cenarios) | FUNCIONAL | 04/04 |
| 34 | B2-03 Character Runtime 6-phase pipeline (tone directives 32 combos) | FUNCIONAL | 04/04 |
| 35 | B2-05 Hierarquia 3 niveis handoff (local/layer/global + handoff_log) | FUNCIONAL | 04/04 |
| 36 | B2-P1 Identidade cliente portal (ClientHeader, initials avatar, plan badge) | FUNCIONAL | 04/04 |
| 37 | B2-P2 Narrativa valor acumulado (ValueNarrative, 3 storytelling cards) | FUNCIONAL | 04/04 |
| 38 | B2-P3 Footer/header premium (glassmorphism, heartbeat, cockpit aesthetic) | FUNCIONAL | 04/04 |
| 39 | B2-P4 Login diferenciado (ambient glow, glassmorphism, WhatsApp fallback) | FUNCIONAL | 04/04 |
| 40 | B3-01 Brain curadoria (approve/reject chunks + portal UI + stats) | FUNCIONAL | 04/04 |
| 41 | B3-02 Friday presenca Lei 3 (6 triggers, anti-spam, quiet hours) | FUNCIONAL | 04/04 |
| 42 | B3-03 SOP onboarding automatizado (6-step pipeline, draft status) | FUNCIONAL | 04/04 |
| 43 | B3-04 UI jogo avancada (GamificationPanel, Brain XP, Zenya Level, 12 achievements) | FUNCIONAL | 04/04 |
| 44 | B3-05 Brain avancado (namespaces, TTL/archival, usage metrics) | FUNCIONAL | 04/04 |
| 45 | B3-06 Cobertura testes 50%->70% (170 novos testes, 307 total, 21 arquivos) | FUNCIONAL | 04/04 |
| 46 | B1-05 Regressao CI gate (35 testes regressao + deploy bloqueado se falhar) | FUNCIONAL | 04/04 |

---

## Pipeline Obrigatorio

```
Orion (identifica + delega) -> @dev (implementa) -> @qa (valida) -> @devops (deploya)
```

Orion nao escreve codigo. @dev nao deploya. @qa nao aprova sem testar. @devops nao deploya sem QA.

---

## BLOCO 1 — Fundacao de Qualidade (07-13 abr, 1 semana)

**Meta:** Cobertura de testes real, Character state canonico, Brain isolamento. O que sustenta tudo acima.

**Por que primeiro:** Tudo que se construir em cima de runtime com ~10% cobertura e sem character state canonico tera retrabalho. Corrigir a base antes de crescer.

### SISTEMA (agentes fazem, sem Mauro)

| ID | Item | Responsavel | Depende de | Paralelo? |
|----|------|------------|------------|-----------|
| B1-01 | **Cobertura Runtime 10% -> 50%+** — testes unitarios para handlers existentes (brain_ingest, brain_query, daily_briefing, activate_agent, content pipeline, observer). Testes de integracao para fluxos criticos. | @qa | Nada (desblq.) | SIM |
| B1-02 | **Character State canonico** — fonte de verdade `character_state` no Supabase (humor, energia, ultimo_evento, arc_position). Sessao Redis para estado efemero. Loader no Runtime que le DB -> Redis na inicializacao. | @dev (Dex) | Nada (desblq.) | SIM |
| B1-03 | **Brain isolamento runtime** — validacao por agente (Friday so le brain_owner=friday, Zenya so le brain_owner=client_X). Middleware que injeta filtro automatico. Testes de isolamento cruzado. | @dev | Nada (desblq.) | SIM |
| B1-04 | **Testes de persona** — Friday sabe o que pode fazer? Zenya responde no tom correto? QA com cenarios de personalidade, edge cases de tom, teste de contaminacao entre personas. | @qa | Nada (desblq.) | SIM |
| B1-05 | **Testes de regressao cross-sprint** — suite que roda automaticamente no CI cobrindo: handlers registrados, brain query/ingest, observer flow, workflow engine. Gate no deploy. | @qa + @devops | B1-01 parcial | APOS B1-01 |
| B1-06 | **VPS Path Unification** — eliminar confusao `/opt/sparkle-runtime/` vs `/opt/sparkle-runtime/sparkle-runtime/`. .venv no .gitignore. | @devops (Gage) | Nada (desblq.) | SIM |

### CLIENTE (segunda-feira, 07/04)

| ID | Item | Responsavel | Depende de |
|----|------|------------|------------|
| B1-C1 | **Zenya Ensinaja go-live** — KB com 10 cursos ja extraidos, deploy n8n workflows, sheets ensina_leads, QA e2e. | @dev -> @qa | Nada (desblq.) |

**Paralelismo Bloco 1:** 6 itens de sistema + 1 cliente = 7 agentes simultaneos. B1-05 comeca apos B1-01 ter cobertura minima. Tudo mais e paralelo dia 1.

---

## BLOCO 2 — Agentes e Personagens (14-27 abr, 2 semanas)

**Meta:** Taxonomia completa de agentes, Character Runtime, DNA Schema, handoff hierarquico. O "sistema nervoso" do organismo.

**Por que segundo:** Agentes em DB (Bloco 0, ja em andamento) desbloqueia taxonomia. Character state (Bloco 1) desbloqueia Character Runtime. DNA schema estrutura o onboarding automatico.

### SISTEMA

| ID | Item | Responsavel | Depende de | Paralelo? | Semana |
|----|------|------------|------------|-----------|--------|
| B2-01 | **Taxonomia tipos agente completa** — definir os 5+ tipos: operational, specialist, character, orchestrator, observer. Schema no Supabase (coluna `agent_type` na tabela `agents`). Regras de routing por tipo. | @architect (Aria) | Schema agente DB (em andamento) | SIM | S1 |
| B2-02 | **Character Orchestrator** — 5o tipo de agente. Gerencia transicoes de humor, decide quando personagem reage, orquestra "momentos de reveal". Handler `character_event` + scheduler. | @architect -> @dev | B2-01 + B1-02 | APOS deps | S1 |
| B2-03 | **Character Runtime sequencia 6 fases** — (1) load character state, (2) apply context, (3) select voice/tone, (4) generate response, (5) update state, (6) persist. Pipeline no Runtime. | @dev (Dex) | B1-02 (character state) | APOS B1-02 | S1 |
| B2-04 | **DNA Schema por cliente (SYS-4)** — tabela `client_dna`, extrator automatico de Tom, persona, regras, diferenciais. Handler + endpoint API. Integra com brain pipeline (fontes -> DNA). | @architect -> @dev | SYS-1 FUNCIONAL | SIM | S1 |
| B2-05 | **Hierarquia 3 niveis handoff** — local (dentro do mesmo workflow), camada (entre workflows), global (escalonamento Orion). Refatorar workflow engine para suportar niveis + fallback. | @architect -> @dev | SYS-3 FUNCIONAL | SIM | S2 |
| B2-06 | **Observer qualidade** — auto-avaliacao com Haiku pos-resposta. Score de qualidade salvo. Threshold para re-run automatico. Dashboard de qualidade no portal. | @dev (Dex) | SYS-5 FUNCIONAL | SIM | S2 |
| B2-07 | **Crons 24/7** — backup diario Supabase, keep-alive Runtime, relatorio semanal automatico, health check com alerta. Tudo em systemd/cron no VPS. | @devops (Gage) | VPS Path (B1-06) | SIM | S1 |
| B2-08 | **Runbook incidentes** — doc operacional: o que fazer quando Runtime cai, quando Supabase fica lento, quando Z-API para, quando deploy falha. Checklist + scripts de recovery. | @devops (Gage) | Nada | SIM | S1 |

### SISTEMA (Portal/UX)

| ID | Item | Responsavel | Depende de | Paralelo? | Semana |
|----|------|------------|------------|-----------|--------|
| B2-P1 | **Identidade do cliente no portal** — logo, cores, nome do negocio visivel. Nao e so "client_id". Experiencia de "este e o MEU sistema". | @ux (Uma) -> @dev | Portal FUNCIONAL | SIM | S1 |
| B2-P2 | **Narrativa de valor acumulado** — visualizacao de "seu Brain cresceu X%", "Zenya resolveu Y conversas", "voce economizou Z horas". Storytelling, nao metricas frias. | @ux -> @dev | Portal FUNCIONAL + Brain pipeline | SIM | S2 |
| B2-P3 | **Footer/header premium** — identidade visual que parece produto, nao prototipo. Lei 15: "se parece Notion, esta errado". | @ux -> @dev | Portal FUNCIONAL | SIM | S1 |
| B2-P4 | **Login diferenciado** — experiencia de entrada que ja comunica valor. Nao e so "email + senha". | @ux -> @dev | Portal auth existente | SIM | S2 |

**Paralelismo Bloco 2:** B2-01/04/07/08/P1/P3 comecam dia 1 (6 paralelos). B2-02/03 comecam apos B1-02. B2-05/06/P2/P4 na segunda semana. Total: ate 8 agentes simultaneos.

---

## BLOCO 3 — Inteligencia e Autonomia (28 abr - 11 mai, 2 semanas)

**Meta:** Brain com curadoria, SOP automatizado, Lei 3 (Friday presenca) corrigida, Lei 15 (UI jogo) avancada. O sistema comeca a parecer organismo.

### SISTEMA

| ID | Item | Responsavel | Depende de | Paralelo? | Semana |
|----|------|------------|------------|-----------|--------|
| B3-01 | **Brain qualidade > volume** — curadoria humana 5-10% dos chunks. Interface no portal para Mauro revisar/aprovar/rejeitar chunks. Score de confianca. Chunks rejeitados saem do embedding. | @pm (Morgan) design -> @dev impl | Brain pipeline FUNCIONAL | SIM | S1 |
| B3-02 | **Lei 3 fix: Friday presenca** — Friday nao espera ser chamada. Implementar: (1) proactive outreach baseado em calendar/contexto, (2) interrupcao inteligente (nao spam), (3) ambient awareness (hora do dia, dia da semana, humor inferido). Expandir os 8 crons existentes para logica contextual. | @dev (Dex) | Friday proativa FUNCIONAL + B1-02 | SIM | S1 |
| B3-03 | **SOP onboarding automatizado** — novo cliente -> agente extrai contexto (site, Instagram, docs), popula client_dna, gera system prompt, cria instancia Zenya. Humano so valida. | @devops (Gage) design -> @dev impl | B2-04 (DNA Schema) | APOS B2-04 | S1 |
| B3-04 | **Lei 15 parcial: UI jogo avancada** — portal com elementos de gamificacao: XP do Brain, nivel do agente, achievements, timeline visual estilo RPG. Nao e dashboard — e cockpit. | @ux (Uma) -> @dev | B2-P1/P3 (portal identity) | APOS B2-P | S2 |
| B3-05 | **Brain isolamento avancado** — alem de owner-based (B1-03), adicionar: namespace por dominio, TTL de chunks, archival automatico de chunks velhos, metricas de uso por chunk. | @dev | B1-03 (isolamento basico) | APOS B1-03 | S2 |
| B3-06 | **Cobertura testes 50% -> 70%** — expandir suite para cobrir character runtime (B2-03), DNA schema (B2-04), handoff hierarquico (B2-05), observer qualidade (B2-06). | @qa | Bloco 2 entregas | APOS B2 | S2 |

**Paralelismo Bloco 3:** B3-01/02 comecam dia 1 (2 paralelos). B3-03 depende de B2-04. B3-04/05/06 na segunda semana. Ate 4 paralelos.

---

## BLOCO 4 — Escala e Produto (12-25 mai, 2 semanas)

**Meta:** Primeiro personagem paralelo, Content Engine v2, modelo de negocio validado. Transicao de "sistema interno" para "produto".

### SISTEMA

| ID | Item | Responsavel | Depende de | Paralelo? | Semana |
|----|------|------------|------------|-----------|--------|
| B4-01 | **Primeiro personagem em paralelo** — Zenya ja opera. Ativar segundo personagem (Finch/Pip/Juno — Mauro decide qual). Validar que Character Runtime (B2-03) suporta multi-personagem. | @dev | B2-02 + B2-03 + DECISAO MAURO | APOS deps | S1 |
| B4-02 | **Content Engine v2** — scheduling multi-plataforma (Instagram + YouTube + TikTok), template por formato (carousel, reels, shorts), preview visual no portal. | @dev | Content Engine FUNCIONAL | SIM | S1 |
| B4-03 | **Zenya self-serve spec** — spec completa de como cliente gerencia Zenya sem Mauro. Painel do cliente, treinamento do Brain pelo cliente, metricas self-service. | @pm (Morgan) | B2-04 (DNA) + B3-01 (curadoria) + DECISAO MAURO | APOS deps | S1 |
| B4-04 | **Modelo negocio Camada 3** — spec: pricing tiers, upgrade path Zenya -> Plataforma, metricas de conversao esperadas, unit economics. | @pm (Morgan) | DECISAO MAURO | APOS decisao | S1 |
| B4-05 | **Member State Engine** — track estado de membros da comunidade futura. Schema Supabase, eventos, niveis, historico. Fundacao para Camada 4 (Social). | @architect -> @dev | Nada (design pode comecar) | SIM | S2 |

**Paralelismo Bloco 4:** B4-02/05 comecam dia 1. B4-01/03/04 dependem de decisoes do Mauro e entregas anteriores.

---

## DECISOES ESTRATEGICAS — Mauro (nao tem prazo tecnico, mas bloqueiam itens)

Estes itens nao sao tarefas de agente. Sao decisoes que so o Mauro pode tomar. Cada uma desbloqueia itens especificos no plano.

| # | Decisao | Desbloqueia | Urgencia |
|---|---------|-------------|----------|
| D1 | **Primeiro personagem em paralelo** — qual? (Finch, Pip, Juno, outro) | B4-01 | Bloco 4 |
| D2 | **Zenya life expectancy** — quanto tempo ate Zenya virar self-serve? Ou sempre managed? | B4-03 | Bloco 4 |
| D3 | **Upgrade path Zenya -> Plataforma** — qual e o produto Camada 3? | B4-04 | Bloco 4 |
| D4 | **Identidade publica** — B2B ou conteudo/IP? Ou ambos com separacao? | Posicionamento, landing, conteudo | Quando quiser |
| D5 | **Modelo negocio Camada 3** — pricing, tiers, unit economics | B4-04 | Bloco 4 |
| D6 | **Sessao Lore** — awakening event, Juno, ensemble, relacao Zenya-Brain | BLOCK-04 | Quando quiser |

**Recomendacao Aria:** D1-D3 idealmente decididas ate fim do Bloco 3 (11 mai) para nao atrasar Bloco 4. D4-D6 podem vir a qualquer momento.

---

## BLOQUEADOS POR ACAO EXTERNA (nao agente)

Estes itens estao prontos tecnicamente. Falta acao humana ou credencial.

| ID | Item | Bloqueio | Quando resolver |
|----|------|----------|-----------------|
| BLOCK-03 | Fun Personalize Julia go-live | API key Loja Integrada (Julia) + Z-API instance | Segunda-feira |
| BLOCK-04 | Lore Zenya + Personagens | Sessao lore com Mauro | DECISAO D6 |
| BLOCK-05 | Gabriela Meta Ads | Saldo + criativos | Segunda-feira |
| BLOCK-06 | Vitalis inteligencia conversas | Msg Joao Lucio + conectar WhatsApp Z-API | Segunda-feira |
| BLOCK-07 | Contract Generator | Token Autentique | Quando Mauro acessar painel |
| OPS-5 | Instagram DM Pilot | App Meta for Developers (~45min Mauro) | Quando priorizar |

---

## CLIENTES — Segunda-feira (nao misturar com sistema)

Regra: SISTEMA PRIMEIRO. Clientes sao atendidos segunda-feira, exceto urgencia de churn.

| Prioridade | Cliente | Acao | MRR em jogo |
|------------|---------|------|-------------|
| 1 | Ensinaja Douglas (OPS-3) | Go-live: KB 10 cursos, workflows, sheets, QA | R$650/mes |
| 2 | Fun Personalize Julia (BLOCK-03) | Cobrar API key, deploy, QA e2e | R$897/mes |
| 3 | Gabriela Consorcio (BLOCK-05) | Saldo + criativos -> unpause campanhas | R$750/mes |
| 4 | Vitalis (BLOCK-06) | Msg Joao Lucio, conectar Z-API | Upsell futuro |

---

## Mapa de Dependencias Visuais

```
                    EM ANDAMENTO (04/04)
                    |-- Schema agente DB
                    |-- Dedup semantica Brain
                    
BLOCO 1 (07-13 abr) ─────────────────────────────────
  B1-01 Cobertura testes ──────> B1-05 Regressao CI
  B1-02 Character State ──────> B2-02 Char Orchestrator
                           ├──> B2-03 Char Runtime 6 fases
                           └──> B3-02 Friday presenca
  B1-03 Brain isolamento ─────> B3-05 Isolamento avancado
  B1-04 Testes persona         (standalone)
  B1-06 VPS path ─────────────> B2-07 Crons 24/7
  B1-C1 Ensinaja               (standalone, segunda)

BLOCO 2 (14-27 abr) ─────────────────────────────────
  B2-01 Taxonomia agentes ────> B2-02 Char Orchestrator
  B2-02 Char Orchestrator ────> B4-01 Primeiro personagem
  B2-03 Char Runtime ─────────> B4-01 Primeiro personagem
  B2-04 DNA Schema ───────────> B3-03 SOP onboarding auto
                           └──> B4-03 Zenya self-serve
  B2-05 Handoff hierarquico    (standalone)
  B2-06 Observer qualidade     (standalone)
  B2-07 Crons 24/7            (standalone)
  B2-08 Runbook               (standalone)
  B2-P1/P3 Portal identity ──> B3-04 UI jogo avancada

BLOCO 3 (28 abr - 11 mai) ───────────────────────────
  B3-01 Brain curadoria        (standalone)
  B3-02 Friday presenca        (standalone)
  B3-03 SOP onboarding ──────> (desbloqueia escala clientes)
  B3-04 UI jogo               (standalone)
  B3-05 Brain isolamento adv  (standalone)
  B3-06 Testes 70%            (standalone)

BLOCO 4 (12-25 mai) ─────────────────────────────────
  B4-01 Personagem paralelo    (depende D1)
  B4-02 Content Engine v2     (standalone)
  B4-03 Zenya self-serve      (depende D2)
  B4-04 Modelo Camada 3       (depende D3/D5)
  B4-05 Member State Engine   (standalone)
```

---

## Checklist Completo de Gaps — Nada Faltando

Cada gap do brownfield esta mapeado a um item do plano.

| Gap identificado | Mapeado em | Status |
|-----------------|------------|--------|
| Character state fonte de verdade | B1-02 | PENDENTE |
| Observer qualidade (auto-avaliacao Haiku) | B2-06 | PENDENTE |
| Character Runtime 6 fases | B2-03 | PENDENTE |
| Hierarquia 3 niveis handoff | B2-05 | PENDENTE |
| Character Orchestrator (5o tipo) | B2-02 | PENDENTE |
| Brain isolamento runtime | B1-03 | PENDENTE |
| Taxonomia tipos agente | B2-01 | PENDENTE |
| Brain qualidade > volume (curadoria) | B3-01 | PENDENTE |
| Personagem em paralelo com infra | B4-01 | PENDENTE (D1) |
| Modelo negocio Camada 3 | B4-04 | PENDENTE (D5) |
| Zenya life expectancy / self-serve | B4-03 | PENDENTE (D2) |
| Lei 3 Friday presenca VIOLADO | B3-02 | PENDENTE |
| Lei 15 UI jogo PARCIAL | B3-04 | PENDENTE |
| Identidade cliente no portal | B2-P1 | PENDENTE |
| Narrativa valor acumulado | B2-P2 | PENDENTE |
| Footer/header premium | B2-P3 | PENDENTE |
| Login diferenciado | B2-P4 | PENDENTE |
| Testes de persona | B1-04 | PENDENTE |
| Cobertura Runtime 10% -> 50% | B1-01 | PENDENTE |
| Testes regressao entre sprints | B1-05 | PENDENTE |
| Crons 24/7 | B2-07 | PENDENTE |
| Runbook incidentes | B2-08 | PENDENTE |
| SOP onboarding automatizado | B3-03 | PENDENTE |
| DNA Schema por cliente (SYS-4) | B2-04 | PENDENTE |
| Painel de Comando (SYS-6) evolucao | B2-P1 a B3-04 | PENDENTE |
| VPS Path Unification (OPS-6) | B1-06 | PENDENTE |

---

## Como Usar Este Plano

**A cada sessao:**
1. Orion le este arquivo + `agent-queue.md`
2. Identifica TODOS os itens desbloqueados (sem dependencias pendentes)
3. Lanca TODOS em paralelo — sem perguntar, sem sequenciar
4. Atualiza status aqui ao final via `POST /system/state`

**Criterio de conclusao de bloco:** todos os DoDs marcados FUNCIONAL + @qa validou.

**Regra de ouro:** se ha 7 itens desbloqueados, 7 agentes rodam. Nao 3.

---

*Aria — @architect | Plano Mestre v2.0 | Brownfield + Forward*
