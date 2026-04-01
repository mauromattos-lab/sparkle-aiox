# Sparkle Runtime — Estado de Implementação
_Atualizado: 2026-04-01 (S4-02 gap_report). Fonte de verdade para @dev, @qa, @devops e Orion._
_REGRA: atualizar este arquivo a cada handler criado, intent adicionado ou schema alterado._

---

## Endpoints HTTP (FastAPI)

### Raiz (`main.py`)
| Método | Path | O que faz |
|--------|------|-----------|
| GET | `/health` | Verifica Supabase, Z-API, Groq e Anthropic. Retorna `ok` ou `degraded`. |
| POST | `/debug/webhook` | Imprime payload recebido no log — utilitário de debug Z-API. |

### Friday (`/friday` — `runtime/friday/router.py`)
| Método | Path | O que faz |
|--------|------|-----------|
| POST | `/friday/message` | Recebe texto plano, classifica intent, executa task, retorna resposta síncrona. |
| POST | `/friday/audio` | Recebe arquivo de áudio (multipart OGG/MP3/WAV), transcreve via Groq Whisper, processa intent. |
| POST | `/friday/audio-url` | Recebe JSON `{audio_url, from_number}`, transcreve via URL, processa intent. |
| POST | `/friday/onboard` | Onboarding autônomo de cliente Zenya. Payload: `OnboardRequest`. Timeout 120s. |
| POST | `/friday/webhook` | Webhook Z-API. Detecta texto ou áudio, processa em background, responde 200 imediatamente. Após cada mensagem, Observer Pattern verifica se conversa atingiu múltiplo de 10 mensagens e enfileira `conversation_summary` automaticamente. |

### Zenya (`/zenya` — `runtime/zenya/router.py`)
| Método | Path | O que faz |
|--------|------|-----------|
| POST | `/zenya/learn` | Recebe notificação do n8n ao encerrar conversa Zenya. Payload: `{phone, client_id, client_name, conversation_text}`. Enfileira task `learn_from_conversation` em background. Responde 200 imediatamente. |

### Tasks (`/tasks` — `runtime/tasks/worker.py`)
| Método | Path | O que faz |
|--------|------|-----------|
| POST | `/tasks/poll` | Pega a task pendente de maior prioridade e executa. Fallback sem Redis. |

### Agents (`/agent` — `runtime/agents/router.py`) — S3-03
| Método | Path | O que faz |
|--------|------|-----------|
| POST | `/agent/invoke` | Invoca qualquer agente registrado na tabela `agents` pelo `agent_id`. Busca `system_prompt`, `model`, `max_tokens` no Supabase e chama `call_claude()`. Stateless, multi-tenant. Retorna `{response, agent_id, model}`. 404 se agente inexistente ou inativo. |

---

## Intents Registrados (Friday Dispatcher)

Classificação feita por `claude-haiku-4-5-20251001`. Resultado inserido em `runtime_tasks`.

| Intent | Exemplos de trigger | Params extraídos | Handler mapeado |
|--------|---------------------|------------------|-----------------|
| `status_report` | "como estão os agentes?", "status", "agentes" | — | `handle_status_report` |
| `status_mrr` | "qual o MRR?", "faturamento", "quanto tô faturando" | — | `handle_status_mrr` |
| `chat` | conversa livre, saudações, perguntas, fallback | — | `handle_chat` |
| `create_note` | "anota X", "lembra que Y", "registra Z", "salva isso" | — | `handle_create_note` |
| `activate_agent` | "ativa o @dev pra fazer X", "chama o arquiteto" | `agent`, `request` (via heurística) | `handle_activate_agent` |
| `weekly_briefing` | "resumo da semana", "o que rolou essa semana" | — | `handle_weekly_briefing` |
| `onboard_client` | "onborda [nome] site:[url] tipo:[tipo]" | `business_name`, `site_url`, `business_type`, `phone` | `handle_onboard_client` |
| `brain_query` | "brain, o que você sabe sobre X?", "consulta o brain" | `query` | `handle_brain_query` |
| `brain_ingest` | "brain, aprende isso: X", "ensina o brain" | `content` | `handle_brain_ingest` |
| `loja_integrada_query` | "consulta pedido", "status do pedido", "meu pedido", "rastrear pedido", "onde está meu pedido" | `cpf`, `email` ou `pedido_id` (ao menos um) | `handle_loja_integrada_query` |
| `gap_report` | "gaps do brain", "o que o brain não sabe", "relatório de gaps", "lacunas do brain" | — | `handle_gap_report` |
| `echo` | texto contendo "echo" | — | `handle_echo` |
| `task_free` | fallback de chat sem intent | — | `handle_chat` (alias) |

**Nota:** qualquer intent não reconhecido cai em `chat`.

---

## Handlers Implementados

| task_type | Handler | Arquivo | O que faz | Status |
|-----------|---------|---------|-----------|--------|
| `activate_agent` | `handle_activate_agent` | `handlers/activate_agent.py` | Registra solicitação de ativação de agente AIOS em `runtime_tasks` com task_type `agent_request`. NÃO executa o agente de verdade — apenas enfileira. | FUNCIONAL |
| `brain_ingest` | `handle_brain_ingest` | `handlers/brain_ingest.py` | Salva conteúdo na tabela `knowledge_base` com source `friday_ingest`. Remove prefixos de comando do texto. | FUNCIONAL |
| `brain_query` | `handle_brain_query` | `handlers/brain_query.py` | Busca na `knowledge_base` via vector search (pgvector RPC `match_brain_chunks`) com fallback para full-text search. Sintetiza com `claude-haiku-4-5-20251001`. Tenta embedding via OpenAI se `OPENAI_API_KEY` disponível. | FUNCIONAL |
| `chat` | `handle_chat` | `handlers/chat.py` | Conversa livre com persona Friday. Usa `claude-sonnet-4-6`. Injeta datetime de Brasília + histórico de 5 mensagens de `conversation_history` por número. Salva par user/assistant no histórico. | FUNCIONAL |
| `conversation_summary` | `handle_conversation_summary` | `handlers/conversation_summary.py` | Busca histórico de um número em `conversation_history` e cria task `learn_from_conversation`. Acionado manualmente ou por health_alert. | FUNCIONAL |
| `create_note` | `handle_create_note` | `handlers/create_note.py` | Limpa prefixos de comando e insere nota em `notes`. Gracioso: avisa Mauro se a tabela não existir, sem crashar. | FUNCIONAL |
| `daily_briefing` | `handle_daily_briefing` | `handlers/daily_briefing.py` | Monta relatório das últimas 24h (tasks, conversas, notas, MRR) e envia via WhatsApp para `MAURO_WHATSAPP`. | FUNCIONAL |
| `echo` | `handle_echo` | `handlers/echo.py` | Retorna o payload exato recebido. Usado para validar o pipeline end-to-end. | FUNCIONAL |
| `health_alert` | `handle_health_alert` | `handlers/health_alert.py` | Verifica 3 condições: agentes sem heartbeat >30min, tasks travadas em `running` >10min, >5 falhas na última hora. Envia alerta WhatsApp se qualquer check falhar. Silêncio = saudável. | FUNCIONAL |
| `learn_from_conversation` | `handle_learn_from_conversation` | `handlers/learn_from_conversation.py` | Analisa conversa concluída com `claude-haiku-4-5-20251001` e insere insights relevantes (alta/média) na `knowledge_base`. Filtra baixa relevância. | FUNCIONAL |
| `loja_integrada_query` | `handle_loja_integrada_query` | `handlers/loja_integrada_query.py` | Consulta pedidos na API Loja Integrada por CPF, e-mail ou ID do pedido. Auth via `LOJA_INTEGRADA_API_KEY` (header `Authorization: chave_api {key}`). Retorna últimos 3 pedidos com número, status, data, total e itens. Stateless — sem persistência em Supabase. Usado pela Zenya da Fun Personalize. | FUNCIONAL |
| `onboard_client` | `handle_onboard_client` | `handlers/onboard_client.py` | Pipeline: scrape site (httpx) → geração KB+system_prompt com `claude-sonnet-4-6` → upsert em `clients` → insert em `zenya_knowledge_base` → clone de 4 workflows n8n (se `N8N_API_KEY` disponível) → salva system_prompt em `notes`. | FUNCIONAL |
| `status_mrr` | `handle_status_mrr` | `handlers/status_mrr.py` | Tenta buscar dados de `clients` (status=active) ou `services` (active=True). Fallback para lista hardcoded com 6 clientes (R$4.594/mês). | FUNCIONAL |
| `status_report` | `handle_status_report` | `handlers/status_report.py` | Busca agentes em `agents`, últimas 10 tasks em `runtime_tasks`, custo de API do dia em `llm_cost_log`. | FUNCIONAL |
| `weekly_briefing` | `handle_weekly_briefing` | `handlers/weekly_briefing.py` | Relatório dos últimos 7 dias: MRR, tasks por tipo/status, notas, conversas. Gera frase de encerramento com `claude-haiku-4-5-20251001`. Envia via WhatsApp. | FUNCIONAL |
| `gap_report` | `handle_gap_report` | `handlers/gap_report.py` | Relatório semanal de gaps do Brain: busca queries `brain_query` sem resposta + registros `conversation_learning` da última semana. Analisa padrões com `claude-haiku-4-5-20251001` e gera top 5 gaps priorizados. Envia via WhatsApp. Cron: segunda-feira 08h Brasília. | FUNCIONAL |
| `task_free` | `handle_chat` (alias) | `handlers/chat.py` | Alias de `chat` — conversa livre sem intent estruturado. | FUNCIONAL |

---

## Cron Jobs

### ARQ Worker (`runtime/tasks/worker.py` — `WorkerSettings`)
Modo produção. Requer Redis (`REDIS_URL`).

| Job | Horário | O que dispara |
|-----|---------|---------------|
| `process_pending_tasks` | A cada 15 segundos (`second={0,15,30,45}`) | Busca até 20 tasks `pending` e executa em paralelo |
| `trigger_daily_briefing` | `11:00 UTC` (08:00 Brasília) | Insere task `daily_briefing` na fila |
| `trigger_weekly_briefing` | Domingo `11:00 UTC` (08:00 Brasília) (`weekday={6}`) | Insere task `weekly_briefing` na fila |
| `trigger_gap_report` | Segunda-feira `11:00 UTC` (08:00 Brasília) (`weekday={0}`) | Insere task `gap_report` na fila |
| `trigger_health_check` | `second=0` a cada 15 min (`minute={0,15,30,45}`) | Insere task `health_alert` na fila |

### APScheduler (`runtime/scheduler.py`)
Modo fallback (in-process, sem Redis). Acionado no startup do FastAPI via `lifespan`.

| Job | Horário | O que dispara |
|-----|---------|---------------|
| `health_check` | A cada 15 minutos (`IntervalTrigger`) | Cria e executa task `health_alert` inline |
| `daily_briefing` | `08:00 Brasília` (`CronTrigger`) | Cria e executa task `daily_briefing` inline |
| `weekly_briefing` | Domingo `08:00 Brasília` (`CronTrigger`, `day_of_week="sun"`) | Cria e executa task `weekly_briefing` inline |
| `gap_report` | Segunda-feira `08:00 Brasília` (`CronTrigger`, `day_of_week="mon"`) | Cria e executa task `gap_report` inline |

---

## Observer Pattern — Aprendizado Automático de Conversas (S4-01)

### Friday (conversas Mauro)
- Trigger: após cada mensagem processada em `_process_text()` e `_process_audio_url()` no webhook `/friday/webhook`
- Condição: conversa do `from_number` atingiu múltiplo de 10 mensagens em `conversation_history`
- Ação: enfileira task `conversation_summary` (priority 2, client `sparkle-internal`)
- Implementação: `asyncio.create_task(_maybe_trigger_learning(from_number))` — não bloqueia resposta ao usuário
- Frequência: a cada 10 mensagens acumuladas (10, 20, 30...) — evita flood

### Zenya (conversas clientes — via n8n)
- Trigger: n8n envia `POST /zenya/learn` ao encerrar atendimento
- Condição: n8n decide quando a conversa encerrou (inatividade, encerramento manual, etc.)
- Ação: enfileira task `learn_from_conversation` diretamente (sem passar por `conversation_summary`)
- Payload n8n: `{"phone": "55...", "client_id": "uuid", "client_name": "Plaka", "conversation_text": "..."}`
- Formato aceito no `conversation_text`:
  - `Cliente: msg\nZenya: resposta` (padrão n8n)
  - `user: msg\nassistant: resposta` (padrão Runtime)
- Arquivo: `runtime/zenya/router.py`

---

## Utilitários de Suporte

### Transcription (`runtime/friday/transcriber.py`)
- Provider: **Groq Whisper** (`whisper-large-v3-turbo`)
- Idioma fixo: `pt` (português)
- Aceita: OGG, MP3, MP4, WAV, M4A
- Dois entry points: `transcribe_bytes()` (upload multipart) e `transcribe_url()` (download por URL)

### TTS (`runtime/utils/tts.py`)
- Provider primário: **ElevenLabs** (`eleven_multilingual_v2`, voice ID `21m00Tcm4TlvDq8ikWAM` — Rachel)
- Fallback: **gTTS** (Google Text-to-Speech)
- Upload para Supabase Storage, bucket `friday-audio` (público)
- Retorna URL pública para `send_audio()` Z-API
- Ativado quando Mauro envia áudio → Friday responde em áudio

### Context Hydrator (`runtime/tasks/hydrator.py`)
- Rodado entre `classify_and_dispatch()` e `execute_task()` em todos os endpoints Friday
- Injeta sempre: `current_datetime` (Brasília)
- Injeta em `chat`/`task_free`: `conversation_history` (últimas 5 msgs por número)
- Injeta em `status_report`, `status_mrr`, `weekly_briefing`, `daily_briefing`: `clients_snapshot`

### Z-API Integration (`runtime/integrations/zapi.py`)
- `send_text(phone, message)` — envia texto
- `send_audio(phone, audio_url)` — envia áudio por URL
- `send_reaction(phone, message_id, reaction)` — reage a mensagem
- `get_status()` — verifica se instância está conectada (usado pelo `/health`)

---

## Schema das Tabelas Relevantes

Colunas derivadas exclusivamente dos selects/inserts encontrados no código.

### `runtime_tasks`
| Coluna | Tipo inferido | Observação |
|--------|---------------|------------|
| `id` | UUID | PK |
| `agent_id` | text | ex: "friday", "orion" |
| `client_id` | text | ex: "sparkle-internal" |
| `task_type` | text | intent string do registry |
| `payload` | jsonb | dados da task |
| `status` | text | `pending`, `running`, `done`, `failed` |
| `priority` | int | maior = mais prioritário |
| `result` | jsonb | output do handler |
| `error` | text | mensagem de erro se falhou |
| `retry_count` | int | tentativas já realizadas |
| `max_retries` | int | limite de retries (padrão 3) |
| `started_at` | timestamptz | quando executou |
| `completed_at` | timestamptz | quando terminou |
| `created_at` | timestamptz | inserção |
| `updated_at` | timestamptz | última atualização |

### `conversation_history`
| Coluna | Tipo inferido | Observação |
|--------|---------------|------------|
| `phone` | text | número do remetente |
| `role` | text | `user` ou `assistant` |
| `content` | text | conteúdo da mensagem |
| `created_at` | timestamptz | timestamp com offset para evitar colisão |

### `notes`
| Coluna | Tipo inferido | Observação |
|--------|---------------|------------|
| `client_id` | text | |
| `agent_id` | text | |
| `task_id` | UUID | referência à task origem |
| `content` | text | conteúdo completo |
| `summary` | text | resumo ou primeiros 200 chars |
| `created_at` | timestamptz | |

### `knowledge_base`
| Coluna | Tipo inferido | Observação |
|--------|---------------|------------|
| `id` | UUID | PK |
| `client_id` | text | |
| `type` | text | `produto`, `faq`, `preferencia`, `horario`, etc. |
| `content` | text | conteúdo do conhecimento |
| `source` | text | ex: `friday_ingest`, `conversation_learning`, `auto_onboarding` |
| `conversation_id` | text | ID da conversa de origem |
| `relevance` | text | `alta`, `media`, `baixa` |
| `created_at` | timestamptz | |

### `zenya_knowledge_base`
| Coluna | Tipo inferido | Observação |
|--------|---------------|------------|
| `client_id` | text | UUID do cliente onboardado |
| `category` | text | `produto`, `servico`, `preco`, `localizacao`, `horario`, etc. |
| `question` | text | |
| `answer` | text | |
| `tags` | array | lista de strings |
| `source` | text | `auto_onboarding` quando gerado via handler |
| `created_at` | timestamptz | |

### `clients`
| Coluna | Tipo inferido | Observação |
|--------|---------------|------------|
| `id` | UUID | PK |
| `name` | text | |
| `slug` | text | gerado a partir do nome |
| `type` | text | tipo do negócio |
| `phone` | text | |
| `status` | text | `active`, `onboarding` |
| `mrr` | numeric | valor mensal |
| `created_at` | timestamptz | |

### `agents`
| Coluna | Tipo inferido | Observação |
|--------|---------------|------------|
| `agent_id` | text | PK/identificador |
| `status` | text | `idle`, `running`, `error` |
| `last_heartbeat` | timestamptz | usado pelo health_alert |
| `name` | text | Nome legível do agente (ex: "Zenya - Ensinaja") — S3-03 |
| `system_prompt` | text | Prompt de sistema completo. Nullable (agentes internos definem no código) — S3-03 |
| `model` | text | ID do modelo Claude. DEFAULT `claude-haiku-4-5-20251001` — S3-03 |
| `max_tokens` | integer | Limite de tokens de saída. DEFAULT 1024 — S3-03 |
| `client_id` | text | FK lógica para `clients`. Nullable (agentes internos) — S3-03 |
| `tools` | jsonb | Array de strings com nomes de tools disponíveis. DEFAULT `[]` — S3-03 |
| `active` | boolean | false = desativado, não pode ser invocado via /agent/invoke. DEFAULT true — S3-03 |
| `created_at` | timestamptz | Timestamp de criação. DEFAULT now() — S3-03 |

**ATENÇÃO:** Colunas S3-03 requerem execução manual do SQL do `docs/S3-03-agent-invoke-spec.md` no Supabase (SQL Editor). SQL não foi aplicado automaticamente.

### `llm_cost_log`
| Coluna | Tipo inferido | Observação |
|--------|---------------|------------|
| `client_id` | text | |
| `task_id` | UUID | referência à task origem |
| `agent_id` | text | |
| `model` | text | ID do modelo Claude usado |
| `input_tokens` | int | |
| `output_tokens` | int | |
| `cost_usd` | float | calculado localmente antes de inserir |
| `purpose` | text | ex: `friday_chat`, `brain_query` |

---

## Modelos Claude em Uso

| Modelo | Onde é usado | Propósito |
|--------|-------------|-----------|
| `claude-haiku-4-5-20251001` | `dispatcher.py` | Classificação de intent (barato + rápido) |
| `claude-haiku-4-5-20251001` | `brain_query.py` | Síntese de resultados do Brain |
| `claude-haiku-4-5-20251001` | `learn_from_conversation.py` | Extração de insights de conversas |
| `claude-haiku-4-5-20251001` | `weekly_briefing.py` | Frase de encerramento do briefing semanal |
| `claude-sonnet-4-6` | `chat.py` | Conversa Friday (modelo padrão para qualidade) |
| `claude-sonnet-4-6` | `onboard_client.py` | Geração de KB + system prompt do cliente |

**Default em `llm.py`:** `claude-haiku-4-5-20251001`

Tabela de pricing registrada em `llm.py` (USD/1M tokens):
| Modelo | Input | Output |
|--------|-------|--------|
| `claude-haiku-4-5-20251001` | $0.25 | $1.25 |
| `claude-3-5-haiku-20241022` | $0.80 | $4.00 |
| `claude-sonnet-4-5` | $3.00 | $15.00 |
| `claude-sonnet-4-6` | $3.00 | $15.00 |
| `claude-opus-4-5` | $15.00 | $75.00 |

---

## Variáveis de Ambiente Necessárias

Definidas em `runtime/config.py` via `pydantic_settings`. Lidas de `.env` ou do ambiente.

| Variável | Obrigatória | Usada em | Observação |
|----------|-------------|----------|------------|
| `SUPABASE_URL` | Sim | `db.py` | URL do projeto Supabase |
| `SUPABASE_KEY` | Sim | `db.py` | Service role key |
| `ANTHROPIC_API_KEY` | Sim | `utils/llm.py` | Sem isso nenhum handler funciona |
| `GROQ_API_KEY` | Sim | `friday/transcriber.py` | Whisper transcrição de áudio |
| `ZAPI_BASE_URL` | Sim | `integrations/zapi.py` | Base URL da instância Z-API |
| `ZAPI_INSTANCE_ID` | Sim | `integrations/zapi.py` | ID da instância |
| `ZAPI_TOKEN` | Sim | `integrations/zapi.py` | Token da instância |
| `ZAPI_CLIENT_TOKEN` | Sim | `integrations/zapi.py` | Header `client-token` |
| `MAURO_WHATSAPP` | Sim (alertas) | `daily_briefing.py`, `health_alert.py`, `weekly_briefing.py`, `gap_report.py` | Número para envio de alertas e briefings |
| `ELEVENLABS_API_KEY` | Não | `utils/tts.py` | TTS primário. Sem ele, usa gTTS como fallback |
| `REDIS_URL` | Não | `tasks/worker.py` | ARQ worker. Default: `redis://localhost:6379`. Sem Redis, usar `/tasks/poll` |
| `N8N_API_KEY` | Não | `handlers/onboard_client.py` | Clone de workflows Zenya. Sem ele, etapa é pulada |
| `OPENAI_API_KEY` | Não | `handlers/brain_query.py` | Embeddings para vector search. Sem ele, usa full-text search como fallback |
| `LOJA_INTEGRADA_API_KEY` | Não* | `handlers/loja_integrada_query.py` | API key da Fun Personalize (Loja Integrada). Sem ela, handler retorna erro amigável. *Obrigatória para Fun Personalize funcionar. |

**Interno (não env):**
- `sparkle_internal_client_id` = `"sparkle-internal"` (hardcoded no config)
- `runtime_version` = `"0.1.0"`
- N8N host hardcoded em `onboard_client.py`: `https://n8n.sparkleai.tech/api/v1`

---

## Estado de Deploy

### O que está no código (confirmado pela leitura)
- Runtime completo em `sparkle-runtime/` — FastAPI + todos os handlers
- 15 task types registrados no REGISTRY + alias `task_free`
- Scheduler APScheduler (in-process) como fallback para ARQ
- ARQ worker configurado como modo produção (requer Redis)
- Onboarding autônomo implementado (Sprint 8) — inclui clone n8n

### O que o código indica como pendente / não-executável agora
- `activate_agent`: registra solicitação mas **não executa o agente** — lifecycle management pendente ("Sprint futuro" conforme comentário no handler)
- `N8N_API_KEY`: não configurado na infra (conforme `memory/MEMORY.md`) — clone de workflows será pulado
- Busca vetorial (`brain_query`): requer `OPENAI_API_KEY` para embeddings + RPC `match_brain_chunks` no Supabase com pgvector — fallback para full-text já implementado
- RPC `get_agents_stale_heartbeat` no Supabase: usada por `health_alert`, mas fallback direto à tabela `agents` já implementado

### Deploy na VPS
O código fonte está local. O estado de deploy na VPS (Hostinger KVM2 + Coolify) deve ser consultado em `memory/infra_stack.md` — não é possível inferir do código qual versão está rodando em produção.
