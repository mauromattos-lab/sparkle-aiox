#!/bin/bash
# =============================================================
# Sparkle Runtime — Setup Completo da VPS
# Rode como root: bash vps-setup.sh
# =============================================================
set -e

echo "============================================"
echo " Sparkle Runtime — Setup VPS (auto)"
echo "============================================"

# ---- 1. Redis -----------------------------------------------
echo ""
echo "[1/6] Instalando Redis..."
apt-get update -q
apt-get install -y -q redis-server nginx certbot python3-certbot-nginx
systemctl enable redis-server
systemctl start redis-server
redis-cli ping | grep -q PONG && echo "  Redis: OK" || { echo "  Redis FALHOU"; exit 1; }

# ---- 2. Python 3.11 -----------------------------------------
echo ""
echo "[2/6] Verificando Python 3.11..."
if ! python3.11 --version &>/dev/null; then
  apt-get install -y -q python3.11 python3.11-venv python3-pip
fi
python3.11 --version

# ---- 3. Clonar repositório ----------------------------------
echo ""
echo "[3/6] Clonando repositório..."
mkdir -p /opt/sparkle-runtime
cd /opt/sparkle-runtime

if [ -d ".git" ]; then
  echo "  Repositório já existe — fazendo git pull..."
  git pull
else
  git clone https://github.com/mauromattos-lab/sparkle-aiox.git /tmp/sparkle-aiox
  cp -r /tmp/sparkle-aiox/sparkle-runtime/. /opt/sparkle-runtime/
  rm -rf /tmp/sparkle-aiox
fi

# ---- 4. Ambiente virtual Python -----------------------------
echo ""
echo "[4/6] Criando virtualenv e instalando dependências..."
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "  Dependências instaladas."
deactivate

# ---- 5. Systemd services ------------------------------------
echo ""
echo "[5/6] Criando serviços systemd..."

cat > /etc/systemd/system/sparkle-runtime.service << 'EOF'
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
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/sparkle-worker.service << 'EOF'
[Unit]
Description=Sparkle ARQ Worker
After=network.target redis-server.service sparkle-runtime.service

[Service]
User=root
WorkingDirectory=/opt/sparkle-runtime
EnvironmentFile=/opt/sparkle-runtime/.env
ExecStart=/opt/sparkle-runtime/.venv/bin/arq runtime.tasks.worker.WorkerSettings
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload

# ---- 6. Nginx -----------------------------------------------
echo ""
echo "[6/6] Configurando Nginx..."

cat > /etc/nginx/sites-available/sparkle-runtime << 'NGINXEOF'
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
NGINXEOF

ln -sf /etc/nginx/sites-available/sparkle-runtime /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
echo "  Nginx configurado."

# ---- Resumo -------------------------------------------------
echo ""
echo "============================================"
echo " Setup concluído!"
echo "============================================"
echo ""
echo "PRÓXIMO PASSO OBRIGATÓRIO:"
echo "  Crie o arquivo /opt/sparkle-runtime/.env com as credenciais:"
echo ""
echo "  nano /opt/sparkle-runtime/.env"
echo ""
echo "Conteúdo do .env (preencha os valores):"
cat << 'ENVEOF'
SUPABASE_URL=https://gqhdspayjtiijcqklbys.supabase.co
SUPABASE_KEY=<sua_key_supabase>
ANTHROPIC_API_KEY=<sk-ant-...>
GROQ_API_KEY=<gsk_...>
ZAPI_BASE_URL=https://api.z-api.io
ZAPI_INSTANCE_ID=3F0B3059B80821F7B9149E8469198590
ZAPI_TOKEN=<seu_token_zapi>
ZAPI_CLIENT_TOKEN=<seu_client_token>
MAURO_WHATSAPP=5512981303249
REDIS_URL=redis://localhost:6379
ENVEOF

echo ""
echo "Depois de criar o .env, execute:"
echo "  systemctl start sparkle-runtime sparkle-worker"
echo "  systemctl status sparkle-runtime sparkle-worker"
echo "  curl http://localhost:8001/health"
echo ""
echo "Para HTTPS (após DNS runtime.sparkleai.tech apontar para este IP):"
echo "  certbot --nginx -d runtime.sparkleai.tech"
