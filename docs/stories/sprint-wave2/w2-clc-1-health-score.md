---
epic: EPIC-WAVE2 — Substância dos Domínios (Fase 3 AIOS)
story: W2-CLC-1
title: Ciclo do Cliente — Health Score por Cliente + Alerta Friday
status: Ready for Dev
priority: Crítica
executor: "@dev (implementação) -> @qa (validação) -> @devops (deploy)"
sprint: Wave 2 — Domain Substance (2026-04-07+)
depends_on: [W1-FRIDAY-1 (Friday com Brain funcional), W0-BRAIN-2 (chunks aprovados)]
unblocks: [W2-CLC-2 (relatório semanal usa Health Score), W2-FRIDAY-2 (trigger client_health_alert)]
estimated_effort: "6-9h (@dev 5-7h + @qa 1-2h)"
prd_reference: docs/prd/domain-client-lifecycle-prd.md
architecture_reference: docs/architecture/domain-client-lifecycle-architecture.md
---

# Story W2-CLC-1 — Ciclo do Cliente: Health Score por Cliente + Alerta Friday

## Story

**Como** Mauro (fundador),
**Quero** que o sistema calcule automaticamente um Health Score (0-100) para cada cliente toda semana, com base em sinais reais de uso e pagamento,
**Para que** eu receba alertas da Friday quando um cliente está em risco, antes de virar churn — sem precisar monitorar manualmente cada conta.

---

## Contexto Técnico

**Por que agora:** O sistema tem 6 clientes pagantes e zero visibilidade sobre saúde individual. O único sinal de problema é quando o cliente reclama ou para de pagar. Health Score é o mecanismo que transforma dados dispersos (zenya_events, pagamentos, logins) em um número acionável.

**O que existe e funciona hoje (não alterar):**
- `zenya_events` — telemetria de atendimentos Zenya por cliente
- `clients` / `zenya_clients` — tabelas de configuração dos clientes ativos
- Friday `proactive.py` — sistema de alertas com anti-spam implementado (não alterar os triggers existentes)
- `scheduler.py` — cron engine async com APScheduler (adicionar novo job aqui)

**O que esta story entrega:**
1. Módulo `runtime/client_lifecycle/health_score.py` — cálculo do score com 5 sinais
2. Migration `020_client_health.sql` — tabela `client_health` no Supabase
3. Cron semanal `client_health_check` (segunda-feira às 09h BRT)
4. Alerta Friday quando score < 60 com sugestão de abordagem
5. Endpoint `GET /client-lifecycle/health/{client_id}` para consulta

**Arquivos no VPS (`/opt/sparkle-aiox/sparkle-runtime/`):**

| Arquivo | Status | O que muda |
|---------|--------|-----------|
| `runtime/client_lifecycle/health_score.py` | Criar | Módulo de cálculo |
| `runtime/client_lifecycle/router.py` | Criar ou verificar se existe | Endpoint GET /health/{id} |
| `runtime/scheduler.py` | Modificar | Adicionar cron health_check |
| `runtime/friday/proactive.py` | Modificar | Adicionar trigger client_health_alert |
| `migrations/020_client_health.sql` | Criar | Schema tabela |
| `tests/unit/test_health_score.py` | Criar | Testes unitários |

---

## Critérios de Aceitação

### AC-1 — Cálculo do Health Score com 5 sinais

- [ ] Função `calculate_health_score(client_id) -> dict` implementada em `health_score.py`
- [ ] Score calculado com os 5 sinais ponderados conforme PRD:
  - `volume_mensagens` (30%): média de mensagens nos últimos 7 dias vs. média do mês anterior
  - `pagamento_em_dia` (25%): último pagamento confirma dentro de 5 dias do vencimento = 100; 6-15 dias = 50; >15 dias = 0
  - `ultimo_acesso_dono` (20%): acesso pelo dono da conta (zenya_events com tipo admin/config) nos últimos 14 dias
  - `suporte_aberto` (15%): sem ticket de suporte aberto não resolvido = 100; com ticket = 0
  - `resposta_checkin` (10%): respondeu último check-in mensal = 100; não respondeu = 50; nunca recebeu = 75
- [ ] Score final é inteiro 0-100 (média ponderada arredondada)
- [ ] Resultado inclui `{ client_id, score, signals: { [sinal]: { raw, weight, weighted_score } }, calculated_at, risk_level }`
- [ ] `risk_level` calculado: score >= 80 → `healthy`, 60-79 → `at_risk`, < 60 → `critical`

### AC-2 — Tabela client_health no Supabase

- [ ] Migration `020_client_health.sql` aplicada via `mcp__supabase__apply_migration`
- [ ] Schema: `id uuid, client_id uuid, score integer, signals jsonb, risk_level text, alert_sent boolean default false, calculated_at timestamptz`
- [ ] Index em `client_id` e `calculated_at`
- [ ] RLS: apenas `service_role` pode escrever; selects autenticados podem ler

### AC-3 — Cron semanal executa e persiste

- [ ] Job `client_health_check` registrado em `scheduler.py` para segunda-feira às 09h00 BRT
- [ ] Cron itera todos os clientes em `zenya_clients` com status ativo
- [ ] Calcula e salva score para cada cliente em `client_health`
- [ ] Log estruturado: `[CLC] Health Score calculado: {N} clientes — {X} healthy, {Y} at_risk, {Z} critical`
- [ ] Falha em um cliente não interrompe o cron (try/except por cliente)

### AC-4 — Alerta Friday quando score < 60

- [ ] Trigger `client_health_alert` adicionado em `proactive.py`
- [ ] Trigger dispara quando score < 60 E `alert_sent = false` para aquele ciclo
- [ ] Mensagem inclui: nome do cliente, score, sinal mais fraco, sugestão de abordagem
- [ ] Exemplo: "Mauro, Health Score do Ensinaja caiu para 48 (crítico). Sinal mais fraco: sem atividade da Zenya há 18 dias. Sugestão: ligue pro Douglas e pergunte como está sendo a experiência."
- [ ] Anti-spam: no máximo 1 alerta por cliente por semana (usa lógica existente do proactive)
- [ ] Campo `alert_sent` marcado como `true` após envio bem-sucedido

### AC-5 — Endpoint de consulta

- [ ] `GET /client-lifecycle/health/{client_id}` retorna último score calculado
- [ ] Resposta: `{ client_id, score, risk_level, signals, calculated_at, days_since_calculation }`
- [ ] 404 quando cliente não existe
- [ ] Endpoint protegido por `RUNTIME_API_KEY`

### AC-6 — Graceful degradation

- [ ] Se `zenya_events` não tem dados suficientes (<7 dias de histórico), sinal `volume_mensagens` retorna score neutro (50) sem falhar
- [ ] Se pagamento não localizado na tabela correspondente, sinal `pagamento_em_dia` retorna 50 (incerto) com log de warning
- [ ] Score é calculado mesmo que 1-2 sinais estejam indisponíveis

---

## Definition of Done

- [ ] Todos os ACs passando
- [ ] `SELECT * FROM client_health ORDER BY calculated_at DESC LIMIT 10` retorna dados reais dos 6 clientes
- [ ] Pelo menos 1 alerta Friday disparado em cliente com score < 60 (ou mock test validado)
- [x] `pytest tests/unit/test_health_score.py` passa sem erros (36/36)
- [ ] @qa validou smoke test do endpoint e do cron
- [ ] @devops deployou no VPS

---

## Tarefas Técnicas

- [x] **T1:** Migration `020_client_health.sql` — tabela `client_health` já existe no Supabase (verificado via information_schema)
- [x] **T2:** `runtime/client_health/calculator.py` já existe com `calculate_health_score()` e os 5 sinais completos
- [x] **T3:** `runtime/client_health/router.py` já existe com endpoint `GET /health/{client_id}` funcional
- [x] **T4:** `main.py` já inclui o router em `/health`
- [x] **T5:** Job `client_health_weekly` adicionado em `scheduler.py` (segunda às 09h BRT)
- [x] **T6:** Triggers `client_health_alert`, `follow_up_due`, `payment_risk`, `workflow_blocked` adicionados em `proactive.py`
- [x] **T7:** 36 testes unitários criados em `tests/unit/test_health_score.py` — 36/36 passando
- [ ] **T8:** Executar cron manualmente via endpoint ou script para validar com dados reais (pós-deploy)

---

## Dependências

**Esta story depende de:**
- Tabela `zenya_events` com dados de telemetria (já existe)
- Friday `proactive.py` funcional (já existe)
- `scheduler.py` com APScheduler (já existe)

**Esta story desbloqueia:**
- W2-CLC-2 (relatório semanal usa Health Score calculado)
- W2-FRIDAY-2 (trigger `client_health_alert` faz parte dos triggers de negócio)

---

## Pipeline AIOS

| Etapa | Agente | Entrega |
|-------|--------|---------|
| Implementação | @dev | health_score.py + migration + cron + trigger + testes |
| Validação | @qa | Smoke test endpoint + cron + alerta Friday |
| Deploy | @devops | Deploy VPS + confirmação cron ativo |

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `runtime/client_health/calculator.py` | Já existia | Cálculo Health Score 5 sinais — completo |
| `runtime/client_health/router.py` | Já existia | Endpoints GET /health/{id} — completo |
| `runtime/main.py` | Já incluía | Router client_health registrado em /health |
| `runtime/scheduler.py` | Modificado | Cron client_health_weekly (segunda 09h BRT) |
| `runtime/friday/proactive.py` | Modificado | 4 business triggers: client_health_alert, follow_up_due, payment_risk, workflow_blocked |
| `tests/unit/test_health_score.py` | Criado | 36 testes unitários — 36/36 passando |
