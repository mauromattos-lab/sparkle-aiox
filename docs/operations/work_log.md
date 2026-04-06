# Log de Atividades — Sparkle AIOX

> **REGRA**: Leia este arquivo antes de iniciar qualquer trabalho. Se já consta como FEITO, vá direto para o próximo passo — não refaça.

> **REGRA ORION**: Antes de analisar ou implementar qualquer coisa para um cliente, consulte este log. Se já consta como FEITO, vá direto para o próximo passo — não refaça.

---

## SESSÃO 2026-04-05 — SPRINT PIPELINE COMERCIAL v1 — FECHADO

### [FUNCIONAL] Pipeline Comercial Sparkle v1
**Status:** FECHADO. @qa 10/10 PASS + 4 stories aprovadas. @po 8/8 stories Closed. @devops deploy confirmado.
**PRD:** `docs/prd/pipeline-comercial-prd.md` (aprovado Mauro 2026-04-05)
**Commit final:** `4d5357d`

**IDs críticos (não perder):**
- WF01 Zenya Vendedora: `IY9g1qHAv1FV8I5D` — n8n.sparkleai.tech
- WF05 Escalada Mauro: `cdqNUH8xoLy9gJCT`
- WF PC-1.6 Follow-up: `ui80HRvfgrYLQXbR`
- Z-API Zenya Vendedora: +5512982201239 (Sparkle Vendas, Chatwoot inbox 11)
- Soul prompt: `docs/zenya/zenya-vendedora-soul.md`
- Playbook Mauro: `docs/playbooks/pipeline-comercial-script-mauro.md`

**O que foi entregue:**
- PC-1.1: Zenya Vendedora ativa no WF01 com soul prompt de vendas
- PC-1.2: BANT extração automática → upsert Supabase `leads` (branch paralelo)
- PC-1.3: Showcase dinâmico via soul prompt (âncoras confeitaria/clínica/escola)
- PC-1.4: Notificação Friday quando score=alto. WF05 com template BANT completo
- PC-1.5: Playbook Canal B (lead frio) + Canal B2 (handoff Zenya). Aprovado Mauro
- PC-1.5b: Template proposta D0 R$497 no playbook. Aprovado Mauro
- PC-1.6: Follow-up D0→D+7 automático. 4 ângulos OpenAI. Webhook trigger + stop
- PC-1.7: View `pipeline_view` + GET /cockpit/pipeline + Friday responde consultas pipeline + trigger fechamento → onboarding

**Decisões técnicas:**
- Tabela `commercial_pipeline` não criada — `leads` já tinha todos os campos (migration anterior)
- `bant_score` é lowercase: alto/medio/baixo/indeterminado (constraint Supabase)
- `channel` para leads Zenya = `"whatsapp"` (não "A")
- Deduplicação notificação Mauro via campo `notes` (flag `mauro_notificado`)
- Follow-up controla sequência via `notes` (flags `|followup:d0|d2|d4|d7`)
- `/cockpit/pipeline` requer `X-API-Key` (RUNTIME_API_KEY no .env do sparkle-runtime)

**Pendente sem bloqueio:**
- Validação e2e de entrega de mensagem (aguarda número Z-API disponível — 15min quando tiver)
- WA Business: Mauro configura respostas rápidas + etiquetas quando puder
- FR7 Calendly integrado ao calendário + FR3 routing Médio/Baixo → sprint futura

---

## SESSÃO 2026-04-05 — EPIC-ONBOARDING COMPLETO (ACEITO PO)

### [FUNCIONAL] EPIC-ONBOARDING — Pipeline E2E Zenya Onboarding
**Status:** ACEITO pelo PO sem ressalvas. Deploy VPS ativo.
**Commit final:** `1e24fac` (CNPJ Sparkle no template)

**Stories entregues (todas DONE):**
- ONB-1 (S0.1, S0.2): Pipeline orquestrador 8 fases (contract→payment→intake→config→test_internal→test_client→go_live→post_go_live)
- ONB-2: Intake automático
- ONB-3: Configuração Zenya automática (soul_prompt + KB)
- ONB-5: QA smoke test (10 perguntas por vertical, 80% threshold)
- Story 1.2: Autentique contract integration (generate + sign + webhook)
- Story 1.7: Client test phase (approve, feedback, business days check)
- Story 1.8: Go-live execution (pre-checklist, atomic go-live, reminders)
- Story 1.9: Post-go-live health monitoring (2x/dia cron, sentiment Haiku, 30-day completion)

**3 Ressalvas PO resolvidas:**
- R1: Integração Autentique (contract_filler.py, generate_contract.py, mark_contract_signed.py, webhook handler)
- R2: POST /zenya/event endpoint (n8n→Runtime telemetria, zenya_events table)
- R3: Timeout alerts (check_condition_timeouts — 48h contrato, 72h pagamento, 5d intake)

**Arquivos novos criados:**
- `runtime/onboarding/service.py` (~1100+ linhas, orquestrador completo)
- `runtime/onboarding/router.py` (endpoints: status, advance, approve, feedback, go-live, generate-contract)
- `runtime/onboarding/health_analyzer.py` (3-layer: zenya_events→conversations→brain)
- `runtime/onboarding/report_generator.py` (weekly WhatsApp report)
- `runtime/onboarding/qa_checklists.py` (soul_prompt + KB validation)
- `runtime/onboarding/test_questions.py` (banco perguntas por vertical)
- `runtime/onboarding/contract_filler.py` (template filling + BRL format)
- `runtime/onboarding/templates/contract_template.md` (CNPJ: 44.263.836/0001-54)
- `runtime/tasks/handlers/smoke_test_zenya.py`
- `runtime/tasks/handlers/post_golive_health.py`
- `runtime/tasks/handlers/generate_contract.py`
- `runtime/tasks/handlers/mark_contract_signed.py`
- Tabela Supabase: `zenya_events` (5 índices)
- Crons: `post_golive_health_check_08h` + `post_golive_health_check_20h`
- Task registry: 52 handlers totais

**Gate system:** 5 gates com PHASE_CONDITIONS verificados por cron horário
**testing_mode:** enum 'off'→'internal_testing'→'client_testing'→'live'

**Stories 1.5a e 1.5b (2026-04-06) — ACCEPTED + DEPLOYED:**
- ONB-1.5a: Clone n8n por tier (4/4 Essencial), Chatwoot inbox, Z-API gate manual, qr-confirmed endpoint
  - IDs workflows Essencial: `7UnYBYZzzPSpEdl3` (Configurações), `IY9g1qHAv1FV8I5D` (Secretária), `cdqNUH8xoLy9gJCT` (Escalar), `X2QGanrmQ94sjmWk` (Quebrar msgs)
  - Template master atualizado manualmente por Mauro: campos `system_prompt` + `cliente_telefone` no Set node
- ONB-1.5b: Google Drive via webhook n8n `7w4uDx1h3Vf0feUP`, Calendar via webhook `AVbmzj48oOeMeKDi`
  - OAuth2 Sparkle no n8n — sem credenciais Google no Runtime
  - Loja Integrada + Nuvemshop validação via API
- Commit final: `dd98c1d`

**Credenciais configuradas no .env VPS (2026-04-06):**
- `AUTENTIQUE_TOKEN=6ee3d69a...` — token Autentique para assinatura digital
- `ASAAS_WEBHOOK_SECRET=whsec_rSzSO-...` — signing secret HMAC-SHA256 Asaas v3
- Webhook Asaas configurado por Mauro no painel → `runtime.sparkleai.tech/webhooks/asaas`

**Pipeline AIOS completo executado:** @dev → @qa (6/6 IVs 1.5a, 7/7 IVs 1.5b) → @po (Accepted) → @devops (push dd98c1d)

**Sem pendências abertas. EPIC-ONBOARDING 100% fechado.**

---

## SESSÃO 2026-04-02 (noite) — Sprint OPS/CORE/BRAIN

### [FUNCIONAL] OPS-1 — Registry Fix
23 handlers registrados (era 17). Dispatcher atualizado (12→15 intents). `db_execute` adicionado ao db.py. Path real: `/opt/sparkle-runtime/sparkle-runtime/`.

### [FUNCIONAL] OPS-4 — Friday Proativa (3 crons)
8 crons totais. billing_risk (08:45), risk_alert (09:30), upsell_opportunity (seg 07:30). Anti-spam via `friday_initiative_log`. WhatsApp testado OK.

### [FUNCIONAL] CORE-1 — Workflow Engine
Tabela `workflow_runs` + 3 colunas em `runtime_tasks`. `_maybe_chain_workflow_step` + `_maybe_fail_workflow` + `create_workflow()`. Testes 2-step, falha, regressão: PASS.

### [FUNCIONAL] BRAIN-1 — Auto-ingestão Conversas Friday
`_score_relevance` + `_maybe_learn_from_task` em router.py. Migration: `owner_type` em knowledge_base. Guard R-T4 ativo. Flywheel Lei 7 operacional.

### [FUNCIONAL] CORE-2 — activate_agent Real (@analyst)
Handler refatorado com tool_use loop (4 tools: brain_query, supabase_read, web_search, calculate). 7 camadas isolamento. Teste Vitalis: análise real entregue no WhatsApp. Custo: ~$0.14/execução.

### [FUNCIONAL] OPS-2 — Zenya Alexsandro (Doceria Dona Geralda)
Z-API Instance ID: `3F0F411ADEA0E14E6F41261BBD342883` | Token: `271488F5849EE2DC665504F4`
KB 193 registros (7 categorias). Workflow 01 JÁ ATIVO — 729 execuções, 99.86% sucesso. Persona "Ge".
Chatwoot: conta 3, inbox 14 ("Zenya Dona Geralda"), access token Mauro: `SU2G1rpjeREnwjSfm2oe278Z`.
`zenya_clients` registro criado no Supabase (UUID: cf635e33). Sistema já operacional em modo teste.
Pendente: Mauro confirmar com Alexsandro → tirar tag "testando-agente" → go-live real.

### [PENDENTE segunda] OPS-3 — Zenya Ensinaja
Douglas enviou dados dos cursos (2026-04-02). KB parcial, precisa ingestão. Véspera de feriado — go-live para segunda-feira.
Dados extraídos do Google Doc (10 cursos com valores/formas de pagamento). WhatsApp escola: (12) 98197-4622. Endereço: Rua Comendador Custódio Vieira, 198 — Lorena.

---

## SESSÃO 2026-04-02 — Sprint 9 + Handlers Runtime

### [INFRA] Path do venv no VPS
**Nota QA**: venv correto fica em `/opt/sparkle-runtime/.venv` (um nível acima do código em `sparkle-runtime/sparkle-runtime/`). Usar sempre esse path para `python -c` e imports.

### [FUNCIONAL] SPRINT9-P3 — Friday TTS
ElevenLabs ativo, voice ID via `ELEVENLABS_VOICE_ID_FRIDAY`, handler ARQ `friday_tts`, fallback para send_text. gTTS não instalado (fallback de texto funciona).

### [FUNCIONAL] SPRINT9-P6 — Brain Auto-create
`ensure_client_brain_space()` idempotente. `POST /zenya/client` cria brain space. `brain_ingest` valida `client_not_found`. Constraint retrocompatível com `client:%`.

### [FUNCIONAL] SPRINT9-P7 — Conclave
3 perspectivas paralelas (analyst/architect/strategic) via Haiku + síntese Sonnet. `CONCLAVE_ENABLED` flag. Gate heurístico `is_complex_query` no dispatcher. Edge case: query curta (<50 palavras + 1 trigger) pode não ativar heurística secundária — gate primário LLM cobre.

### [FUNCIONAL] SPRINT8-TECH — Supabase Connection Pool
`db.py` reescrito: `DB_SEMAPHORE(12)`, `max_connections=30`, `pool_timeout=15s`, `db_execute` com retry 3x + jitter. `get_async_http_client()` singleton. `max_jobs=6`, `limit=10`. 2 httpx efêmeros residuais em Z-API e OpenAI (não bloqueantes).

### [AGUARDANDO_ATIVACAO] BLOCK-03 — Fun Personalize (Julia)
Infra pronta: endpoints `/zenya/*` multi-tenant, `zenya_clients` com `fun-personalize` (`active=false`), `loja_integrada_query` registrado. Falta: API key Loja Integrada de Julia + Z-API instance. Quando chegar: `echo "LOJA_INTEGRADA_API_KEY=X" >> .env && systemctl restart sparkle-runtime` + UPDATE zenya_clients SET active=true, zapi_instance_id=X WHERE client_id='fun-personalize'.

### [FUNCIONAL] RUNTIME-HANDLERS-CLOSE-LOOP
`send_character_message` handler criado com `db_execute`, histórico em `zenya_messages`. Tabela `zenya_messages` criada (`client_id, phone, role, content, created_at`). `onboard_client` agora fecha upsert em `zenya_clients active=True`. Loop Runtime clientes completo.

---

## SESSÃO 2026-04-01 — S8-P3 Brain Embeddings QA

### [APROVADO PARCIAL] QA P3 — Brain Embeddings

**Data**: 2026-04-01 | **Responsável**: @qa | **Status**: APROVADO PARCIAL — falta OPENAI_API_KEY

**O que foi validado:**
- pytest 20/20 PASSED (P1 + P3 completos) ✓
- Health: status=ok, supabase=true, zapi=true, groq=true, anthropic=true ✓
- Friday smoke: `/friday/message` "qual meu MRR atual?" → R$5.491/mês, 7 clientes (sem regressão) ✓
- Dry-run backfill: 101 chunks, 34.301 chars, **$0.000172 USD** custo estimado ✓
- `.env` VPS: `BRAIN_EMBEDDINGS_ENABLED=false`, OPENAI_API_KEY comentada (não configurada) ✓
- `brain_ingest.py` P3: `asyncio.create_task()` background embedding pós-INSERT confirmado ✓
- `brain_ingest.py` P3: falha silenciosa — ingestão nunca bloqueada confirmado ✓
- `brain_query.py` P3: threshold de similaridade + fallback text search confirmado ✓

**PENDENTE (bloqueado por OPENAI_API_KEY — @devops configura):**
- AC-2: ingest com embedding real
- AC-3: smoke semântico "visão de longo prazo" → "império Sparkle"
- AC-6: backfill real executar sem --dry-run

**Arquivo:** `docs/reviews/qa-p3-brain-embeddings.md`

**Handoff @devops:** Configurar `OPENAI_API_KEY` no VPS + `BRAIN_EMBEDDINGS_ENABLED=true`, reiniciar runtime, executar backfill, sinalizar @qa para smoke final.

---

## SESSÃO 2026-04-01 — S8-P3 Brain Embeddings (IMPLEMENTADO)

### [IMPLEMENTADO] P3 — Brain Embeddings — aguardando OPENAI_API_KEY + QA

**Data**: 2026-04-01 | **Responsável**: @dev | **Status**: ARTEFATOS PRONTOS — PENDENTE OPENAI_API_KEY

**O que foi implementado:**
- `runtime/utils/embeddings.py` — abstração provider-agnóstica (OpenAI/futuro Cohere/local)
  - `generate_embedding(text)` — falha silenciosa, retorna None se flag desabilitada ou key ausente
  - `estimate_cost_usd(total_chars)` — $0.02/1M tokens (text-embedding-3-small)
  - Feature flag: `BRAIN_EMBEDDINGS_ENABLED=false` por padrão
- `runtime/tasks/handlers/brain_ingest.py` — background task via `asyncio.create_task()` pós-INSERT
  - Ingestão retorna imediatamente, embedding gerado assincronamente
  - Falha no embedding não bloqueia ingestão
- `runtime/tasks/handlers/brain_query.py` — threshold de similaridade aplicado
  - Filtra resultados RPC `match_brain_chunks` por `similarity >= brain_similarity_threshold`
  - Se threshold eliminar tudo → fallback para text search automaticamente
  - Logs de similaridade adicionados ao _format_chunks para diagnóstico
- `runtime/config.py` — `brain_embeddings_enabled` (default False) + `brain_similarity_threshold` (default 0.75)
- `scripts/backfill_embeddings.py` — batches de 10, pausa 1s, alerta se custo > $1, `--dry-run`
- `.env` VPS — `BRAIN_EMBEDDINGS_ENABLED=false`, `BRAIN_SIMILARITY_THRESHOLD=0.75` configurados
- `tests/test_brain_embeddings.py` — 10 testes novos, 20/20 total passando

**DRY-RUN BACKFILL (AC-5):**
- 101 chunks sem embedding | 34.301 chars | **Custo estimado: $0.000172 USD** (< $0.001)
- Custo máximo com margem 20%: $0.000206 USD
- Modelo: text-embedding-3-small @ $0.02/1M tokens

**PENDENTE (bloqueado por OPENAI_API_KEY):**
- AC-1: @devops configura `OPENAI_API_KEY` no VPS `/opt/sparkle-runtime/sparkle-runtime/.env`
- AC-2: Após key + `BRAIN_EMBEDDINGS_ENABLED=true` → testar ingest com embedding
- AC-3: Smoke test semântico: "visão de longo prazo" → encontrar "império Sparkle"
- AC-6: Backfill real executar com `python scripts/backfill_embeddings.py` (sem --dry-run)
- QA: smoke test final em produção após ativação

**Para ativar embeddings (Orion decide timing):**
```bash
# 1. Adicionar no .env do VPS:
OPENAI_API_KEY=sk-...
BRAIN_EMBEDDINGS_ENABLED=true

# 2. Rodar backfill real:
cd /opt/sparkle-runtime/sparkle-runtime
python scripts/backfill_embeddings.py

# 3. Reiniciar runtime:
systemctl restart sparkle-runtime
```

---

## SESSÃO 2026-04-01 — S8-P1 Brain Separation QA

### [APROVADO] QA P1 — Brain Separation FUNCIONAL

**Data**: 2026-04-01 | **Responsável**: @qa | **Status**: APROVADO COM RESSALVA — P3 DESBLOQUEADO

**O que foi validado:**
- DB: 101 registros `pipeline_type='mauro'`, 0 `cliente` — isolamento perfeito ✓
- pytest 10/10 PASSED com `/opt/sparkle-runtime/.venv/bin/pytest` ✓
- brain_ingest validações 400 (missing/invalid owner_type, client sem client_id) ✓
- brain_query isolamento mauro vs cliente confirmado ✓
- dispatcher.py injeta `owner_type='mauro'` para Friday ✓
- Health: supabase=true, todos checks ok ✓
- Friday smoke: `qual meu MRR atual?` → R$5.491/mês, 7 clientes (dados reais) ✓
- knowledge_base preservada (101 registros, não dropada) ✓

**Bug tech-debt (não bloqueia P3):**
- Text search fallback falha multi-palavra PT-BR (`plainto_tsquery` stopwords)
- Single-word funciona. Solução permanente: P3 Embeddings.

**Arquivo:** `docs/reviews/qa-p1-brain-separation.md`

**P3 DESBLOQUEADO** — @dev pode iniciar Brain Embeddings.

---

## SESSÃO 2026-04-01 — S8-P5 Instagram Webhook

### [APROVADO] QA P5 — Endpoint /instagram/webhook

**Data**: 2026-04-01 | **Responsável**: @qa | **Status**: APROVADO — handoff Orion

**O que foi validado:**
- GET challenge com token correto → retorna challenge (plain text) ✓
- GET token errado → 403 ✓
- GET sem token → 403 ✓
- POST DM válida (object=instagram) → 200 OK, background task disparado ✓ (retorna `{"status":"ok"}` — spec pedia "queued", divergência mínima, não bloqueia)
- POST payload não-instagram (object=page) → `{"status":"ignored","reason":"..."}` ✓
- Health check → ok, Supabase+Z-API+Groq+Anthropic todos conectados ✓
- `runtime/instagram/router.py` existe e registrado em main.py (linha 50+58) ✓

**Variáveis confirmadas no .env VPS:**
- `INSTAGRAM_VERIFY_TOKEN=test` — funcional
- `INSTAGRAM_PAGE_TOKEN=` — placeholder (esperado — aguarda app Meta real)

**Arquivo de relatório:** `docs/reviews/qa-p5-instagram-webhook.md`

**Handoff para Orion / Mauro:**
Webhook pronto tecnicamente. Para ativar canal Instagram real:
1. Criar app no Meta for Developers
2. Registrar webhook URL: `https://runtime.sparkleai.tech/instagram/webhook`
3. Verify token: `test` (ou atualizar INSTAGRAM_VERIFY_TOKEN para valor mais seguro)
4. Obter Page Token → atualizar `INSTAGRAM_PAGE_TOKEN` no .env do VPS (via SSH)
5. Assinar evento `messages` no painel do app Meta

---

## SESSÃO 2026-04-01 — S8-P2 Friday Autônoma

### [APROVADO QA] Friday Iniciativas Proativas — P2 aprovado, crons desabilitados

**Data**: 2026-04-01 | **Responsável**: @qa | **Status**: APROVADO — handoff Orion

**O que foi validado:**
- Health runtime: ok (supabase, zapi, groq, anthropic todos true) ✓
- Anti-spam: 6 window_keys, todos count=1 — zero duplicatas ✓
- UNIQUE constraint `friday_initiative_log_window_key_key` ativo no DB ✓
- Endpoint `POST /friday/trigger-initiative` com dry_run=true → 200 OK ✓
- 3 handlers com `asyncio.to_thread` correto (sem await em função síncrona) ✓
- window_key sem None: fallback implementado em risk e billing, upsell usa PK de clients ✓
- Crons desabilitados: 3 linhas `add_job` comentadas em scheduler.py ✓
- Alertas enviados APENAS para Mauro (5512981303249) — confirmado via Supabase log ✓

**Pendências antes de reabilitar crons (gate Orion):**
- Popular `has_zenya` e `has_trafego` em tabela `clients` (upsell_opportunity)
- Confirmar janela billing_risk (<= 3 dias) com Mauro
- Confirmar frequência desejada (diário vs on-demand)
- Descomentar 3 linhas em scheduler.py + restart VPS

**Relatório QA:** `docs/reviews/qa-p2-friday-autonoma.md`

---

### [FUNCIONAL] Friday Iniciativas Proativas — 3 tipos ativos

**Data**: 2026-04-01 | **Responsável**: @dev | **Status**: FUNCIONAL — handoff @qa

**O que foi feito:**
- Tabela `friday_initiative_log` confirmada no Supabase: colunas `initiative_type`, `client_id`, `client_name`, `window_key`, `message_preview`, `sent_at`, `zapi_response`, `dismissed_by_mauro`. UNIQUE constraint em `window_key` ativo.
- RPC `get_clients_without_recent_activity` confirmada existente.
- Endpoint `POST /friday/trigger-initiative` implementado em `runtime/friday/router.py` — aceita `risk_alert`, `billing_risk`, `upsell_opportunity`.
- Registry (`runtime/tasks/registry.py`) com os 3 task_types registrados: `friday_initiative_risk`, `friday_initiative_billing`, `friday_initiative_upsell`.
- Scheduler (`runtime/scheduler.py`) com 3 crons: risk 9h30, billing 8h45, upsell seg 7h30 Brasília — confirmado no log de startup.
- **Bug corrigido**: handlers chamavam `await send_whatsapp_text(...)` mas `send_text` é síncrona. Patch aplicado nos 3 handlers: `await asyncio.to_thread(send_whatsapp_text, ...)`.
- **Bug corrigido**: `window_key` usava `client_id` que era `None` para clientes vindos de `v_payments_overdue` (view sem UUID). Patch aplicado: fallback para `whatsapp` ou `client_name` limpo.

**Testes realizados:**
- `POST /friday/trigger-initiative {"initiative_type": "risk_alert"}` → 200 OK, `sent: 6` (6 alertas enviados para Mauro via Z-API real)
- Segundo trigger mesmo dia → `sent: 0, skipped_spam: 6` — anti-spam UNIQUE funcionando
- `POST /friday/trigger-initiative {"initiative_type": "billing_risk"}` → 200 OK, `sent: 0` (sem vencimentos em <= 3 dias hoje — correto)
- `POST /friday/trigger-initiative {"initiative_type": "upsell_opportunity"}` → 200 OK, `sent: 0` (sem clientes com gap has_zenya/has_trafego configurado)
- `friday_initiative_log` persistindo com window_keys únicos por cliente/data/tipo

**Pendente para @qa:**
- AC-6: Mauro confirmar recebimento de ao menos 1 mensagem proativa real (já enviado 6 no teste — verificar WhatsApp)
- Validar billing e upsell quando dados reais existirem (clientes próximos do vencimento ou com gap de produto)
- Testes unitários com mock de Z-API e Supabase (opcional para DoD completo)

**Arquivos modificados no VPS:**
- `/opt/sparkle-runtime/sparkle-runtime/runtime/tasks/handlers/friday_initiative_risk.py` — patch asyncio.to_thread + window_key fix
- `/opt/sparkle-runtime/sparkle-runtime/runtime/tasks/handlers/friday_initiative_upsell.py` — patch asyncio.to_thread
- `/opt/sparkle-runtime/sparkle-runtime/runtime/tasks/handlers/friday_initiative_no_contact.py` — patch asyncio.to_thread

---

## SESSÃO 2026-04-01 — S8-P1 Brain Separation

### [FUNCIONAL] Brain Separation Mauro vs Clientes

**Data**: 2026-04-01 | **Responsável**: @dev | **Status**: FUNCIONAL — P3 desbloqueado

**O que foi feito:**
- Migration SQL aplicada: 101 registros de `knowledge_base` migrados para `brain_chunks` com `pipeline_type='mauro'`. View `v_knowledge_base_pre_migration` criada como backup. `knowledge_base` intacta.
- RPC `match_brain_chunks` atualizada para suportar `pipeline_type='mauro'` (sem filtro de client_id). RPC `search_brain_text` criada para fallback textual.
- `brain_ingest.py` refatorado: `owner_type` obrigatório no payload → 400 se ausente. Rota para `brain_chunks` (não mais `knowledge_base`). `pipeline_type='mauro'` ou `'cliente'`.
- `brain_query.py` refatorado: `_search_knowledge_base` com isolamento por `owner_type`. Vector search via `match_brain_chunks` + fallback text via `search_brain_text`.
- `runtime/friday/dispatcher.py` atualizado (T4): injeta `owner_type='mauro'` nos payloads de `brain_query` e `brain_ingest` (Friday sempre é Mauro).
- `tests/test_brain_isolation.py` criado: 10 testes — 10/10 PASSED em 2.32s.
- Runtime restartado: health OK, supabase/zapi/groq/anthropic todos true.
- SMOKE-05: `POST /character/message` (Zenya slug=zenya) responde normalmente.

**Verificação de isolamento confirmada:**
- `SELECT pipeline_type, COUNT(*) FROM brain_chunks GROUP BY pipeline_type` → `mauro: 101`, `cliente: 0`
- Query mauro não retorna chunks de cliente (teste automatizado passando)
- Query cliente não retorna chunks de mauro (teste automatizado passando)

**Nota**: Os 101 chunks migrados são dados de clientes que estavam sob `sparkle-internal` — Brain Mauro genuíno ainda precisa ser alimentado via Friday. Embeddings ficam NULL até P3.

**Handoff para @qa**: validar ACs via endpoints reais. Ver story `docs/stories/sprint-8/p1-brain-separation.md`. P3 (Brain Embeddings) está desbloqueado.

---

## SESSÃO 2026-04-01 — Fun Personalize Loja Integrada Integration

### [FUNCIONAL] integrations/loja_integrada.py + handler refactor

**Data**: 2026-04-01 | **Responsável**: @dev

**O que foi feito:**
- Criado `runtime/integrations/loja_integrada.py` — camada de API pura seguindo padrão de `zapi.py`. Funções: `get_api_key`, `is_configured`, `get_orders_by_cpf`, `get_orders_by_email`, `get_order_by_id`, `format_order`, `format_date`, `format_currency`, `status_label`.
- Refatorado `runtime/tasks/handlers/loja_integrada_query.py` para importar da camada de integração — sem lógica HTTP/formato duplicada.
- Endpoint `GET /zenya/order?store=fun_personalize&query={texto}` testado com 4 cenários (pedido_id, email, store inválida, sem identificador) — todos passaram.
- Commit no VPS: `21e9a45`

**Estado**: FUNCIONAL aguardando LOJA_INTEGRADA_API_KEY da Julia.
**Ação quando Julia enviar key**: `echo "LOJA_INTEGRADA_API_KEY=VALOR" >> /opt/sparkle-runtime/sparkle-runtime/.env && systemctl restart sparkle-runtime` — integração ativa imediatamente sem nenhum outro deploy.

**Handoff para @qa**: validar endpoint com API key real quando Julia enviar.

---

## SESSÃO 2026-04-01 — S8-P6 Mission Control

### [FUNCIONAL] Mission Control — /mission-control portal page

**Commit:** `21c280e` (main)

**Arquivos criados:**
- `portal/app/mission-control/page.tsx` — página completa com PhaseTimeline (6 fases), ActivePhaseSection, AgentCard grid, accordion fases completas, empty/loading/error states, StatusLegend. SVG inline (sem emoji). Decisão: sem link no layout.tsx — acesso direto por URL.
- `portal/hooks/useAgentWorkItems.ts` — Supabase Realtime + fallback polling 30s, STATUS_MAP completo, prioridade error>active>blocked>idle>done
- `portal/components/AgentCard.tsx` — 5 estados visuais, glow effects, animate-pulse só no active dot, formatElapsed

**Supabase:**
- `agent_work_items` já estava na `supabase_realtime` publication — confirmado via `pg_publication_tables`
- Seed de 9 rows inserido cobrindo todos os 5 estados (em_execucao, aguardando_qa, funcional, pendente, erro)
- FK em `output_type` referencia `responsibility_registry` — valores válidos consultados antes do INSERT

**Deploy:** CI/CD automático via push para main (.github/workflows/deploy-portal.yml)

**Status story:** APROVADO_QA — pronto para deploy

**QA @qa — 2026-04-01:**
- Build TypeScript: PASSOU (zero erros, /mission-control 61.4 kB)
- Lint: PASSOU após correção D1 (`.eslintrc.json` ausente — criado pelo @qa)
- STATUS_MAP: todos os 5 status do seed mapeados corretamente
- Priority sort: error(0) > active(1) > blocked(2) > idle(3) > done(4) — OK
- AgentCard 5 estados: spec match 100% (dotColor, borderColor, bgColor, glow, animate)
- layout.tsx: intacto, sem nav adicionado — conforme UX spec §10
- Seed: 9 rows, 5 status distintos, 8 agentes distintos — confirmado via Supabase MCP
- Realtime publication: `agent_work_items` em `supabase_realtime` — confirmado
- Defect D1 (MENOR): `.eslintrc.json` ausente — CORRIGIDO pelo @qa
- Relatório completo: `docs/reviews/qa-p6-mission-control.md`

**Handoff @devops:**
- Incluir `portal/.eslintrc.json` no commit/push (arquivo criado pelo @qa)
- Push para main aciona CI/CD automaticamente
- Pós-deploy: SMOKE-06 + SMOKE-11 no browser
- Mauro valida AC-1 (< 2s) e AC-3 (5 estados) no celular 390px

---

## SESSÃO 2026-04-01 — Fix Supabase 502 Under Load

### [FUNCIONAL] Runtime db.py — Pool httpx + Semáforo + Retry com backoff

**Problema root cause:** `db.py` original usava `create_client()` sem opções de pool — cada `asyncio.to_thread()` paralelo tentava abrir conexão HTTP simultaneamente. O free tier PostgREST do Supabase tem cap de ~10 conexões simultâneas, causando 502 "Server disconnected" em 7+ chamadas paralelas.

**Fix implementado em `/opt/sparkle-runtime/sparkle-runtime/runtime/db.py`:**
- `httpx.Client` com `Limits(max_connections=5, max_keepalive_connections=5, keepalive_expiry=30)` injetado via `SyncClientOptions(httpx_client=...)`
- `asyncio.Semaphore(_MAX)` criado lazy — gate de concorrência espelha o pool limit
- `execute_with_retry(fn, label)` — wrapper async com 3 tentativas, backoff exponencial (0.5s, 1s, 2s) para `ConnectError`, `RemoteProtocolError`, `ReadError`, `TimeoutException`, 502, "server disconnected"
- `SUPABASE_MAX_CONNECTIONS` env var adicionada em `config.py` (default=5, tunável)
- Interface pública preservada: `supabase` singleton — todos os 32 callers existentes continuam funcionando sem alteração

**Commit:** `43f5447` no VPS (branch master)

**Teste de carga:** 10 queries paralelas via `asyncio.gather()` → 10/10 OK, 0 falhas, 0.40s total

**Health check pós-restart:** `{"status":"ok","supabase":true,"zapi_connected":true,"anthropic_configured":true}`

**Handoff para @qa:** Re-testar carga com o endpoint `/health` e um endpoint real de conversação (ex: `/zenya/message`) com 7+ chamadas simultâneas — deve retornar 0 502s.

---

## SESSÃO 2026-04-01 — S8-P5 Instagram Webhook Endpoint

### [FUNCIONAL] Runtime — `/instagram/webhook` GET + POST implementado e testado

**Sprint:** S8-P5 — Instagram DM Piloto
**VPS path:** `/opt/sparkle-runtime/sparkle-runtime/runtime/instagram/`

**O que foi implementado:**
- `runtime/instagram/__init__.py` — módulo criado
- `runtime/instagram/router.py` — router FastAPI com:
  - `GET /instagram/webhook` — Meta challenge handshake. Retorna `hub.challenge` como `text/plain`. Rejeita token errado ou vazio.
  - `POST /instagram/webhook` — recebe DM events Meta. Ack imediato 200. Processa em background via `classify_and_dispatch` (mesmo da Friday). Ignora payloads sem `object: instagram`.
  - `_send_instagram_reply()` — reply via Graph API v19.0 `/me/messages`. Silencioso se `INSTAGRAM_PAGE_TOKEN` não configurado.
- `runtime/config.py` — `instagram_verify_token` + `instagram_page_token` adicionados
- `.env` — `INSTAGRAM_VERIFY_TOKEN=test` + `INSTAGRAM_PAGE_TOKEN=` (placeholder para produção)
- `main.py` — router registrado em `/instagram`

**Testes passados no VPS:**
- `GET ?hub.mode=subscribe&hub.verify_token=test&hub.challenge=abc123` → `abc123` OK
- `GET` com token errado → `Forbidden` OK
- `GET` com token vazio → `Forbidden` OK (edge case corrigido)
- `POST {object: instagram, DM event}` → `{"status":"ok"}` OK
- `POST {object: page}` → `{"status":"ignored"}` OK
- `GET /health` → `{"status":"ok"}` OK

**Env vars para produção (Mauro preenche após App Review Meta):**
- `INSTAGRAM_VERIFY_TOKEN` — token escolhido ao configurar webhook no Developer Portal
- `INSTAGRAM_PAGE_TOKEN` — System User Token com permissão `instagram_manage_messages`

**Próximo passo:** @qa validar em Development Mode + Mauro registrar webhook URL no Developer Portal Meta

---

## SESSÃO 2026-04-01 — S8-P5 Meta Instagram App Setup

### [ARTEFATO] Meta Instagram App Setup — Guia operacional criado

**Arquivo:** `docs/operations/meta-instagram-app-setup.md`
**Sprint:** S8-P5 — Instagram DM Piloto

**O que foi feito:**
- Pesquisa completa do processo atual Meta Instagram Messaging API (2025/2026)
- Confirmado: API ainda é Instagram Graph API / Instagram Platform — não houve migração para nome diferente
- Documentado processo completo: criação do app, webhook setup, System User Token, App Review
- Mapeado que `META_TOKEN_SPARKLE` existente NÃO serve para Instagram Messaging — precisa de app separado
- Identificadas 5 permissões necessárias para Advanced Access
- Documentados templates de texto para o App Review (descrição + use case + roteiro do vídeo)

**Decisão arquitetural registrada:** Usar Facebook Login (Business Manager) e não Instagram Login — permite gerenciar múltiplos clientes via System User Token único.

**Próximas ações:**
- Mauro: criar app no Developer Portal + System User Token (2 etapas, ~25 min total)
- @dev: implementar endpoint `/instagram/webhook` no Character Runtime (sem Mauro)
- App Review: submeter após @qa validar em Development Mode — prazo de aprovação 5–10 dias úteis

---

## SESSÃO 2026-04-01 — Character Runtime E2E + Portal + Vitalis SQL

### [FUNCIONAL] Character Runtime — Fix deploy + teste E2E

**Problema**: `sparkle-runtime.service` apontava para `/opt/sparkle-runtime` (código antigo sem modules agents/characters/members/zenya). Repo correto estava clonado em `/opt/sparkle-runtime/sparkle-runtime/`.

**Fix aplicado**:
- `/etc/systemd/system/sparkle-runtime.service`: `WorkingDirectory` e `EnvironmentFile` atualizados para `/opt/sparkle-runtime/sparkle-runtime`
- `.env` copiado do diretório antigo para o novo
- `systemctl daemon-reload && systemctl restart sparkle-runtime`

**Resultado**: Serviço UP, ambos workers healthy. Testado E2E:
- `GET /character/finch` → perfil retornado corretamente
- `POST /character/message` Finch → resposta Claude sonnet-4-6, stateful, soul_prompt ativo
- `POST /character/message` Zenya → resposta correta como assistente
- `GET /health` → status "ok", supabase/zapi/anthropic todos verdes

**Nota curl**: Curl do Windows com aspas especiais causa "error parsing body" — testar via SSH no VPS ou com ferramenta HTTP adequada.

### [FUNCIONAL — DNS PENDENTE] Portal — Container rodando no VPS

**Estado**: Container `sparkle-portal` UP na porta 3000, respondendo HTTP 200 internamente.

**Deploy realizado**:
- Dockerfile corrigido (removido COPY public/ que não existe)
- Repo clonado em `/opt/sparkle-portal/` no VPS
- Imagem buildada: `sparkle-portal:latest`
- Rede criada: `sparkle-portal-net` (coolify-proxy conectado)
- Container rodando com todas as env vars e Traefik labels
- Traefik configurado para `portal.sparkleai.tech` com TLS Let's Encrypt

**Pendente**: Registro DNS `A portal → 187.77.37.88` no painel Hostinger. Após DNS propagar, portal estará em https://portal.sparkleai.tech

**Env vars ativas no container**: ver `.env` no Coolify (não versionar credenciais)

### [MAPEADO] Vitalis SQL — Aguarda decisão @architect

**Ver seção abaixo.**

---

## SESSÃO 2026-04-01 — Sprint 8 Launch + QA Smoke/Persona Tests

### [FUNCIONAL] QA Sprint 8 — Smoke + Persona Tests Aprovados

**Data**: 2026-04-01 | **Responsável**: @qa + Orion

**Smoke Tests (19)**: 10 PASS | 1 FAIL (falso positivo) | 8 SKIP
- FAIL INT-02: ElevenLabs API key "ausente" — **FALSO POSITIVO**: o smoke script não carrega o .env. Confirmado via `GET /friday/tts-info` → `elevenlabs / Roberta / active` ✅
- SKIPs: credenciais não exportadas no shell (runtime usa corretamente via .env)

**Persona Tests (19)**: 18 PASS | 1 FAIL intermitente (502 Supabase sob carga)
- Gênero correto (F): 10/10
- Capacidades: MRR retornou R$5.491 (dados vivos), @dev acionado com task ID real
- Presença: briefing semanal gerado proativamente
- Injection resistance: 3/4 — o 4o falhou por 502, reteste passou

**Issues reais identificados**:
1. Supabase perde conexão em 7+ chamadas paralelas → issue SPRINT8-TECH no agent-queue.md
2. ElevenLabs: funcional, sem ação necessária

**Voice fix confirmado**: Roberta (`RGymW84CSmfVugnA5tvA`) ativa. Rachel removida.

**Relatório completo**: `docs/reviews/qa-sprint8-smoke-results.md`

---

### [EM_EXECUCAO] Sprint 8 — Agentes Lançados

| Agente | Entregável | Status |
|--------|-----------|--------|
| @pm | `docs/sprints/sprint-8-prds.md` | ✅ CONCLUÍDO |
| @analyst | `docs/sprints/sprint-8-viability.md` | ✅ CONCLUÍDO |
| @po | `docs/sprints/sprint-8-po-kickoff.md` | ✅ CONCLUÍDO |
| @qa | `docs/reviews/qa-sprint8-smoke-results.md` | ✅ CONCLUÍDO |
| @architect | `docs/sprints/sprint-8-tech-specs.md` | ⏳ EM EXECUÇÃO |
| @sm | Stories com AC/DoD | 🔲 Aguarda @architect |

**Perguntas pendentes para Mauro**:
- Q1: Qual cliente para piloto Instagram DM?
- Q3: Quais 3 alertas autônomos da Friday?
- Q4: Mission Control no portal ou via Friday primeiro?
- Sessão lore Zenya: quando?

---

## SESSÃO 2026-04-01 — Desativação Workflows Internos n8n (Sparkle Runtime)

### [FEITO] n8n — Desativação de workflows substituídos pelo Runtime

**Script**: `scripts/n8n-deactivate-internal.py`
**Auth**: header `X-N8N-API-KEY`; endpoint correto: `POST /api/v1/workflows/{id}/deactivate`

| ID | Nome | Resultado |
|----|------|-----------|
| `Izoupz82zVf6kZRQ` | Friday Brain | SKIP — ID não encontrado no n8n (provavelmente já removido) |
| `zxznYpW2PBhJrGjV` | Friday Notifier | JA_INATIVO — nenhuma ação necessária |
| `hCukbZX875Y18ThZ` | Sparkle Gateway | DESATIVADO com sucesso |
| `LMcmB2oYX5RGnFxc` | ZApi Router | DESATIVADO com sucesso |
| `U68uGoBZsRxXSARL` | Weekly Report V2 | DESATIVADO com sucesso |

Workflows de clientes (Plaka, Confeitaria, Ensinaja) e infra (supabase keep-alive, n8n backup) **não foram tocados**.

---

## SESSÃO 2026-04-01 — Gabriela Meta Ads (Nova Campanha WhatsApp)

### [PARCIAL] Campanha Gabriela — Consórcio Veículos Rio Verde/GO

**Status**: Campanha + AdSet + Upload de vídeo/imagem CONCLUÍDOS. Creative/Ad BLOQUEADOS por app Meta em modo desenvolvimento.

**IDs criados (PAUSED, reutilizáveis):**
- `campaign_id`: `120241237415280772`
- `adset_id`: `120241237534650772` (último — há orphans de testes anteriores)
- `video_id`: `4369573166647389` (IMG_8733.MP4, 21.9MB)
- `image_hash`: `1760dc0c4c5ae307d06b438147cd6640` (thumbnail)

**Configuração validada:**
- Geo: Rio Verde/GO — key `267187`, raio 17km (15km dá erro de limite na API)
- Objective: OUTCOME_ENGAGEMENT + is_adset_budget_sharing_enabled=false
- Optimization: CONVERSATIONS + MESSENGER (WHATSAPP bloqueado — Page tem número pessoal, não Business)
- bid_strategy: LOWEST_COST_WITHOUT_CAP
- targeting_automation: advantage_audience=0 (obrigatório para MESSENGER)
- Interesses: Automóveis (6003176678152), Automotive design (6003641420907), Business/Consórcio (6003402305839), Financiamento (6003321839097), Veículos (6003133486214)
- Orçamento: 2000 centavos/dia = R$20

**BLOQUEIO ATIVO (error_subcode 1885183):**
App Meta vinculado à conta `act_1273799064911268` está em **modo de desenvolvimento**.
- Acao: Mauro deve acessar developers.facebook.com -> selecionar o app -> "Modos de app" -> mudar para "Publico" (Live)
- Apos isso: re-executar `scripts/gabriela-ads-create.py` — script é idempotente, reutiliza campanha/adset existentes

**2 pendencias adicionais para Gabriela:**
1. Conectar WhatsApp Business a Page `456788517514349` para usar destination_type=WHATSAPP nativo
2. Fornecer @handle Instagram para campanha de retargeting (bloqueada desde sessao anterior)

**Script**: `scripts/gabriela-ads-create.py`

---

## SESSÃO 2026-03-31 — Sprint 8 + Gabriela + Fix Plaka

### ✅ FEITO

- **Sprint 8 — Onboarding Autônomo**: Sparkle Runtime agora faz onboarding completo de cliente. 4 arquivos modificados: `runtime/tasks/handlers/onboard_client.py` (novo), `runtime/friday/dispatcher.py` (intent onboard_client), `runtime/tasks/registry.py` (registro), `runtime/friday/router.py` (endpoint POST /onboard). Fluxo: scrape site (httpx, verify=False) → Claude Sonnet gera KB + system prompt → upsert Supabase clients → insert zenya_knowledge_base → clone 4 workflows n8n → notifica Mauro.
- **Gabriela Meta Ads — 2 campanhas + 4 ad sets criados** via Meta API v19.0 (PAUSED). Desafios: interest IDs deprecados (solução: `/search` API para novos IDs), objetivo LEADS incompatível sem pixel (solução: OUTCOME_TRAFFIC + LINK_CLICKS), Advantage+ obrigatório declarar (solução: `targeting_automation: {advantage_audience: 0}`). Análise histórica CSV: objetivo original era MESSAGES, R$6,74/conversa, frequência 4,96 (saturado), criativo de vídeo 23% completion. Retargeting (campanha 3) bloqueado: precisa Instagram @handle da Gabriela.
- **Plaka workflow 371QcYGrXmZ1n8bV — CORRIGIDO E REATIVADO**: Model `gpt-4.1-mini-2025-04-14` → `gpt-4.1-mini`. Processo de fix: GET → strip campos read-only (id, versionId, createdAt, updatedAt, tags) + campos extras de settings (binaryMode, availableInMCP) + active → PUT → POST /activate. Agora ativo.
- **Meta token atualizado** em settings.json com novo token de longa duração para a BM Sparkle.

---

## INFRAESTRUTURA AIOS — Fábrica / Gap Closure

### ✅ FEITO (2026-03-30) — Sessão Fase 0 → 0.5

- **02-data-schema.sql executado**: 4 bugs corrigidos (função update_updated_at_column, ARRAY[]::TEXT[], nomes @pm/@ux, FK forward reference). Schema completo no Supabase.
- **Bootstrap 8 agentes**: `docs/operations/agent-bootstrap/` — architect.md, devops.md, po.md, pm.md, sm.md, ux.md, data-engineer.md, squad-creator.md. Todos os 11 agentes agora têm bootstrap.
- **Constitution v1.1**: Princípio 8 adicionado — "Colaboração Proativa Dentro do Escopo". Ativação sem Orion como intermediário.
- **agent-toolkit-standard.md**: Model routing table (Opus/Sonnet/Haiku/Groq por tipo de tarefa), "Use or Lose" critérios mensais, 3 perguntas obrigatórias antes de adicionar ferramenta.
- **08-sector-processes.md**: PT-1 (Landing Page E2E), PT-2 (Planejamento de Iniciativa Grande), PT-3 (Onboarding Meta Ads) adicionados.
- **AGENT_CONTEXT.md**: Atualizado com Princípio 8, 11 agentes, Sparkle Brain section, processos PT-1/PT-2/PT-3.
- **fase-0.5-megabrain-dev-brief.md**: Brief completo para @dev implementar Sparkle Brain — pipeline 7 estágios, DNA schema 6 camadas, Cargo Agents, Conclave, Skills, spec de 5 workflows n8n.
- **Squads C-01/C-02**: Validados por Orion. Fixes corretos, headers v1.1.0.
- **Weekly Report V2 PUT**: PUT feito via API n8n (ID: U68uGoBZsRxXSARL, 12 nodes, 2026-03-30 06:41 UTC). Aguarda ativação manual.
- **clone-zenya-client.py QA**: 2 gaps identificados: 4 vs 13 workflows + system_prompt_id ausente. Aguardando confirmação Mauro.
- **agent-queue.md**: Atualizado com status corretos, BLOCK-07 adicionado, tabela FUNCIONAL expandida.

### ✅ FEITO (2026-03-29)
- **Supabase `agent_queue`**: Tabela criada com RLS + trigger updated_at + view `v_agent_queue_active`. 11 itens do agent-queue.md importados. A "esteira da fábrica" — estado visível persistido, consultável por qualquer agente via `mcp__supabase__execute_sql`.
- **Bootstrap por agente**: `docs/operations/agent-bootstrap/dev.md`, `qa.md`, `analyst.md` — contrato executável de ativação. Ferramentas obrigatórias, anti-padrões, checklist, handoff format. Referenciados no AGENT_CONTEXT.md.
- **Community Skills**: Seção do toolkit corrigida — comandos `npx skills add` eram aspiracionais/inexistentes. Documentado o que realmente existe: 9 agentes AIOS já instalados em ~/.claude/settings.json.
- **AGENT_CONTEXT.md**: Seção "Bootstrap por Agente" adicionada com tabela de links.
- **docs/agent-queue.md**: ITEM-05 marcado FUNCIONAL, 12 novos itens adicionados à tabela de referência.
- **@sm — Agent Activation Templates**: 6 arquivos criados em `docs/operations/agent-activation/`: template-base.md, activation-dev.md, activation-qa.md, activation-analyst.md, handoff-automatico.md, rotinas-independentes.md. Novo formato `PROMPT_PARA_PRÓXIMO` definido. 5 rotinas independentes com gatilho. AGENT_CONTEXT.md e sparkle-os-processes.md atualizados.
- **@devops — Inventário técnico**: DESCOBERTA CRÍTICA — Docker Desktop NÃO está instalado. EXA, Context7, Apify, Playwright todos offline. Supabase MCP é o único funcional. Hooks funcionais. Community Skills (`npx skills add`) nunca foram executadas. ComfyUI/RunPod são Fase 2 (zero instalado). ROOT CAUSE DO GAP: Docker Desktop ausente — uma instalação desbloqueia 4 MCPs.

---

## PLAKA / Roberta

### ✅ FEITO
- **2026-03-26**: Análise do workflow `01 - PLAKA acessórios` — identificado system prompt de 60KB, ferramenta Buscar_base_conhecimento já existente, Google Sheets `1owkGkYk59pMKjQoh0_y3JKWLCxB3MHBQ2VrOoQa6w4s` já configurado com 6 abas
- **2026-03-27**: System prompt atualizado no n8n via API — reduzido de 58.420 → 4.935 chars (92% de redução). Workflow ID: `371QcYGrXmZ1n8bV`
- **2026-03-27**: CSVs com 52 scripts extraídos e salvos em `C:\Users\Mauro\Desktop\`: kb_Produto_Qualidade.csv, kb_Pedidos_Logística.csv, kb_Garantia_Trocas.csv, kb_Compras_Pagamento.csv, kb_Sobre_a_Plaka.csv

- **2026-03-27**: Google Sheets populado via workflow temporário n8n — 52 scripts em 5 abas (Produto & Qualidade:13, Pedidos & Logística:13, Garantia & Trocas:4, Compras & Pagamento:9, Sobre a Plaka:13). Planilha ID: `1owkGkYk59pMKjQoh0_y3JKWLCxB3MHBQ2VrOoQa6w4s`

### ✅ FEITO
- **2026-03-27**: Workflow `15. PLAKA - Rastrear pedido` (ID: `jag4nERPiqJBalYm`) **ativado** via API n8n — estava inativo
- **2026-03-27**: Confirmado que Demo Secretária v3 (ID: `IY9g1qHAv1FV8I5D`) já tem `toolWorkflow` "Rastrear pedido" conectado ao workflow 15
- **2026-03-27**: API Nuvemshop Sparkle Store funcionando (bearer `86c20e999e5d0548d0ac70a3cad5d3ee4f3791f1`, store ID `7480606`) — 3 pedidos reais (#104, #105, #106) com produtos de joalheria
- **2026-03-27**: Demo rastreio validada — simulação de resposta da Roberta testada com dados reais. PRONTA para apresentar à Isa e Luiza
- **2026-03-27**: Decisão — app Nuvemshop será configurado em modo read-only (só consulta, sem alterar) para conforto da Luiza no upgrade

### ⏳ PENDENTE
- **Apresentação Isa/Luiza** — demo pronta, agendar apresentação (amanhã conforme planejado)
- **Setup completo Zenya Roberta** — WhatsApp liberado, configuração do zero pendente
- **Testar** workflow Plaka com novo prompt enxuto — enviar mensagem teste e verificar se Roberta busca KB corretamente
- **Aditivo contratual ou upsell** para formalizar integração Nuvemshop antes de entregar em produção

---

## VITALIS LIFE / João Lúcio

### ✅ FEITO
- **2026-03-26**: Coleta de dados Meta Ads (77 dias) no Supabase — tabelas `meta_campaigns`, `meta_insights` populadas para client_id `0bab562c-9f91-4acc-8e35-cb7b5cee7f88`
- **2026-03-26**: Análise por dia da semana — Ter-Qui melhor CPL (R$9,50-9,80), Sábado pior (R$11,61). Dados em `meta_insights`
- **2026-03-26**: Análise por criativo — Ad C "Comunicado" gerou zero leads em todas campanhas
- **2026-03-26/27**: Relatório completo salvo no Supabase (`meta_account_reports`) — Score 55/100, 5 problemas, 5 recomendações
- **2026-03-26**: Contexto correto: João vende **equipamento de sedação consciente para médicos e dentistas** (B2B, alto ticket) — CPL R$10 é BOM para esse nicho
- **2026-03-27**: [ARTEFATO] Scripts `run_analysis.py` e `save_report.py` criados em `C:\Users\Mauro\Desktop\`
- **2026-03-27**: [ARTEFATO PENDENTE] Sistema de inteligência de conversas construído — 3 blueprints JSON + SQL + prompt, NÃO importados/ativados:
  - `n8n-workflows/vitalis-zapi-listener.json` — blueprint (não importado)
  - `n8n-workflows/vitalis-conversation-classifier.json` — blueprint (não importado)
  - `n8n-workflows/vitalis-intelligence-report.json` — blueprint (não importado)
  - `docs/stories/vitalis-supabase-setup.sql` — SQL não executado (tabelas vitalis_conversations + vitalis_sales inexistentes)
  - `squads/trafego-pago/vitalis-conversation-classifier-prompt.md` — [ARTEFATO] pronto

### ⏳ PENDENTE
- Enviar mensagem para João com análise e proposta de conectar WhatsApp na Z-API
- **Conectar número WhatsApp do João na Z-API (QR code)** — bloqueante para tudo abaixo
- **Executar SQL** `docs/stories/vitalis-supabase-setup.sql` no Supabase Dashboard (não foi possível via API — chave não tem acesso DDL via REST)
- **Configurar Client-Token Z-API**: No painel Z-API, ativar segurança "Client-Token" na instância e configurar o webhook URL: `https://n8n.sparkleai.tech/webhook/vitalis-zapi-listener-001`
- **Adicionar GROQ_API_KEY** nas variáveis de ambiente do n8n (console.groq.com, free tier suficiente)
- Importar os 3 workflows JSON no n8n e ativar após Z-API conectado
- Configurar rastreamento de vendas no Supabase + Conversions API Meta
- Analisar dados históricos por dia para recomendar distribuição de budget (dados já coletados, só falta análise)

---

## GABRIELA / Consórcio

### ✅ FEITO
- **2026-03-26/27**: Partner assignment configurado na BM nova — todos os assets (Ad Account, Instagram, Facebook Page, WhatsApp) compartilhados com sucesso. Gabriela testou criando campanha e conseguiu atribuir tudo

### ✅ FEITO
- **2026-03-27**: [ARTEFATO] Estrutura completa de campanha Meta Ads preparada (JSON-ready) — 3 campanhas, 6 ad sets, 6 criativos com copy, CTA WhatsApp e códigos de rastreio (GAB-IMV-01/02, GAB-VEI-01/02, GAB-RTG-01/02). Arquivo: `squads/trafego-pago/briefings/gabriela-campaign-structure.md`
- **2026-03-27**: Verificado via API — ad account da Gabriela NÃO está no token Sparkle (só Vitalis aparece). Bloqueio documentado.
- **2026-03-27**: HOUSING special ad category identificada como obrigatória para campanha de imóvel (limita segmentação idade/gênero)

### ⏳ PENDENTE
- **Vincular ad account da Gabriela ao token Meta Sparkle** — bloqueante para execução
- Validar interest IDs via API `/search` após vinculação
- Obter PAGE_ID, IG_ACCOUNT_ID e verificar se tem pixel
- Pedir para Gabriela: valor mínimo de parcela, número de clientes atendidos, imagens/vídeos para criativos
- Construir campanha real na BM nova (estrutura JSON pronta, só executar)
- Analisar R$35k de dados históricos da conta antiga
- Atualizar público salvo (desatualizado — Goiás/Brasília, interesses errados)

---

## FUN PERSONALIZE / Julia Gomes

### ⏳ PENDENTE (bloqueado)
- Setup Zenya Premium (Loja Integrada) — **bloqueado aguardando API key da Julia**
- Julia ainda não enviou a API key da Loja Integrada

---

## ENSINAJA / Douglas

### ✅ FEITO
- **2026-03-27**: [ARTEFATO] Knowledge base completo criado em `docs/zenya/clients/ensinaja/knowledge-base.md` — 12 cursos mapeados com conteúdo programático, valores confirmados (Barbearia R$1.329,30 promo, Retroescavadeira R$499,90 à vista), endereço: Rua Dr. Castro Santos, 250 — Campo do Galvão, Guaratinguetá/SP, Tel: (12) 2103-0458
- **2026-03-27**: [ARTEFATO PENDENTE] Workflows n8n clonados a partir do master — `01. Ensinaja - Secretária v3`, `05. Ensinaja - Escalar humano`, `07. Ensinaja - Quebrar e enviar mensagens`, `00. Ensinaja - Configurações` (todos INATIVOS — não funcionais até go-live)
- **2026-03-27**: Zenya Demo já conectada às contas @ensinajaguara e @ensinajalorena (confirmado via screenshot)

### ✅ FEITO
- **2026-03-27**: [FUNCIONAL] System prompt da Ensina Já configurado no workflow n8n `01. Ensinaja - Secretaria v3` (ID: `agEnqd5797ugaxEp`) via API PUT — prompt completo com fluxo de matrícula, regras, info da escola, cursos com/sem preço, tom de voz (3.596 chars)
- **2026-03-27**: [FUNCIONAL] KB populada no Supabase `zenya_knowledge_base` — 35 registros inseridos: 12 cursos, 14 info_escola, 9 faq. Script: `scripts/populate-kb-ensinaja.py`. client_id: `b1d89755-3314-4842-bb34-d33d95f0b6f4`

### ⏳ PENDENTE
- **Confirmar com Douglas**: valores dos 10 cursos sem preço, carga horária Barbearia e Retroescavadeira, horários de atendimento, se há unidade presencial em Lorena, se aluno pode fazer mais de um curso ao mesmo tempo — mensagem pronta gerada pelo Orion
- Substituir número do Douglas no node de escalar humano
- Criar planilha Google Sheets `ensina_leads` + configurar ID no workflow
- Atualizar KB no Supabase com valores reais após confirmação de Douglas
- Ativar workflows após configuração completa

---

## ALEXSANDRO / Confeitaria

### ✅ FEITO
- **2026-03-27**: [ARTEFATO] Knowledge base completo criado em `docs/zenya/clients/alexsandro-confeitaria/knowledge-base.md` — ~100 produtos com preços extraídos do Yooga (cardápio completo: doces vitrine, salgados, assados, bolos massa chocolate + branca, açaí, bebidas)
- **2026-03-27**: [ARTEFATO] System prompt da "Gê" criado em `docs/zenya/clients/alexsandro-confeitaria/system-prompt.md` — fluxo de encomenda, regras, tom definidos
- **2026-03-27**: [ARTEFATO PENDENTE] Workflows n8n clonados a partir do master — `01. Confeitaria Dona Geralda - Secretária v3`, `05. Confeitaria - Escalar humano`, `07. Confeitaria - Quebrar e enviar mensagens`, `00. Confeitaria - Configurações` (todos INATIVOS — não funcionais até go-live)
- **2026-03-27**: Número da confeitaria: +5511976908238 (número da loja, não do Alexsandro)

### ✅ FEITO
- **2026-03-29**: [FUNCIONAL] System prompt da "Gê" configurado no workflow n8n `01. Confeitaria Dona Geralda - Secretária v3` (ID: `u7BDmAvPE4Sm6NXd`) via API PUT — prompt completo com fluxo de encomenda, regras criticas, info da loja, tom de voz (3.926 chars)
- **2026-03-29**: Campos estáticos do Info node verificados — `cobranca_valor: 500` correto para contrato Alexsandro, campos dinâmicos extraem do webhook Chatwoot

### ✅ FEITO
- **2026-03-27**: [FUNCIONAL] Supabase KB populada — tabela `zenya_knowledge_base` com 193 registros da confeitaria (script `scripts/populate-kb-confeitaria.py` executado com sucesso)
- **2026-03-27**: [ARTEFATO] SQL schema criado — `docs/architecture/supabase-knowledge-base.sql` com tabela `zenya_knowledge_base` (universal para todas as Zenyas, FK clients, RLS service_role, índices por client_id + category)
- **2026-03-27**: [ARTEFATO] Script `scripts/populate-kb-confeitaria.py` criado — lê 7 CSVs (`doces-vitrine`, `salgados`, `assados`, `bolos-chocolate`, `bolos-branca`, `acai-bebidas`, `info-loja`), faz clean insert via Supabase REST API, sem dependência de Google Sheets ou service account. Suporta `--print-sql` para imprimir DDL.
- **2026-03-27**: [ARTEFATO PENDENTE] Chatwoot inbox confeitaria: NÃO criado — número +5511976908238 não está configurado. Bloqueado aguardando nova instância Z-API. API de criação de inbox confirmada funcional (POST /api/v1/accounts/1/inboxes + provider zapi).

### ⏳ PENDENTE
- Confirmar com Ariane: endereço completo, horários, formas de pagamento, entrega ou só retirada, bolos decorados/personalizados
- Organizar fotos dos produtos (Ariane mandou via WhatsApp com nomes dos doces) — Mauro vai montar pasta
- **BLOQUEANTE — Executar SQL no Supabase Dashboard**: Acessar https://supabase.com/dashboard/project/gqhdspayjtiijcqklbys/sql e executar `docs/architecture/supabase-knowledge-base.sql` para criar a tabela
- **Após criar tabela**: Rodar `python scripts/populate-kb-confeitaria.py` — esperado ~200 registros inseridos (bolos têm 2 preços: fatia + kg)
- **Chatwoot inbox confeitaria**: Criar nova instância Z-API para o número 5511976908238, obter token+instance_id, então POST /api/v1/accounts/1/inboxes com provider=zapi e credenciais novas
- **Substituir Google Sheets KB** no workflow n8n pela lógica de consulta Supabase `zenya_knowledge_base` (node Buscar_base_conhecimento)
- **id_conversa_alerta** no node Info — ainda com placeholder, precisa do ID real da conversa de alerta no Chatwoot (após criar inbox)
- Substituir número do Alexsandro no node de escalar humano
- Ativar workflows após configuração completa e QA

---

## INFRAESTRUTURA / Friday v1

### ✅ FEITO
- **2026-03-27**: [ARTEFATO] Friday v1 construída — 4 arquivos JSON/SQL/PY:
  - `docs/architecture/supabase-friday.sql` — SQL schema para tabela `friday_tasks` (NÃO executado ainda)
  - `scripts/friday-worker.py` — worker local Python (não implantado em produção)
  - `n8n-workflows/friday-brain.json` — blueprint do workflow (não é o workflow ativo)
  - `n8n-workflows/friday-task-notifier.json` — blueprint do notificador (não é o workflow ativo)

### ✅ FEITO
- **2026-03-29**: [FUNCIONAL] Workflow `sparkle-zapi-router.json` recriado e ATIVO no n8n (ID: `LMcmB2oYX5RGnFxc`) — ID anterior `dFbGUUmb6vxHTV8I` não existia mais (possivelmente deletado). Recriado via POST + ativado via API. versionId: `0c04bd24-38ff-48ef-a920-6360338c0d28`
  - Webhook: `POST /zapi-router` — responde 200 imediato, roteia em background
  - Mensagem recebida do Mauro (5512981303249) → Friday Brain + Chatwoot (paralelo)
  - Mensagem recebida de outros → Chatwoot direto
  - Eventos (status, presença, etc.) → Chatwoot direto
  - Tag: Compartilhado | Ativo: sim — **NOTA: não testado end-to-end (Z-API ainda aponta para Chatwoot direto)**
- **2026-03-28**: [FUNCIONAL] Friday Brain (ID: `Izoupz82zVf6kZRQ`) ativo no n8n — **NOTA: não testado e2e**
- **2026-03-28**: [FUNCIONAL] Friday Notifier (ID: `zxznYpW2PBhJrGjV`) ativo no n8n — **NOTA: não testado e2e**

### ✅ FEITO
- **2026-03-28**: [FUNCIONAL] Sparkle Gateway (ID: `hCukbZX875Y18ThZ`) atualizado via PUT API n8n — Friday v1 Sprint 1 completo no n8n:
  - **7 nodes → 16 nodes** (preservou webhook `zapi-router-002` e Chatwoot)
  - Nodes adicionados: Classificar Intencao (gpt-4o-mini), Parse Classificacao, Switch Tipo (4 branches), Executar Query (Supabase), Executar Acao (prospect/template/welcome), Inserir Task Build + Confirmar Build, Chat Friday + Parse Chat, Merge Respostas, Error Handler
  - Fluxo: Webhook → Chatwoot + Check Mauro → Is Mauro? → Classificar → Parse → Switch → QUERY/ACTION/BUILD/CHAT → Merge → Error Handler → Responder Mauro
  - QUERY: consulta v_mrr_summary, v_payments_overdue, v_client_health, v_billing_calendar, prospects
  - ACTION: cadastra prospect (Supabase), envia mensagem (Z-API), dispara welcome (webhook)
  - BUILD: INSERT friday_tasks + confirma "Enviei pro Orion"
  - CHAT: gpt-4o-mini persona Friday
  - Script: `tmp_friday_v1_put.py` (pode ser deletado)
  - **NOTA: views Supabase e tabela friday_tasks ainda não criadas — workflow quebrará em QUERY/BUILD até executar SQLs**

### ✅ FEITO
- **2026-03-29**: [FUNCIONAL] Supabase: `friday_tasks`, `v_mrr_summary`, `v_payments_overdue`, `v_client_health`, `v_billing_calendar` — CONFIRMADOS EXISTENTES via MCP
- **2026-03-29**: [FUNCIONAL] Supabase RLS audit executado — 8/8 blocos SQL aplicados via MCP. 25 políticas ativas. Fixes: vitalis_conversations/vitalis_sales (RLS sem políticas → corrigido), meta_insights/campaigns/reports/prospects (RLS adicionado, LGPD), friday_tasks (acesso anônimo removido), contracts (service_role adicionada). Relatório: `docs/reviews/supabase-rls-audit.md`
- **2026-03-29**: [FUNCIONAL] Weekly Report V2 criado no n8n (ID: `U68uGoBZsRxXSARL`) — 12 nodes, dual trigger (segunda 9h + webhook manual), 4 queries Supabase paralelas, envio WhatsApp para Mauro. AGUARDA ativação manual: https://n8n.sparkleai.tech/workflow/U68uGoBZsRxXSARL
- **2026-03-29**: [ARTEFATO] Script `scripts/clone-zenya-client.py` criado e validado por @qa — clona 4 workflows Zenya Prime (IDs: G0ormrjMIPrTEnVH, r3C1FMc6NIi6eCGI, ttMFxQ2UsIpW1HKt, 4GWd6qHwbJr3qLUP) para novo cliente via API n8n + popula 00.Configurações automaticamente. Uso: `python scripts/clone-zenya-client.py --nome "X" --slug "x" --telefone "55..." --id-supabase "uuid"`
- **2026-03-29**: [ARTEFATO] `docs/zenya/SOUL.md` v1.1 criado e validado — alma universal da Zenya, tabela universal vs. configurável, tags [HUMANO] e [LEAD] como padrão oficial, glossário Zenya/Secretária v3

### ✅ FEITO (sessão perdida na compactação — data exata desconhecida, antes de 2026-03-31)
- **[FUNCIONAL] Friday áudio E2E testado** — pipeline completo funcionando: áudio WhatsApp → Z-API → webhook → runtime → Groq Whisper transcreve → Claude responde → Z-API envia resposta
- **[FUNCIONAL] Friday responde em áudio** — TTS via ElevenLabs funcionando. Voz trocada para uma nova voz (ID exato desconhecido — ⚠️ verificar no painel ElevenLabs qual voz está ativa). Chave API ElevenLabs configurada no .env da VPS.
- **[FUNCIONAL] Z-API webhook** redirecionado para `https://runtime.sparkleai.tech/friday/webhook`
- **[FUNCIONAL] Runtime deploy** — runtime.sparkleai.tech online, systemd, Traefik/Coolify, todos checks verdes

### ⏳ PENDENTE
- **Weekly Report V2**: Mauro ativar manualmente no n8n UI: https://n8n.sparkleai.tech/workflow/U68uGoBZsRxXSARL
- **Identificar voz ElevenLabs ativa**: acessar painel ElevenLabs e registrar o ID da voz atual da Friday

---

## INFRAESTRUTURA / Onboarding Workflow

### ✅ FEITO
- **2026-03-27**: [ARTEFATO PENDENTE] Workflow `sparkle-onboard-client` criado no n8n via API POST (ID: `lmorPUMjAH4McOwG`) — 18 nodes, tag Compartilhado, INATIVO (ativar manualmente para registrar webhook)
  - Webhook POST `/onboard-client` → Validate Input → IF novo/existente → INSERT clients Supabase → INSERT payments Supabase
  - Branches paralelas: Welcome Message Z-API, Template Coleta Dados Z-API (por nicho), Clone Zenya Secretária v3 (se has_zenya=true)
  - Placeholders: Asaas Billing [TODO], Chatwoot Inbox [TODO]
  - Notifica Mauro via Z-API ao final com resumo do cliente
  - Script: `scripts/create-onboarding-workflow.py`
  - URL: https://n8n.sparkleai.tech/workflow/lmorPUMjAH4McOwG

### ⏳ PENDENTE
- **Ativar manualmente** o workflow no n8n para registrar o webhook (bug de webhook — não ativar via API)
- **Testar** com payload real: POST https://n8n.sparkleai.tech/webhook/onboard-client
- **Criar tabela `payments`** no Supabase (se não existir) — verificar schema
- **Integrar Asaas** (node placeholder) quando sair do sandbox — adicionar ASAAS_API_KEY nas vars do n8n
- **Integrar Chatwoot** (node placeholder) — endpoint POST /api/v1/accounts/{account_id}/inboxes

---

## INFRAESTRUTURA / Contract Generator

### ✅ FEITO
- **2026-03-29**: [FUNCIONAL] BUG-001 + BUG-002 corrigidos — `valorPorExtenso` agora algorítmica (aceita qualquer valor, formato BR), centralizada em `script.js` como `window.valorPorExtenso`, duplicação removida dos templates
- **2026-03-29**: [FUNCIONAL] Integração Autentique implementada e validada por @qa — `contract-generator/server.py` (proxy Flask local), botão "Enviar para Assinatura" no frontend. Uso: criar `.env` com `AUTENTIQUE_TOKEN`, `pip install -r requirements.txt`, `python server.py`. Token em: app.autentique.com.br → Configurações → API

### ⏳ PENDENTE
- Mauro obter `AUTENTIQUE_TOKEN` no painel da Autentique para testar integração

---

## INFRAESTRUTURA / Squads

### ✅ FEITO
- **2026-03-29**: 7 problemas corrigidos em 4 squads:
  - `sales-pipeline/lead-to-proposal.yaml` (C-01): input `proposal` condicional para leads HOT apenas
  - `sales-pipeline/weekly-pipeline-review.yaml` (C-02): agente correto (`sales-qualifier`) no step generate-report
  - `trafego-pago/squad.yaml`: metrics.north_star adicionado, Gabriela adicionada na lista de clientes
  - `trafego-pago/daily-sync.yaml`: query SQL corrigida (`meta_account_id IS NOT NULL`)
  - `client-success/weekly-health-cycle.yaml`: steps sem agente definido corrigidos
  - `content-factory/content-production-cycle.yaml`: loop infinito limitado a 3 iterações

---

## PLAKA / Roberta

### ✅ FEITO
- **2026-03-29**: [FUNCIONAL] Delta v3 implementado no workflow `371QcYGrXmZ1n8bV`:
  - Delta 1: node `Check Agente-Off Gate` adicionado (verifica label `agente-humano` no payload Chatwoot, retorna [] para pausar Zenya). Complementa gate existente `Verificar etiquetas em tempo real` (label `agente-off` via API).
  - Delta 2: `Buscar_base_conhecimento` já estava correto — aponta para WF-14 com Sheets `1owkGkYk59pMKjQoh0_y3JKWLCxB3MHBQ2VrOoQa6w4s`. 6 abas incluindo `Escalamento`.
  - Spec técnica: `docs/zenya/clients/plaka/delta-v3.md`
  - Aguarda QA e go-live (bloqueado: Luiza precisa liberar WhatsApp)

---

## VITALIS / João Lúcio

### ✅ FEITO
- **2026-03-29**: Análise de budget por dia da semana concluída — `docs/reviews/vitalis-budget-analysis.md`
  - Melhor CPL: Domingo R$7,64 / Quinta R$8,47 / Terça R$8,57
  - Pior CPL: Sábado R$9,69 (21% mais caro)
  - Melhor criativo: [VIDEO][VITALIS - final 8440] CPL R$5,82 (atualmente PAUSADO — verificar motivo)
  - ⚠️ ALERTA: Campanhas gastando R$2.160/mês — acima do contrato R$1.500. Confirmar com João.

### ⏳ PENDENTE
- Mauro confirmar com João sobre spending acima do contrato (R$2.160 vs R$1.500)
- Apresentar análise de budget ao João com recomendação de redistribuição
- Conectar WhatsApp do João na Z-API (QR code) para ativar inteligência de conversas

---

## CINARA / Nail Designer (PERDIDO)

### ❌ NÃO FECHOU
- **2026-03-26**: Proposta enviada — R$297-400/mês
- **2026-03-27**: Cinara achou caro, não vai contratar

---

## Sessão 2026-03-30 — @architect (Aria) + Orion

### FEITO

**Mega Brain / Sparkle Brain:**
- Lidos todos os 29 chunks da transcrição da live Mega Brain (Thiago Finch, 27/02/2026, ~6h)
- Criado `docs/strategy/content-pillar-megabrain-synthesis.md` — visão unificada Content Pillar + Mega Brain + AIOS v2 + decisões do Mauro
- Criado `docs/architecture/aios-v2/fase-0.5-megabrain-dev-brief.md` — dev brief técnico completo para Sparkle Brain (adaptação multi-tenant)
- Adicionado `mega-brain/` ao .gitignore

**Arquitetura AIOS v2:**
- `00-constitution.md` — Princípio 8 adicionado (Colaboração Proativa Dentro do Escopo), versão 1.1
- `06-implementation-roadmap.md` — Fase 0.5 inserida entre Fase 0 e Fase 1
- `02-data-schema.sql` — 4 bugs corrigidos: função update_updated_at_column() faltando, ARRAY[] sem cast, @pm e @ux com name=NULL, FK circular projects→project_templates. SQL executado com sucesso no Supabase.

**Toolkit e Processos:**
- `docs/operations/agent-toolkit-standard.md` — adicionados: roteamento Opus/Sonnet/Haiku/Groq por tipo de task + critério Use or Lose
- `docs/architecture/aios-v2/08-sector-processes.md` — adicionados processos PT-1 (Landing Page E2E), PT-2 (Planejamento de Iniciativa Grande), PT-3 (Onboarding Meta Ads)
- `AGENT_CONTEXT.md` — atualizado com Princípio 8, processos PT-1/PT-2/PT-3, lista completa de bootstraps, seção Sparkle Brain

**Bootstraps (8 novos):**
- `docs/operations/agent-bootstrap/architect.md` ✅
- `docs/operations/agent-bootstrap/devops.md` ✅
- `docs/operations/agent-bootstrap/po.md` ✅
- `docs/operations/agent-bootstrap/pm.md` (Morgan) ✅
- `docs/operations/agent-bootstrap/sm.md` ✅
- `docs/operations/agent-bootstrap/ux.md` (Uma) ✅
- `docs/operations/agent-bootstrap/data-engineer.md` ✅
- `docs/operations/agent-bootstrap/squad-creator.md` ✅

**Agent Queue:**
- ITEM-03 (Squads C-01/C-02) — validado FUNCIONAL
- ITEM-05 (Bootstrap files) — FUNCIONAL
- ITEM-06 (Sparkle Brain) — EM_EXECUCAO (@dev)
- ITEM-07 (AGENT_CONTEXT update) — FUNCIONAL
- Fase 0 concluída — SQL no Supabase executado com sucesso

### PENDENTE
- @dev: Sparkle Brain workflows n8n + schema brain_* (ITEM-06)
- @dev: Script Auto-Clonagem v3 (ITEM-01)
- @dev: Weekly Report V2 (ITEM-02)
- @qa: Contract Generator (ITEM-04)
- Fase 1: Task Dispatcher (desbloqueada após Sparkle Brain estável)
- BLOCKs 01-06: aguardando ações do Mauro (Z-API, Douglas, Julia, Gabriela, Vitalis)

---

## Sessão 2026-04-01 — Sprint 1 + Sprint 2 (continuação)

### ✅ FEITO

- **2026-04-01**: [FUNCIONAL] brain_query CONFIRMADO em produção — Mauro testou via WhatsApp, Brain retornou síntese real sobre Zenya. 96 registros na knowledge_base (84 carregados pelo @dev + 12 anteriores).
- **2026-04-01**: [FUNCIONAL] brain_ingest fix: `relevance: "high"` → `"alta"` (consistência PT-BR). Commit `3063c57`.
- **2026-04-01**: [FUNCIONAL] dispatcher.py: extração explícita de `content` para intent `brain_ingest` adicionada ao prompt _CLASSIFY_SYSTEM. Commit `3063c57`.
- **2026-04-01**: [ARTEFATO] S2-01 handler `loja_integrada_query` implementado e aprovado pelo @qa. Stateless, lê LOJA_INTEGRADA_API_KEY do env, aceita cpf/email/pedido_id, retorna últimos 3 pedidos. Commit `3063c57`.
- **2026-04-01**: [FUNCIONAL] S2-01 endpoint `GET /zenya/order` implementado no zenya router. Parâmetros: store, query (texto livre), pedido_id, cpf, email. _parse_query infere tipo automaticamente (email > CPF > ID pedido). Validação de store (fun_personalize/fun-personalize). Chama handle_loja_integrada_query de forma síncrona. Testado: retorna erro amigável sem API key, erro correto para store inválida, mensagem de orientação sem query. Commit `0cd456c` no VPS. AGUARDA: LOJA_INTEGRADA_API_KEY da Julia para ativar consulta real.
- **2026-04-01**: [CONFIRMADO] Cron jobs ARQ worker verificados no código: daily_briefing 11h UTC (8h Brasília), health_check a cada 15min. S3-01 aprovado.

### ⏳ PENDENTE

- **Deploy commit `3063c57` para VPS**: ✅ FEITO (2026-04-01 12:34 UTC)
- **brain_ingest E2E**: ✅ CONFIRMADO — Mauro testou, "Anotado! ✅" retornado, KB atualizado. S1-03 COMPLETO.
- **SQL S3-03 agents table**: ✅ FEITO — ALTER TABLE agents + índices executados no Supabase
- **Deploy commits `3063c57` + `ea6182a`**: ✅ FEITO — health ok, todos checks true
- **LOJA_INTEGRADA_API_KEY no VPS**: ⏳ PENDENTE — Julia não enviou ainda. Quando receber: `echo "LOJA_INTEGRADA_API_KEY=VALOR_AQUI" >> /opt/sparkle-runtime/sparkle-runtime/.env && systemctl restart sparkle-runtime`. Endpoint já pronto em GET /zenya/order.
- **Weekly Report V2**: ⏳ PENDENTE — Mauro ativar no n8n: https://n8n.sparkleai.tech/workflow/U68uGoBZsRxXSARL

### STATUS SPRINTS (2026-04-01)
- Sprint 1 (Brain Operacional): ✅ COMPLETO EM PRODUÇÃO
- Sprint 2 (Clientes Pendentes): 🔶 S2-01 código pronto, aguarda API key Julia. S2-02/S2-03 bloqueados por Mauro.
- Sprint 3 (Maturidade Runtime): ✅ COMPLETO EM PRODUÇÃO (crons, /agent/invoke, SQL)
- Sprint 4 (Inteligência): 🔜 PRÓXIMO

---

## Sessão 2026-04-01 — Sprint 8 P3 QA Fixes (@dev)

### ✅ FEITO

- **2026-04-01**: [FUNCIONAL] Fix #1 — BRAIN_SIMILARITY_THRESHOLD: 0.75 → 0.50 no .env da VPS. Threshold mais permissivo reduz falsos negativos no vector search. Confirmado: `grep BRAIN_SIMILARITY_THRESHOLD .env` = 0.50.
- **2026-04-01**: [FUNCIONAL] Fix #2 — POST /brain/search: novo módulo `runtime/brain/router.py` criado. Expõe endpoint HTTP direto para busca no Brain sem passar pelo task queue. Parâmetros: query, top_k, owner_type, client_id. Registrado em main.py (`app.include_router(brain_router)`). Smoke test: endpoint responde em https://runtime.sparkleai.tech/brain/search.
- **2026-04-01**: [FUNCIONAL] Fix #3 — ILIKE fallback: terceiro nível de busca adicionado em `_search_knowledge_base`. Fluxo completo: vector search → search_brain_text RPC → ILIKE direto em brain_chunks.canonical_content. Split por termos ≥ 3 chars, até 5 termos. Smoke test: ILIKE retornou 3 chunks para "MRR faturamento".
- **2026-04-01**: [ARTEFATO] Função pública `search_brain(query, top_k, owner_type, client_id)` adicionada ao brain_query.py para consumo pelo router HTTP.
- **2026-04-01**: [INFO] Alinhamento de nomes: RPC match_brain_chunks usa aliases canonical_text/narrative_text (preservados); ILIKE acessa canonical_content/insight_narrative (nomes reais da tabela); search_brain_text RPC retorna `content` (preservado).
- **2026-04-01**: [COMMIT] hash `040be5f` no repo VPS `/opt/sparkle-runtime/sparkle-runtime`. Push ao GitHub pendente (VPS não tem credencial GitHub SSH — infra preexistente).
- **2026-04-01**: [RUNTIME] sparkle-runtime UP — `active (running)` confirmado após restart.

### ⏳ PENDENTE

- **GitHub push**: VPS não tem SSH key para GitHub. Configurar `ssh-keygen` na VPS + adicionar deploy key no repo `mauromattos-lab/sparkle-aiox`, ou usar token HTTPS. Não bloqueia o runtime (código está na VPS).
- **@qa**: Re-validar os 3 fixes do S8-P3 em produção.
