# Runbook de Incidentes — Sparkle AIOX

**Agente:** @devops (Gage)
**Versao:** 2.0
**Data:** 2026-04-04
**Ultima revisao:** 2026-04-04

> **Como usar este runbook:** Quando um incidente ocorrer, va direto para o cenario correspondente. Cada cenario tem 4 blocos: Sintomas, Diagnostico, Resolucao, Prevencao. Siga a sequencia. Nao improvise.

---

## Indice de Cenarios

| # | Cenario | Impacto | Tempo Estimado |
|---|---------|---------|----------------|
| 1 | [Runtime Down](#1-runtime-down) | CRITICO — API inteira fora, Friday nao processa, Brain para | 5-15 min |
| 2 | [Supabase Lento/Fora](#2-supabase-lentofora) | ALTO — queries timeout, Brain/State falham | 5-20 min |
| 3 | [Z-API Desconectou](#3-z-api-desconectou) | CRITICO — WhatsApp nao envia/recebe, Zenya para | 5-15 min |
| 4 | [Deploy Falhou](#4-deploy-falhou) | MEDIO — codigo novo nao entrou, sistema rodando versao anterior | 10-20 min |
| 5 | [Portal Nao Carrega](#5-portal-nao-carrega) | MEDIO — dashboard Mission Control inacessivel | 10-20 min |
| 6 | [ARQ Worker Parou](#6-arq-worker-parou) | ALTO — tarefas async nao processam (ingestao, insights, crons) | 5-15 min |
| 7 | [Brain Quality Degradation](#7-brain-quality-degradation) | MEDIO — dados duplicados ou mal classificados no brain_chunks | 15-30 min |

---

## Informacoes de Acesso Rapido

| Servico | URL / Acesso | Porta |
|---------|-------------|-------|
| VPS SSH | `ssh -i ~/.ssh/sparkle_vps root@187.77.37.88` | 22 |
| Runtime (externo) | https://runtime.sparkleai.tech | 8001 (interno) |
| Runtime (interno) | http://127.0.0.1:8001 | 8001 |
| Portal (externo) | https://portal.sparkleai.tech | 3001 (mapeado de 3000) |
| Supabase Dashboard | https://supabase.com/dashboard/project/gqhdspayjtiijcqklbys | — |
| Z-API Dashboard | https://app.z-api.io | — |
| GitHub Actions | https://github.com/mauromattos-lab/sparkle-aiox/actions | — |
| Coolify Dashboard | http://187.77.37.88:8000 | 8000 |
| Redis (local) | `redis-cli` na VPS | 6379 |

### Caminhos no VPS

| Item | Caminho |
|------|---------|
| Repo git | `/opt/sparkle-runtime/` |
| Codigo Runtime | `/opt/sparkle-runtime/sparkle-runtime/` |
| Codigo Portal | `/opt/sparkle-runtime/portal/` |
| .env Runtime | `/opt/sparkle-runtime/sparkle-runtime/.env` |
| venv Python | `/opt/sparkle-runtime/.venv/` |
| Log ARQ | `/var/log/sparkle-arq.log` |
| Log Keep-alive | `/var/log/sparkle-keep-alive.log` |
| ARQ cleanup script | `/usr/local/bin/sparkle-arq-cleanup.sh` |

### Servicos systemd

| Servico | Unit File |
|---------|-----------|
| `sparkle-runtime` | `/etc/systemd/system/sparkle-runtime.service` |
| `sparkle-arq` | `/etc/systemd/system/sparkle-arq.service` |
| `redis-server` | Sistema (apt) |

---

## 1. Runtime Down

**Impacto:** CRITICO. A API inteira para. Friday nao processa mensagens. Brain nao ingere. Scheduler nao roda health_alert. Portal perde backend. Zenya perde roteamento.

### Sintomas

- `https://runtime.sparkleai.tech/health` retorna erro ou timeout
- Friday nao responde no WhatsApp
- Portal mostra dados desatualizados ou erro de conexao
- GitHub Actions health-monitor falha e envia alerta WhatsApp

### Diagnostico

SSH na VPS e execute em sequencia:

```bash
# 1. Checar status do servico
systemctl status sparkle-runtime --no-pager -l

# 2. Checar se a porta esta aberta
ss -tlnp | grep 8001

# 3. Testar health endpoint localmente
curl -s http://127.0.0.1:8001/health

# 4. Ver logs recentes (ultimas 100 linhas)
journalctl -u sparkle-runtime --no-pager -n 100

# 5. Checar memoria e disco
free -h
df -h /
```

**Causas comuns:**
- OOM kill (VPS tem 8GB RAM, Runtime usa ~250MB, mas picos de ingestao podem subir)
- Erro de import apos deploy (dependencia faltando)
- .env corrompido ou variavel faltando
- Redis fora (Runtime depende de Redis para scheduler)

### Resolucao

**Caminho rapido — restart simples:**

```bash
systemctl restart sparkle-runtime
sleep 5
curl -s http://127.0.0.1:8001/health
```

Se retornar `{"status":"ok",...}` com todos os checks `true`, resolvido.

**Se o restart nao resolver — verificar dependencias:**

```bash
# Redis esta rodando?
systemctl status redis-server
redis-cli ping
# Esperado: PONG

# .env existe e tem as variaveis criticas?
ls -la /opt/sparkle-runtime/sparkle-runtime/.env
head -10 /opt/sparkle-runtime/sparkle-runtime/.env
# Deve ter: SUPABASE_KEY, ANTHROPIC_API_KEY, GROQ_API_KEY, ZAPI_*

# Testar se o Python carrega sem erro
cd /opt/sparkle-runtime/sparkle-runtime
/opt/sparkle-runtime/.venv/bin/python3 -c "from main import app; print('OK')"
```

**Se houve deploy recente e o servico nao sobe — rollback:**

```bash
cd /opt/sparkle-runtime
# Ver commits recentes
git log --oneline -5
# Rollback para commit anterior
git checkout <COMMIT_HASH_ANTERIOR>
systemctl restart sparkle-runtime
sleep 5
curl -s http://127.0.0.1:8001/health
```

### Quando escalar

- Restart + rollback nao resolvem
- OOM recorrente (3+ vezes no mesmo dia) — necessario upgrade de VPS ou otimizacao de workers
- Redis corrompido — `redis-cli FLUSHALL` como ultimo recurso (perde dados de filas em andamento)

### Prevencao

- **Keep-alive script** em `/opt/sparkle-runtime/scripts/keep-alive.sh` — faz health check local, reinicia apos 3 falhas consecutivas. Deve ser adicionado ao cron:
  ```bash
  # Adicionar ao crontab se nao estiver la:
  crontab -e
  # */5 * * * * /opt/sparkle-runtime/scripts/keep-alive.sh
  ```
- **GitHub Actions health-monitor** roda a cada 5 minutos, pinga `/health` externamente e envia alerta WhatsApp se falhar
- **systemd Restart=always RestartSec=5** garante restart automatico em crash

---

## 2. Supabase Lento/Fora

**Impacto:** ALTO. Queries de Brain, State, Agent Registry, e Tasks falham. Runtime health check mostra `"supabase": false`. Portal nao carrega dados. Ingestao para.

### Sintomas

- `curl https://runtime.sparkleai.tech/health` mostra `"supabase": false`
- Erros `connection timeout` ou `too many connections` nos logs do Runtime
- Portal carrega mas mostra listas vazias ou erros
- Ingestao de conteudo falha silenciosamente

### Diagnostico

```bash
# 1. Health check do Runtime (campo supabase)
curl -s http://127.0.0.1:8001/health | python3 -m json.tool

# 2. Testar conectividade direta ao Supabase
curl -s -o /dev/null -w "%{http_code}" \
  "https://gqhdspayjtiijcqklbys.supabase.co/rest/v1/" \
  -H "apikey: $(grep SUPABASE_KEY /opt/sparkle-runtime/sparkle-runtime/.env | cut -d= -f2)"

# 3. Checar no dashboard Supabase
# Acessar: https://supabase.com/dashboard/project/gqhdspayjtiijcqklbys
# Ver: Database > Query Performance, Database > Connections
```

**Via MCP Supabase (de dentro do Claude Code):**

```sql
-- Conexoes ativas
SELECT count(*) FROM pg_stat_activity WHERE state = 'active';

-- Queries lentas (>5s)
SELECT pid, now() - pg_stat_activity.query_start AS duration, query
FROM pg_stat_activity
WHERE state = 'active' AND now() - pg_stat_activity.query_start > interval '5 seconds'
ORDER BY duration DESC;

-- Tamanho das tabelas principais
SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC LIMIT 10;
```

**Causas comuns:**
- Connection pool exhaustion (Supabase free tier: 60 connections)
- Queries sem index (especialmente em brain_chunks com pgvector)
- Supabase paused (free tier pausa apos 7 dias sem atividade — improvavel com health_alert ativo)
- Rede entre VPS e Supabase com latencia

### Resolucao

**Se Supabase pausou:**
1. Acessar https://supabase.com/dashboard/project/gqhdspayjtiijcqklbys
2. Clicar em "Resume project"
3. Aguardar ~2 minutos
4. Verificar: `curl -s http://127.0.0.1:8001/health`

**Se connection pool exhaustion:**

```sql
-- Matar conexoes idle ha mais de 5 minutos
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle' AND state_change < now() - interval '5 minutes';
```

**Se query lenta por falta de index:**

```sql
-- Verificar se indexes pgvector existem
SELECT indexname, tablename FROM pg_indexes
WHERE tablename IN ('brain_chunks', 'brain_insights');

-- Se o index de embedding nao existir:
CREATE INDEX IF NOT EXISTS brain_chunks_embedding_idx
ON brain_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

### Prevencao

- O scheduler `health_alert` roda a cada 30s e testa Supabase — impede pausa por inatividade
- Monitorar tamanho de `brain_chunks` — acima de 10k rows, considerar particionar ou limpar chunks de baixa qualidade (confidence < 0.5)

---

## 3. Z-API Desconectou

**Impacto:** CRITICO. WhatsApp nao envia nem recebe mensagens. Zenya para de atender clientes. Friday nao recebe comandos de Mauro.

### Sintomas

- `curl https://runtime.sparkleai.tech/health` mostra `"zapi_connected": false`
- Clientes reportam que Zenya nao responde
- Mauro manda mensagem para Friday e nao recebe resposta
- Logs do Runtime mostram erros Z-API 401/403/500

### Diagnostico

```bash
# 1. Health check (campo zapi_connected)
curl -s http://127.0.0.1:8001/health | python3 -m json.tool

# 2. Testar Z-API diretamente
source /opt/sparkle-runtime/sparkle-runtime/.env
curl -s "https://api.z-api.io/instances/${ZAPI_INSTANCE_ID}/token/${ZAPI_TOKEN}/status" \
  -H "Client-Token: ${ZAPI_CLIENT_TOKEN}"

# 3. Checar se o webhook esta configurado
curl -s "https://api.z-api.io/instances/${ZAPI_INSTANCE_ID}/token/${ZAPI_TOKEN}/webhooks" \
  -H "Client-Token: ${ZAPI_CLIENT_TOKEN}"
```

**Causas comuns:**
- WhatsApp deslogou no celular (Z-API usa sessao WhatsApp Web)
- Instancia Z-API expirou ou foi desconectada
- Token invalido (rotacao de credenciais)
- Webhook URL mudou ou esta apontando para URL errada

### Resolucao

**Se instancia desconectou:**
1. Acessar https://app.z-api.io
2. Navegar ate a instancia Sparkle
3. Clicar em "Reconectar" — vai gerar QR code
4. Escanear com o WhatsApp do numero de producao
5. Verificar: `curl -s http://127.0.0.1:8001/health`

**Se webhook esta errado:**

```bash
# Reconfigura webhook para apontar pro Runtime
source /opt/sparkle-runtime/sparkle-runtime/.env
curl -s -X PUT "https://api.z-api.io/instances/${ZAPI_INSTANCE_ID}/token/${ZAPI_TOKEN}/webhooks" \
  -H "Client-Token: ${ZAPI_CLIENT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"webhookUrl": "https://runtime.sparkleai.tech/webhook/zapi"}'
```

### Prevencao

- Health check do Runtime verifica Z-API a cada 30s via health_alert
- GitHub Actions health-monitor pinga `/health` a cada 5 minutos
- Manter celular com WhatsApp sempre conectado a internet e carregando

---

## 4. Deploy Falhou

**Impacto:** MEDIO. Codigo novo nao entra em producao, mas o sistema continua rodando na versao anterior. Se o deploy era um fix critico, o bug permanece.

### Sintomas

- GitHub Actions mostra workflow vermelho em https://github.com/mauromattos-lab/sparkle-aiox/actions
- Alerta de deploy failed no historico de Actions
- Codigo novo commitado nao aparece no comportamento do Runtime/Portal

### Diagnostico

```bash
# 1. Checar status no GitHub Actions
# Acessar: https://github.com/mauromattos-lab/sparkle-aiox/actions
# Ou via gh CLI:
gh run list --repo mauromattos-lab/sparkle-aiox --limit 5

# 2. Ver logs do ultimo deploy
gh run view <RUN_ID> --repo mauromattos-lab/sparkle-aiox --log

# 3. Na VPS, verificar em qual commit esta
cd /opt/sparkle-runtime
git log --oneline -3
# Comparar com o ultimo commit no GitHub
```

**Causas comuns:**
- Health check pos-deploy falhou (servico nao subiu com codigo novo)
- SSH key expirou ou secret do GitHub esta errado
- Conflito de git no VPS (dirty working tree)
- Build do Docker Portal falhou (dependencia npm, out of disk)

### Resolucao

**Deploy manual do Runtime (se CI/CD nao funciona):**

```bash
ssh -i ~/.ssh/sparkle_vps root@187.77.37.88

cd /opt/sparkle-runtime

# Salvar commit atual para rollback
PREVIOUS=$(git rev-parse HEAD)
echo "Rollback commit: $PREVIOUS"

# Puxar codigo novo
git pull origin main

# Reiniciar servicos
systemctl restart sparkle-runtime
systemctl restart sparkle-arq

# Verificar health
sleep 5
curl -s http://127.0.0.1:8001/health

# Se falhou — rollback
git checkout $PREVIOUS
systemctl restart sparkle-runtime
systemctl restart sparkle-arq
```

**Deploy manual do Portal (se CI/CD nao funciona):**

```bash
ssh -i ~/.ssh/sparkle_vps root@187.77.37.88

cd /opt/sparkle-runtime
git pull origin main

cd portal
docker build \
  --build-arg SUPABASE_URL="https://gqhdspayjtiijcqklbys.supabase.co" \
  --build-arg SUPABASE_ANON_KEY="<ANON_KEY_FROM_GITHUB_SECRETS>" \
  -t sparkle-portal:latest .

docker stop sparkle-portal && docker rm sparkle-portal

docker run -d \
  --name sparkle-portal \
  --restart unless-stopped \
  --network coolify \
  --label "traefik.enable=true" \
  --label "traefik.http.routers.sparkle-portal-https.rule=Host(\`portal.sparkleai.tech\`)" \
  --label "traefik.http.routers.sparkle-portal-https.entrypoints=https" \
  --label "traefik.http.routers.sparkle-portal-https.tls=true" \
  --label "traefik.http.routers.sparkle-portal-https.tls.certresolver=letsencrypt" \
  --label "traefik.http.routers.sparkle-portal-http.rule=Host(\`portal.sparkleai.tech\`)" \
  --label "traefik.http.routers.sparkle-portal-http.entrypoints=http" \
  --label "traefik.http.middlewares.redirect-to-https.redirectscheme.scheme=https" \
  --label "traefik.http.routers.sparkle-portal-http.middlewares=redirect-to-https" \
  --label "traefik.http.services.sparkle-portal.loadbalancer.server.port=3000" \
  sparkle-portal:latest

sleep 5
curl -sk -o /dev/null -w "%{http_code}" https://portal.sparkleai.tech
```

**Rollback do Runtime via CI/CD:**

O workflow `deploy-runtime.yml` faz rollback automatico se o health check falha apos deploy. Se precisar forcar rollback manual:

```bash
cd /opt/sparkle-runtime
git log --oneline -10
# Identificar o commit bom
git checkout <COMMIT_BOM>
systemctl restart sparkle-runtime
systemctl restart sparkle-arq
```

### Prevencao

- deploy-runtime.yml ja tem rollback automatico
- deploy-portal.yml verifica HTTP response apos deploy
- Sempre testar localmente antes de push (especialmente imports Python e build Docker)

---

## 5. Portal Nao Carrega

**Impacto:** MEDIO. Dashboard Mission Control inacessivel. Nao afeta Runtime, Friday ou Zenya diretamente.

### Sintomas

- `https://portal.sparkleai.tech` retorna 502, 503, ou timeout
- GitHub Actions health-monitor falha no check-portal
- Alerta WhatsApp de Portal offline

### Diagnostico

```bash
ssh -i ~/.ssh/sparkle_vps root@187.77.37.88

# 1. Container esta rodando?
docker ps --filter name=sparkle-portal

# 2. Logs do container
docker logs sparkle-portal --tail 50

# 3. Testar internamente (container expoe 3000)
curl -s -o /dev/null -w "%{http_code}" http://localhost:3001

# 4. Traefik esta roteando?
# Checar se o container esta na network coolify
docker inspect sparkle-portal --format '{{json .NetworkSettings.Networks}}' | python3 -m json.tool

# 5. Checar labels Traefik
docker inspect sparkle-portal --format '{{json .Config.Labels}}' | python3 -m json.tool
```

**Causas comuns:**
- Container crashou ou parou
- Container nao esta na network `coolify` (Traefik nao enxerga)
- Labels Traefik errados — **problema conhecido:** usar um unico router com `entrypoints=http,https` causa 502. Deve ter dois routers separados: `sparkle-portal-http` (redirect) e `sparkle-portal-https` (TLS)
- Certificado TLS expirou (letsencrypt certresolver falhou)
- Disco cheio (build Docker gera imagens grandes)

### Resolucao

**Se container parou — restart simples:**

```bash
docker start sparkle-portal
sleep 5
curl -sk -o /dev/null -w "%{http_code}" https://portal.sparkleai.tech
```

**Se container nao existe ou precisa rebuild:**

```bash
# Parar e remover se existir
docker stop sparkle-portal 2>/dev/null; docker rm sparkle-portal 2>/dev/null

# Rebuild
cd /opt/sparkle-runtime/portal
docker build \
  --build-arg SUPABASE_URL="https://gqhdspayjtiijcqklbys.supabase.co" \
  --build-arg SUPABASE_ANON_KEY="<CHAVE>" \
  -t sparkle-portal:latest .

# Rodar com labels corretos (DOIS routers — http redirect + https)
docker run -d \
  --name sparkle-portal \
  --restart unless-stopped \
  --network coolify \
  --label "traefik.enable=true" \
  --label "traefik.http.routers.sparkle-portal-https.rule=Host(\`portal.sparkleai.tech\`)" \
  --label "traefik.http.routers.sparkle-portal-https.entrypoints=https" \
  --label "traefik.http.routers.sparkle-portal-https.tls=true" \
  --label "traefik.http.routers.sparkle-portal-https.tls.certresolver=letsencrypt" \
  --label "traefik.http.routers.sparkle-portal-http.rule=Host(\`portal.sparkleai.tech\`)" \
  --label "traefik.http.routers.sparkle-portal-http.entrypoints=http" \
  --label "traefik.http.middlewares.redirect-to-https.redirectscheme.scheme=https" \
  --label "traefik.http.routers.sparkle-portal-http.middlewares=redirect-to-https" \
  --label "traefik.http.services.sparkle-portal.loadbalancer.server.port=3000" \
  sparkle-portal:latest

sleep 5
curl -sk -o /dev/null -w "%{http_code}" https://portal.sparkleai.tech
```

**Se disco cheio — limpar imagens Docker antigas:**

```bash
docker image prune -f
docker system prune -f
df -h /
```

**Problema conhecido — split router Traefik:**

Se alguem recriar o container com um unico router tipo:
```
traefik.http.routers.sparkle-portal.entrypoints=http,https
```
Isso causa 502. A solucao correta e SEMPRE ter dois routers separados:
- `sparkle-portal-http` com entrypoint `http` + middleware redirect-to-https
- `sparkle-portal-https` com entrypoint `https` + TLS + certresolver

### Prevencao

- Container roda com `--restart unless-stopped`
- GitHub Actions health-monitor pinga Portal a cada 5 minutos
- Limpar imagens Docker antigas periodicamente: `docker image prune -f`

---

## 6. ARQ Worker Parou

**Impacto:** ALTO. Tarefas assincronas nao processam: ingestao de conteudo (brain_ingest), extracao de insights (extract_insights), crons agendados (process_pending_tasks, health_alert). O Runtime API continua respondendo mas nada e executado de fato.

### Sintomas

- Tarefas ficam com status `pending` ou `in_progress` indefinidamente em `agent_tasks`
- Brain nao ingere novos conteudos
- `/system/pulse` mostra `workflows.completed_today` parado
- Logs em `/var/log/sparkle-arq.log` nao atualizam

### Diagnostico

```bash
ssh -i ~/.ssh/sparkle_vps root@187.77.37.88

# 1. Status do servico
systemctl status sparkle-arq --no-pager -l

# 2. Ver logs recentes
tail -50 /var/log/sparkle-arq.log

# 3. Checar se processo arq esta rodando
pgrep -fa "arq runtime.tasks.worker"

# 4. Checar Redis (ARQ depende de Redis)
redis-cli ping
redis-cli keys "arq:*"

# 5. Checar se ha tarefas stuck no Redis
redis-cli keys "arq:in-progress:*"
```

**Causas comuns:**
- Redis caiu (ARQ usa Redis como broker)
- Worker crashou com excecao nao tratada
- Tarefas stuck (rodam >10 min sem completar) — bloqueiam o worker
- Workers orfaos (processos arq que sobreviveram a um restart)

### Resolucao

**Restart simples:**

```bash
systemctl restart sparkle-arq
sleep 3
systemctl status sparkle-arq --no-pager
```

**Se Redis caiu:**

```bash
systemctl restart redis-server
sleep 2
redis-cli ping
# Depois restart do ARQ
systemctl restart sparkle-arq
```

**Se ha tarefas stuck no Redis:**

```bash
# Listar chaves in-progress
redis-cli keys "arq:in-progress:*"

# Limpar tarefas in-progress antigas (cuidado — interrompe tarefas em andamento)
redis-cli keys "arq:in-progress:*" | xargs -I {} redis-cli del {}

# Restart worker
systemctl restart sparkle-arq
```

**Se ha workers orfaos:**

O script `/usr/local/bin/sparkle-arq-cleanup.sh` e executado automaticamente no ExecStopPost do systemd. Para rodar manualmente:

```bash
/usr/local/bin/sparkle-arq-cleanup.sh
systemctl restart sparkle-arq
```

**Auto-resolucao de tarefas stuck:**

O handler `health_alert` (executado pelo scheduler a cada 30s) verifica automaticamente tarefas com status `in_progress` ha mais de 10 minutos e as marca como `failed`. Isso impede acumulo de tarefas fantasma.

### Prevencao

- systemd `Restart=always RestartSec=5` reinicia o worker automaticamente
- `sparkle-arq-cleanup.sh` mata workers orfaos no stop
- `health_alert` handler limpa tarefas stuck >10 min
- Monitorar `/var/log/sparkle-arq.log` para erros recorrentes

---

## 7. Brain Quality Degradation

**Impacto:** MEDIO. Dados duplicados ou mal classificados em `brain_chunks` e `brain_insights` degradam qualidade das respostas da Zenya e do Brain search. Nao causa downtime mas reduz eficacia.

### Sintomas

- Brain search retorna resultados repetidos ou irrelevantes
- Dominios estranhos aparecem em insights (ex: "conteudo_digital" ao inves de "content_strategy")
- `brain_chunks` cresce rapido sem aumento proporcional de conteudo novo
- Confidence scores baixos em chunks recentes

### Diagnostico

```sql
-- Executar via MCP Supabase (mcp__supabase__execute_sql)

-- 1. Contagem total e por status
SELECT status, count(*) FROM brain_sources GROUP BY status;

-- 2. Distribuicao de dominios em insights
SELECT domain, count(*) FROM brain_insights GROUP BY domain ORDER BY count DESC;

-- 3. Chunks com confidence muito baixa
SELECT id, title, confidence, created_at
FROM brain_chunks
WHERE confidence < 0.5
ORDER BY created_at DESC LIMIT 20;

-- 4. Possíveis duplicatas (mesmo titulo + source)
SELECT title, source_id, count(*)
FROM brain_chunks
GROUP BY title, source_id
HAVING count(*) > 1
ORDER BY count DESC LIMIT 20;

-- 5. Insights com dominios nao canonicos
SELECT DISTINCT domain FROM brain_insights
WHERE domain NOT IN (
  'content_strategy', 'video_production', 'prompt_engineering',
  'dev_tools', 'product_strategy', 'ai_tools', 'ux_design',
  'onboarding_education', 'ai_development', 'marketing_sales',
  'project_management', 'narrative_storytelling', 'mindset', 'geral'
);
```

### 13 Dominios Canonicos

O sistema usa exatamente 14 dominios canonicos (definidos em `sparkle-runtime/runtime/tasks/handlers/extract_insights.py`):

| Dominio | Descricao |
|---------|-----------|
| `content_strategy` | Criacao de conteudo, estrategia editorial, copywriting |
| `video_production` | Edicao de video, motion graphics, animacao |
| `prompt_engineering` | Engenharia de prompt, otimizacao de output IA |
| `dev_tools` | Ferramentas de dev, CLI, DevOps, infraestrutura |
| `product_strategy` | Posicionamento de produto, SaaS, pricing |
| `ai_tools` | Ferramentas de IA, automacao, workflows com IA |
| `ux_design` | Design de interface, UX |
| `onboarding_education` | Tutoriais, documentacao, onboarding |
| `ai_development` | Arquitetura de sistemas IA, engenharia de IA |
| `marketing_sales` | Marketing digital, vendas, growth |
| `project_management` | Gestao de projetos, produtividade |
| `narrative_storytelling` | Estrutura narrativa, roteiro |
| `mindset` | Mentalidade, psicologia, motivacao |
| `geral` | Fallback quando nenhum outro se aplica |

### Resolucao

**Limpar chunks de baixa qualidade:**

```sql
-- Remover chunks com confidence muito baixa (< 0.3)
DELETE FROM brain_chunks WHERE confidence < 0.3;

-- Remover insights com dominios invalidos (normalizar para 'geral')
UPDATE brain_insights SET domain = 'geral'
WHERE domain NOT IN (
  'content_strategy', 'video_production', 'prompt_engineering',
  'dev_tools', 'product_strategy', 'ai_tools', 'ux_design',
  'onboarding_education', 'ai_development', 'marketing_sales',
  'project_management', 'narrative_storytelling', 'mindset', 'geral'
);
```

**Deduplicacao semantica:**

O sistema tem RPCs Supabase para dedup:
- `match_similar_chunks(query_embedding, similarity_threshold, match_count)` — busca chunks similares
- `match_similar_insights(query_embedding, similarity_threshold, match_count)` — busca insights similares

Threshold padrao: 0.92 (definido em `sparkle-runtime/runtime/brain/dedup.py`).

Para rodar dedup em lote, usar o backfill script:

```bash
cd /opt/sparkle-runtime/sparkle-runtime
/opt/sparkle-runtime/.venv/bin/python3 ../scripts/backfill_embeddings.py
```

**Remover duplicatas exatas (mesmo source_id + titulo):**

```sql
-- Identificar e manter apenas o mais recente
DELETE FROM brain_chunks a
USING brain_chunks b
WHERE a.id < b.id
  AND a.title = b.title
  AND a.source_id = b.source_id;
```

### Prevencao

- O handler `brain_ingest` ja faz dedup semantica antes de inserir (threshold 0.92)
- O handler `extract_insights` normaliza dominios para os 14 canonicos
- Ingestoes duplicadas do mesmo URL sao detectadas por `source_id`
- Monitorar periodicamente a distribuicao de dominios e confidence scores

---

## Checklist Pos-Incidente

Apos resolver qualquer incidente:

- [ ] Verificar que `/health` retorna `{"status":"ok"}` com todos os checks `true`
- [ ] Verificar que `/system/pulse` mostra dados recentes
- [ ] Se afetou clientes, verificar que Z-API esta `connected`
- [ ] Se afetou Brain, verificar ultima ingestao em `/brain/activity`
- [ ] Registrar o incidente: o que aconteceu, quando, como foi resolvido
- [ ] Se o incidente revelou gap de monitoramento, criar issue para melhorar

---

## Contatos de Escalacao

| Nivel | Quem | Quando |
|-------|------|--------|
| L1 | @devops (Gage) — automatico | Qualquer incidente |
| L2 | Mauro Mattos | Decisao de negocio, credencial externa, upgrade de infra |
| Externo | Supabase Support | Problema no lado Supabase (status.supabase.com) |
| Externo | Z-API Support | Problema na plataforma Z-API |
| Externo | Hostinger Support | Problema na VPS (rede, hardware) |
