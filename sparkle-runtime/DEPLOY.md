# Sparkle Runtime — Guia de Deploy em Produção

> Autor: @devops (Gage) | Data: 2026-03-31
> Destinatário: Mauro — todos os comandos são exatos, copie e execute.

---

## Decisão de Plataforma

**Recomendação: subir na VPS existente onde o n8n já roda.**

### Por que não Railway / Render?

| Critério | Railway/Render | VPS Própria |
|---|---|---|
| Custo | ~$10–20/mês extra (plano pago p/ ARQ+Redis) | R$0 adicional (já pago) |
| Redis incluído | Pago ($5+/mês no Railway) | Instala grátis na mesma VPS |
| Domínio `*.sparkleai.tech` | Requer DNS externo + config extra | Nginx já configurado |
| Tempo para subir | 30–60 min (configurar serviço novo) | 15–20 min (mesma infra) |
| Compatibilidade ARQ+Redis | Sim (mas Redis separado = custo) | Redis local = zero latência |
| Controle total | Limitado | Total |

**Conclusão:** a VPS é a escolha certa para o Marco 0. Railway/Render faz sentido quando o volume de clientes exigir auto-scaling — isso não é hoje.

---

## Pré-requisitos (verifique antes de começar)

Acesse a VPS:

```bash
ssh root@SEU_IP_VPS
```

Verifique que Python 3.11+ está instalado:

```bash
python3 --version
```

Se retornar versão abaixo de 3.11, instale:

```bash
apt update && apt install -y python3.11 python3.11-venv python3-pip
```

---

## Passo 1 — Redis na VPS

O ARQ worker precisa de Redis. Instale e habilite:

```bash
apt update && apt install -y redis-server
systemctl enable redis-server
systemctl start redis-server
```

Verifique que está rodando:

```bash
redis-cli ping
```

Resposta esperada: `PONG`

O Redis ficará disponível em `redis://localhost:6379` — exatamente o valor padrão do Runtime.

---

## Passo 2 — Clonar o código na VPS

```bash
mkdir -p /opt/sparkle-runtime
cd /opt/sparkle-runtime
git clone https://github.com/SEU_ORG/sparkle-runtime.git .
```

> Se o repositório for privado, use um token de acesso pessoal do GitHub:
> `git clone https://SEU_TOKEN@github.com/SEU_ORG/sparkle-runtime.git .`

---

## Passo 3 — Ambiente virtual Python

```bash
cd /opt/sparkle-runtime
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Passo 4 — Variáveis de Ambiente

Crie o arquivo `.env` na VPS:

```bash
nano /opt/sparkle-runtime/.env
```

Cole o conteúdo abaixo, preenchendo cada valor:

```dotenv
# ── Supabase ────────────────────────────────────────────────
SUPABASE_URL=https://gqhdspayjtiijcqklbys.supabase.co
SUPABASE_KEY=sua_chave_supabase_aqui

# ── Anthropic (Claude) ──────────────────────────────────────
ANTHROPIC_API_KEY=sk-ant-...

# ── Groq (transcrição de áudio / Whisper) ──────────────────
GROQ_API_KEY=gsk_...

# ── Z-API ──────────────────────────────────────────────────
ZAPI_BASE_URL=https://api.z-api.io
ZAPI_INSTANCE_ID=seu_instance_id
ZAPI_TOKEN=seu_token_zapi
ZAPI_CLIENT_TOKEN=seu_client_token_zapi

# ── Friday ─────────────────────────────────────────────────
MAURO_WHATSAPP=5512999999999

# ── Redis (ARQ worker) ─────────────────────────────────────
REDIS_URL=redis://localhost:6379
```

Salve: `Ctrl+O`, `Enter`, `Ctrl+X`

> **Variável que o dev não incluiu no .env.example:** `MAURO_WHATSAPP`
> Esta variável está em `config.py` mas estava ausente do `.env.example`.
> Preencha com o número do WhatsApp do Mauro no formato internacional sem `+` (ex: `5512999999999`).

---

## Passo 5 — Teste rápido antes de subir como serviço

```bash
cd /opt/sparkle-runtime
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8001 --workers 1
```

Em outro terminal (ou curl de outra máquina):

```bash
curl http://localhost:8001/health
```

Resposta esperada (status "ok" ou "degraded" se Z-API não estiver configurado ainda):

```json
{
  "status": "ok",
  "version": "0.1.0",
  "checks": { ... }
}
```

Se funcionou, pare o servidor: `Ctrl+C`

---

## Passo 6 — Serviços systemd (API + ARQ Worker)

### 6a — API (uvicorn)

```bash
nano /etc/systemd/system/sparkle-runtime.service
```

Cole:

```ini
[Unit]
Description=Sparkle Runtime API
After=network.target redis-server.service

[Service]
User=root
WorkingDirectory=/opt/sparkle-runtime
EnvironmentFile=/opt/sparkle-runtime/.env
ExecStart=/opt/sparkle-runtime/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8001 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Salve: `Ctrl+O`, `Enter`, `Ctrl+X`

### 6b — ARQ Worker (processamento assíncrono de tarefas)

```bash
nano /etc/systemd/system/sparkle-worker.service
```

Cole:

```ini
[Unit]
Description=Sparkle ARQ Worker
After=network.target redis-server.service

[Service]
User=root
WorkingDirectory=/opt/sparkle-runtime
EnvironmentFile=/opt/sparkle-runtime/.env
ExecStart=/opt/sparkle-runtime/.venv/bin/arq runtime.tasks.worker.WorkerSettings
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Salve: `Ctrl+O`, `Enter`, `Ctrl+X`

### Ative e inicie os dois:

```bash
systemctl daemon-reload
systemctl enable sparkle-runtime sparkle-worker
systemctl start sparkle-runtime sparkle-worker
```

Verifique status:

```bash
systemctl status sparkle-runtime
systemctl status sparkle-worker
```

Ambos devem mostrar `Active: active (running)`.

---

## Passo 7 — Nginx (domínio público + HTTPS)

### Subdomínio recomendado: `runtime.sparkleai.tech`

#### 7a — DNS

No painel do seu registrador de domínio, adicione um registro A:

```
Tipo: A
Nome: runtime
Valor: SEU_IP_VPS
TTL: 300
```

#### 7b — Configuração Nginx

```bash
nano /etc/nginx/sites-available/sparkle-runtime
```

Cole:

```nginx
server {
    listen 80;
    server_name runtime.sparkleai.tech;

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection keep-alive;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120;
        proxy_connect_timeout 120;
        client_max_body_size 25M;
    }
}
```

Salve: `Ctrl+O`, `Enter`, `Ctrl+X`

Ative e recarregue:

```bash
ln -s /etc/nginx/sites-available/sparkle-runtime /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

#### 7c — HTTPS com Certbot (gratuito)

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d runtime.sparkleai.tech
```

Siga as instruções na tela (email para renovação, aceite os termos).

Ao finalizar, o Certbot configura HTTPS automático e renovação automática.

**URL final do webhook:** `https://runtime.sparkleai.tech/friday/webhook`

---

## Passo 8 — Configurar webhook no Z-API

No painel do Z-API, configure o webhook de mensagens recebidas para:

```
https://runtime.sparkleai.tech/friday/webhook
```

Método: `POST`

---

## Passo 9 — Deploy de atualizações (como fazer no futuro)

Quando o dev entregar uma nova versão, execute na VPS:

```bash
cd /opt/sparkle-runtime
git pull
source .venv/bin/activate
pip install -r requirements.txt
systemctl restart sparkle-runtime sparkle-worker
```

Verifique que voltou:

```bash
curl https://runtime.sparkleai.tech/health
```

---

## Monitoramento

### UptimeRobot (gratuito — suficiente para Marco 0)

1. Acesse https://uptimerobot.com e crie uma conta gratuita.
2. Clique em **Add New Monitor**.
3. Configure:
   - **Monitor Type:** HTTP(s)
   - **Friendly Name:** Sparkle Runtime
   - **URL:** `https://runtime.sparkleai.tech/health`
   - **Monitoring Interval:** 5 minutos
   - **Alert Contacts:** adicione seu e-mail e/ou número de WhatsApp

Quando o servidor cair, você receberá alerta imediato.

### Logs em tempo real (quando precisar debugar)

```bash
# Logs da API
journalctl -u sparkle-runtime -f

# Logs do Worker ARQ
journalctl -u sparkle-worker -f

# Logs do Redis
journalctl -u redis-server -f
```

---

## Checklist de Go-Live

- [ ] Redis instalado e rodando (`redis-cli ping` retorna `PONG`)
- [ ] Dependências Python instaladas (`pip install -r requirements.txt`)
- [ ] Arquivo `.env` criado com todas as variáveis preenchidas (incluindo `MAURO_WHATSAPP`)
- [ ] `/health` retorna `"status": "ok"` localmente
- [ ] `sparkle-runtime.service` ativo (`systemctl status sparkle-runtime`)
- [ ] `sparkle-worker.service` ativo (`systemctl status sparkle-worker`)
- [ ] DNS `runtime.sparkleai.tech` apontando para IP da VPS
- [ ] Nginx configurado e recarregado
- [ ] HTTPS ativo (Certbot executado com sucesso)
- [ ] `/health` retorna `"status": "ok"` via `https://runtime.sparkleai.tech/health`
- [ ] Webhook configurado no Z-API para `https://runtime.sparkleai.tech/friday/webhook`
- [ ] Monitor UptimeRobot criado

---

## Resumo de Variáveis Necessárias

| Variável | Obrigatória | Origem |
|---|---|---|
| `SUPABASE_URL` | Sim | Settings AIOS |
| `SUPABASE_KEY` | Sim | Settings AIOS |
| `ANTHROPIC_API_KEY` | Sim | console.anthropic.com |
| `GROQ_API_KEY` | Sim | console.groq.com |
| `ZAPI_BASE_URL` | Sim | Painel Z-API |
| `ZAPI_INSTANCE_ID` | Sim | Painel Z-API |
| `ZAPI_TOKEN` | Sim | Painel Z-API |
| `ZAPI_CLIENT_TOKEN` | Sim | Painel Z-API |
| `MAURO_WHATSAPP` | Sim | Número do Mauro (sem +) |
| `REDIS_URL` | Sim (padrão ok) | `redis://localhost:6379` |

> `REDIS_URL` já tem valor padrão no código. Se você instalou o Redis na VPS conforme Passo 1, não precisa mudar nada.
