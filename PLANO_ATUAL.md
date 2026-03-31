# PLANO ATUAL — Sparkle AIOX
> Orion lê este arquivo no início de TODA sessão antes de qualquer ação.
> Última atualização: 2026-03-31

---

## MECANISMO ANTI-COMPACTAÇÃO (LEIA PRIMEIRO)

### Passo 1 — Consultar estado real do sistema via Supabase

No início de toda sessão, Orion deve executar esta query via MCP Supabase para saber o estado **real** do sistema (independente do contexto da conversa):

```sql
SELECT get_orion_session_context();
```

Esta função retorna:
- `agents`: 5 agentes registrados (brain, friday, orion, qa, zenya)
- `tasks_by_status_7d`: quantas tasks done/pending/failed nos últimos 7 dias
- `pending_tasks`: tasks aguardando execução (worker não está rodando ainda)
- `recent_tasks`: últimas 10 tasks executadas
- `cost_usd_7d`: custo LLM acumulado nos últimos 7 dias

### Passo 2 — Ler este arquivo

As informações de **plano, prioridade e bloqueios** estão neste arquivo.
O Supabase tem o **estado em tempo real** do que o runtime executou.

---

## PLANO VIGENTE (NÃO SUBSTITUIR SEM ATUALIZAR AQUI)

| Documento | Papel |
|-----------|-------|
| `docs/strategy/plano-mestre-sparkle-2026.md` | Estratégia — 3 fases (Abr / Mai-Jun / Jul-Dez 2026) |
| `docs/architecture/dev-vision-marco0.md` | Marco 0 técnico — FastAPI Runtime |
| `docs/architecture/aria-architectural-evaluation.md` | 6 decisões arquiteturais (todas implementadas) |
| `docs/architecture/sparkle-brain-mechanism.md` | Mecanismo técnico do Sparkle Brain |
| `docs/architecture/sparkle-os-project.md` | Arquitetura de longo prazo do Runtime |

**NÃO usar como plano principal:** `docs/architecture/aios-v2/` (n8n AIOS v2 — infraestrutura de suporte, não o foco de desenvolvimento)

---

## STATUS MARCO 0 (atualizado 2026-03-31 — fim do dia)

| Item | Status |
|------|--------|
| `sparkle-runtime/` — código FastAPI | ✅ EXISTE, TESTADO E NO GITHUB |
| Migration `001_initial.sql` no Supabase | ✅ APLICADA (agents, runtime_tasks, llm_cost_log, brain_*) |
| RPC `get_orion_session_context` no Supabase | ✅ CRIADA (migration 002) |
| `/health` — todos checks verdes | ✅ supabase, zapi, groq, anthropic |
| `echo` e `status_report` intents | ✅ FUNCIONANDO (smoke test aprovado) |
| BUG-01 e BUG-02 do QA report | ✅ JÁ CORRIGIDOS |
| `.gitignore` + push ao GitHub | ✅ mauromattos-lab/sparkle-aiox |
| Script `scripts/vps-setup.sh` | ✅ CRIADO |
| Deploy VPS (24/7) | ❌ PENDENTE — próximo passo |
| DNS runtime.sparkleai.tech | ❌ PENDENTE — criar no painel Hostinger |
| Nginx + HTTPS (Certbot) | ❌ PENDENTE — após deploy |
| Friday v1.1 — audio via Z-API webhook | ❌ PENDENTE (transcriber existe, falta teste E2E) |
| Zenya Confeitaria go-live | ❌ BLOQUEADO (BLOCK-01: Z-API pendente do Mauro) |
| Dashboard mínimo (3 telas) | ❌ PENDENTE |

---

## DEPLOY VPS — PRÓXIMO PASSO DESBLOQUEADO

### O que o Mauro precisa fazer (SSH na VPS):

```bash
# 1. Conectar na VPS
ssh root@147.93.39.95

# 2. Baixar e rodar script de setup (instala Redis, Python, Nginx, cria systemd)
curl -fsSL https://raw.githubusercontent.com/mauromattos-lab/sparkle-aiox/main/sparkle-runtime/scripts/vps-setup.sh | bash

# 3. Criar .env com credenciais reais
nano /opt/sparkle-runtime/.env
# (copiar conteúdo do sparkle-runtime/.env local — já tem todas as credenciais)

# 4. Iniciar serviços
systemctl start sparkle-runtime sparkle-worker
curl http://localhost:8001/health

# 5. Adicionar DNS no painel Hostinger:
#    Tipo: A | Nome: runtime | Valor: 147.93.39.95 | TTL: 300

# 6. HTTPS (após DNS propagar)
certbot --nginx -d runtime.sparkleai.tech

# 7. Verificar
curl https://runtime.sparkleai.tech/health
```

### O que a Orion faz após confirmação de deploy:
- Configurar Z-API webhook: `https://runtime.sparkleai.tech/friday/webhook`
- Testar Friday audio pipeline E2E
- Atualizar status neste arquivo

---

## PRIORIDADE DE TRABALHO

1. **Deploy VPS** — desbloqueado, depende só do Mauro rodar os comandos acima
2. **Friday audio E2E** — pós-deploy
3. **Dashboard mínimo** — portal Next.js com queries do Runtime + Supabase
4. **Plano-mestre Fase 1** — prioridade padrão fora das urgências
5. **Clientes** — entram como interrupção quando Mauro traz algo específico

---

## PRÓXIMOS PASSOS QUE DEPENDEM DO MAURO

- BLOCK-01: Z-API Confeitaria → Chatwoot inbox → Zenya go-live
- BLOCK-02: Resposta do Douglas (Ensinaja)
- BLOCK-03: API key Loja Integrada (Julia / Fun Personalize)
- BLOCK-04: Redirect Z-API Friday para Runtime webhook (após deploy)
- BLOCK-05: Vincular ad account Gabriela + criativos
- BLOCK-06: WhatsApp Vitalis (João)

---

## REGRA ANTI-DESVIO

Se Orion começar uma sessão e a conversa anterior tinha contexto de AIOS v2 ou outro plano:
**PARAR. Rodar `get_orion_session_context()`. Ler este arquivo. Retomar pelo próximo item desbloqueado acima.**

Pergunta de verificação rápida: "O runtime está rodando na VPS?"
- NÃO → próximo passo é o deploy (comandos acima)
- SIM → checar pending_tasks no Supabase e continuar o plano-mestre
