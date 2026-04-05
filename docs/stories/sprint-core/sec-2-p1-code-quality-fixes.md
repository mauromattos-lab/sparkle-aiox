# SEC-2: P1 Code Quality Fixes — Brownfield Audit

**Sprint:** Core Quality
**Status:** PRONTO_PARA_DEV
**Pipeline:** Processo 3 (Correcao de Bug) — sparkle-os-processes.md
**Criado por:** @architect (Aria) — analise profunda dos 8 P1 do brownfield audit (2026-04-05)

---

## Contexto

Auditoria brownfield (2026-04-04) identificou 8 bugs P1 no sparkle-runtime. Apos analise profunda do codigo-fonte, **6 sao confirmados**, **1 e parcial** (ja tem mitigacao mas precisa de melhoria), e **1 nao existe** (o /health nao tem cron count hardcoded — bug reportado incorretamente).

### Resumo de Analise

| Bug | Confirmado? | Severidade Real | Complexidade |
|-----|-------------|-----------------|--------------|
| P1-1: billing.py blocking call | SIM | ALTA — bloqueia event loop | Trivial |
| P1-2: billing_alert task never executed | SIM | MEDIA — alert pode ficar pendente | Trivial |
| P1-3: _get_embedding deduplication | PARCIAL — dedup existe, mas _get_embedding duplicada em 3+ arquivos | MEDIA — custo OpenAI desnecessario | Moderada |
| P1-4: brain stats full table scan | SIM | ALTA — piora com crescimento do brain | Moderada |
| P1-5: CORS too permissive | SIM | MEDIA-ALTA — permite requests de qualquer origem | Trivial |
| P1-6: ARQ duplicate crons | SIM | MEDIA — crons duplicados entre APScheduler e ARQ | Moderada |
| P1-7: Hardcoded crons count | NAO EXISTE — /health nao reporta cron count | N/A | N/A |
| P1-8: Race conditions | SIM — confirm_existing_chunk/insight tem read-then-write race | MEDIA — confirmation_count pode perder incrementos | Moderada |

**Total: 6 bugs confirmados + 1 parcial = 7 fixes necessarios.**

---

## Batch A: Billing Fixes (P1-1, P1-2)

Ambos afetam o fluxo de cobranca em atraso. Devem ser corrigidos juntos.

---

### P1-1: billing.py send_text() bloqueia event loop (Severidade: ALTA)

**Arquivo:** `sparkle-runtime/runtime/tasks/handlers/billing.py` linhas 97-98
**Bug:** `handle_billing_alert` chama `send_text()` diretamente. `send_text()` em `runtime/integrations/zapi.py` usa `httpx.Client` sincrono (blocking). Dentro de um handler async chamado pelo event loop do FastAPI, isso bloqueia a thread principal.

**Evidencia:** `zapi.py` linha 39: `with httpx.Client(timeout=15) as client:` — sincrono, nao async.

**Impacto:** Enquanto a mensagem WhatsApp e enviada (ate 15s timeout), o event loop do FastAPI trava. Nenhuma outra request e processada. Em caso de timeout da Z-API, o runtime inteiro fica congelado por 15 segundos.

**Fix esperado:** Wrappear a chamada `send_text()` com `asyncio.to_thread()` como ja e feito em todos os outros locais que chamam funcoes sincronas do Supabase.

### Acceptance Criteria
- [ ] `send_text()` em `handle_billing_alert` e chamado via `await asyncio.to_thread(lambda: send_text(...))`
- [ ] Mesmo tratamento aplicado a qualquer outro local que chame `send_text()` diretamente de contexto async
- [ ] Timeout de 15s do httpx continua respeitado (nao alterar zapi.py neste fix)

---

### P1-2: billing_alert task criada mas nunca executada inline (Severidade: MEDIA)

**Arquivo:** `sparkle-runtime/runtime/billing/router.py` linhas 148-169
**Bug:** `_trigger_billing_alert()` insere a task `billing_alert` na tabela `runtime_tasks` com status `pending`, mas nao chama `execute_task()` inline. O scheduler (APScheduler) nao tem cron para processar tasks pendentes — ele agenda task types especificos. O ARQ worker (Redis) so roda se Redis esta disponivel.

**Evidencia:** Comparar com `_run_and_execute()` em `scheduler.py` (linhas 41-68) que faz insert + `execute_task()` inline. `_trigger_billing_alert()` so faz insert.

**Impacto:** Em modo dev (sem Redis), a billing_alert task fica pendente indefinidamente ate alguem chamar `POST /tasks/poll` manualmente. Em producao com ARQ, funciona porque `process_pending_tasks` roda a cada 15s — mas depende de Redis estar up.

**Fix esperado:** Chamar `execute_task()` inline apos o insert, como fazem todos os outros jobs do scheduler. Manter o insert no Supabase para auditoria.

### Acceptance Criteria
- [ ] `_trigger_billing_alert()` chama `execute_task(task)` apos insert bem-sucedido
- [ ] Task continua sendo inserida no Supabase antes da execucao (registro de auditoria)
- [ ] Se execute_task falhar, a task permanece como `pending` para retry via poll

---

## Batch B: Brain Fixes (P1-3, P1-4, P1-8)

Todos afetam o modulo Brain. Devem ser corrigidos juntos para evitar conflitos.

---

### P1-3: _get_embedding duplicada em multiplos arquivos (Severidade: MEDIA)

**Arquivos afetados:**
- `sparkle-runtime/runtime/tasks/handlers/brain_ingest.py` linhas 78-95
- `sparkle-runtime/runtime/brain/knowledge.py` linhas 23-38
- `sparkle-runtime/runtime/brain/ingest_url.py` (importada por brain_ingest_pipeline.py)
- `sparkle-runtime/runtime/tasks/worker.py` linhas 60-73 (inline, nao extrai para funcao)

**Bug:** A funcao `_get_embedding()` existe em pelo menos 3 arquivos com implementacoes quase identicas. Cada uma abre um `httpx.AsyncClient()` novo por chamada. Em requests concorrentes (ex: brain_ingest_pipeline processando 10 chunks), 10 conexoes HTTP separadas sao abertas para o mesmo endpoint OpenAI.

**Nota:** A dedup semantica (brain/dedup.py) ja existe e funciona corretamente — `check_duplicate_chunk()` e `confirm_existing_chunk()` fazem o trabalho. O problema nao e dedup ausente, e a funcao de embedding estar espalhada e sem connection pooling.

**Impacto:** Custo OpenAI inflado (conexoes redundantes), risco de rate limit em ingestoes pesadas, codigo duplicado dificulta manutencao (se trocar modelo, precisa trocar em 3+ lugares).

**Fix esperado:** Extrair `_get_embedding()` para um modulo unico (`runtime/brain/embedding.py`) e importar nos 4 locais. Opcionalmente, usar um `httpx.AsyncClient` compartilhado (singleton ou com connection pooling).

### Acceptance Criteria
- [x] Funcao `get_embedding(text: str) -> list[float] | None` existe em um unico modulo (`runtime/brain/embedding.py`)
- [x] `brain_ingest.py`, `knowledge.py`, `ingest_url.py` importam de `runtime.brain.embedding`
- [x] Worker `_fetch_brain_context()` tambem usa o modulo centralizado
- [x] Comportamento identico ao atual (mesma model, mesmo truncamento, mesmo fallback None)
- [x] Testes existentes (`test_brain_ingest_handler.py`) continuam passando

---

### P1-4: brain_namespace_stats() full table scan (Severidade: ALTA)

**Arquivo:** `sparkle-runtime/runtime/brain/metrics_router.py` linhas 98-103
**Bug:** `brain_namespace_stats()` faz `SELECT namespace, usage_count FROM brain_chunks` — busca TODAS as linhas da tabela para depois agregar em Python. Com o Brain crescendo (centenas de chunks agora, milhares em breve), isso se torna um gargalo de performance e memoria.

**Evidencia:** Linha 99-103: `supabase.table("brain_chunks").select("namespace, usage_count").execute()` — sem filtro, sem limite.

**Impacto:** Latencia crescente no endpoint `/brain/metrics/namespaces`. Com 10k chunks, a resposta vai levar segundos e consumir dezenas de MB de RAM. O comentario no codigo ja reconhece o problema: "Use raw SQL via RPC for aggregation / Fallback: fetch all and aggregate in Python (safer for Supabase client)".

**Fix esperado:** Criar uma RPC no Supabase (`brain_namespace_stats`) que faz o `GROUP BY namespace` com agregacao SQL nativa, e chamar via `supabase.rpc()`.

### Acceptance Criteria
- [x] Nova RPC `brain_namespace_stats` criada no Supabase (migration)
- [x] RPC retorna: namespace, chunk_count, total_usage, avg_usage via `GROUP BY`
- [x] Endpoint `/brain/metrics/namespaces` chama RPC ao inves de fetch all
- [x] Resposta identica ao formato atual (schema do JSON nao muda)
- [x] Fallback para o metodo Python caso RPC nao exista (deploy gradual)

---

### P1-8: Race condition em confirm_existing_chunk/insight (Severidade: MEDIA)

**Arquivo:** `sparkle-runtime/runtime/brain/dedup.py` linhas 88-128
**Bug:** `confirm_existing_chunk()` e `confirm_existing_insight()` fazem read-then-write: primeiro buscam o `confirmation_count` atual, depois fazem update com count+1. Se duas tasks concorrentes confirmam o mesmo chunk, ambas podem ler count=3, e ambas escrevem count=4 — perdendo um incremento.

**Evidencia:** Linhas 92-106 — `SELECT confirmation_count` seguido de `UPDATE confirmation_count = count + 1`. Sem transacao atomica.

**Impacto:** `confirmation_count` pode estar subcontado. Nao causa corrupcao de dados nem perda de chunks, mas metricas de confianca ficam imprecisas.

**Fix esperado:** Usar operacao atomica SQL. Duas opcoes:
  - (A) Criar RPC `increment_confirmation_count(p_table, p_id)` que faz `UPDATE SET confirmation_count = confirmation_count + 1`
  - (B) Usar SQL raw via RPC existente

**Opcao recomendada:** (A) — RPC dedicada. Mais seguro e reutilizavel.

### Acceptance Criteria
- [x] `confirm_existing_chunk()` usa operacao atomica (RPC ou SQL inline) sem read-then-write
- [x] `confirm_existing_insight()` usa mesma abordagem
- [x] Incremento nunca se perde em cenario concorrente
- [x] Se RPC for usada, migration inclui criacao da function

---

## Batch C: Infrastructure Fixes (P1-5, P1-6)

Afetam configuracao de servidor. Independentes dos batches anteriores.

---

### P1-5: CORS permite todas as origens (Severidade: MEDIA-ALTA)

**Arquivo:** `sparkle-runtime/main.py` linhas 39-44
**Bug:** `allow_origins=["*"]` permite qualquer website fazer requests ao runtime. Combinado com endpoints autenticados, isso significa que um site malicioso pode fazer requests autenticadas se o browser do usuario tiver cookies/headers ativos.

**Evidencia:** Linha 40: `allow_origins=["*"]`

**Nota:** O impacto real e mitigado pelo fato de a autenticacao usar API key no header (nao cookie), entao CSRF classico nao se aplica. Mas e ma pratica e expoe surface area desnecessaria.

**Fix esperado:** Restringir origins ao dominio do runtime + dominio do Mission Control. Permitir `*` apenas em modo dev (`RUNTIME_ENV=development`).

### Acceptance Criteria
- [x] CORS `allow_origins` configurado via env var `CORS_ALLOWED_ORIGINS` (comma-separated)
- [x] Default em producao: `["https://runtime.sparkleai.tech", "https://mission.sparkleai.tech"]`
- [x] Se `CORS_ALLOWED_ORIGINS=*` ou env var nao setada em dev, permite tudo (backwards compatible)
- [x] Adicionar `cors_allowed_origins` em `runtime/config.py`

---

### P1-6: ARQ cron_jobs duplicam o APScheduler (Severidade: MEDIA)

**Arquivo:** `sparkle-runtime/runtime/tasks/worker.py` linhas 471-483
**Bug:** `WorkerSettings.cron_jobs` define crons para `daily_briefing`, `weekly_briefing`, `gap_report`, `health_check`, `weekly_content`. O `scheduler.py` define os MESMOS jobs via APScheduler. Se o ARQ worker rodar junto com o FastAPI app, ambos disparam os mesmos jobs — duplicando tasks no Supabase.

**Evidencia:**
- `worker.py` L474: `cron(trigger_daily_briefing, hour={11}, minute={0})`
- `scheduler.py` L324-329: `_run_daily_briefing` com `CronTrigger(hour=8, minute=0, timezone=_TZ)`
- O scheduler.py `_run_and_execute()` (L41) cria + executa inline
- O worker.py `trigger_daily_briefing()` (L382) so cria (insert) — depende de `process_pending_tasks` para executar

**Impacto:** Mauro recebe briefing duplicado. Tasks duplicadas no Supabase gastam tokens LLM desnecessarios.

**Contexto adicional:** O docstring do scheduler.py diz "Fallback quando ARQ worker (Redis) nao esta disponivel". Isso sugere que a intencao e que apenas UM dos dois rode. Mas nao ha guarda que impeca ambos de rodar.

**Fix esperado:** Duas opcoes:
  - (A) Se Redis esta disponivel, scheduler.py nao registra os jobs que o ARQ ja cobre. Scheduler fica como fallback real.
  - (B) Remover os cron_jobs do ARQ WorkerSettings e usar apenas APScheduler (ja que o scheduler faz insert + execute inline, e mais confiavel).

**Opcao recomendada:** (B) — O APScheduler ja faz tudo que o ARQ cron faria, e de forma mais robusta (inline execution). Manter o ARQ worker apenas para `process_pending_tasks` (polling de tasks pendentes).

### Acceptance Criteria
- [x] Nao ha duplicacao de cron jobs entre APScheduler e ARQ
- [x] Se opcao B: `WorkerSettings.cron_jobs` contem apenas `process_pending_tasks`
- [ ] ~~Se opcao A: scheduler.py checa `REDIS_URL` e pula jobs que o ARQ ja cobre~~ (N/A — opcao B escolhida)
- [x] Funcoes `trigger_daily_briefing`, `trigger_weekly_briefing`, etc. podem ser removidas ou marcadas deprecated
- [x] Jobs registrados logados no startup para auditoria (scheduler.py ja faz isso — manter)

---

## Bug P1-7: Hardcoded crons count — NAO CONFIRMADO

**Analise:** O endpoint `/health` em `main.py` (linhas 98-115) nao reporta nenhum cron count. Nao ha campo `crons_scheduled`, `job_count` ou similar. O scheduler.py loga `{len(jobs)} jobs` no startup mas isso nao e exposto no /health.

**Conclusao:** Este bug nao existe no codigo atual. Possivelmente foi reportado baseado em uma versao anterior ou confusao com o log de startup. **Nenhum fix necessario.**

---

## File List

| Arquivo | Mudanca |
|---------|---------|
| `sparkle-runtime/runtime/tasks/handlers/billing.py` | asyncio.to_thread para send_text (P1-1) |
| `sparkle-runtime/runtime/billing/router.py` | execute_task inline em _trigger_billing_alert (P1-2) |
| `sparkle-runtime/runtime/brain/embedding.py` | **NOVO** — modulo centralizado de embedding (P1-3) |
| `sparkle-runtime/runtime/brain/knowledge.py` | Import de embedding.py (P1-3) |
| `sparkle-runtime/runtime/tasks/handlers/brain_ingest.py` | Import de embedding.py (P1-3) |
| `sparkle-runtime/runtime/brain/ingest_url.py` | Import de embedding.py (P1-3) |
| `sparkle-runtime/runtime/tasks/worker.py` | Import de embedding.py + limpar ARQ crons (P1-3, P1-6) |
| `sparkle-runtime/runtime/brain/metrics_router.py` | Usar RPC para namespace stats (P1-4) |
| `sparkle-runtime/runtime/brain/dedup.py` | Increment atomico (P1-8) |
| `sparkle-runtime/main.py` | CORS configuravel (P1-5) |
| `sparkle-runtime/runtime/config.py` | cors_allowed_origins (P1-5) |
| **Supabase migrations** | RPC brain_namespace_stats (P1-4), RPC increment_confirmation (P1-8) |

---

## Dependencias entre Fixes

```
P1-3 (embedding centralizado) → deve ser feito ANTES de P1-8 (dedup usa embedding)
P1-1 e P1-2 → independentes, podem ser feitos em paralelo
P1-4 e P1-8 → independentes entre si, mas ambos precisam de migrations Supabase
P1-5 e P1-6 → independentes de tudo
```

**Ordem recomendada de implementacao:**
1. Batch C (P1-5, P1-6) — zero dependencias, risco baixo
2. Batch A (P1-1, P1-2) — fixes triviais, impacto imediato
3. Batch B (P1-3, P1-4, P1-8) — requer migrations, mais complexo

---

## Pipeline AIOS

1. **@architect (Aria)** — Spec aprovada (esta story)
2. **@dev** — Implementar os 7 fixes seguindo os acceptance criteria, na ordem de batches
3. **@qa** — Validar cada fix:
   - P1-1: confirmar que billing alert nao bloqueia (testar com Z-API timeout simulado)
   - P1-2: confirmar que billing_alert executa inline (sem depender de poll)
   - P1-3: confirmar imports centralizados, testes existentes passam
   - P1-4: confirmar que /brain/metrics/namespaces retorna mesmo schema com RPC
   - P1-5: confirmar CORS restrito em prod, permissivo em dev
   - P1-6: confirmar que nao ha crons duplicados no startup log
   - P1-8: confirmar increment atomico (teste de concorrencia se possivel)
4. **@devops** — Deploy em producao + health check + verificar logs de cron
