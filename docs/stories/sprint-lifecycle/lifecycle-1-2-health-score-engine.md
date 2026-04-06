---
epic: EPIC-CLIENT-LIFECYCLE — Gestao do Ciclo de Vida do Cliente
story: LIFECYCLE-1.2
title: "Health Score Engine"
status: DONE
priority: Alta
executor: "@dev (implementacao)"
sprint: Client Lifecycle Wave 1
prd: docs/prd/domain-client-lifecycle-prd.md
architecture: docs/architecture/domain-client-lifecycle-architecture.md
squad: squads/client-lifecycle/
depends_on: [LIFECYCLE-1.1]
unblocks: [LIFECYCLE-1.3]
estimated_effort: 6-8h de agente (@dev)
---

# Story 1.2 — Health Score Engine

**Sprint:** Client Lifecycle Wave 1
**Status:** `DONE`
**Sequência:** 2 de 4
**PRD:** `docs/prd/domain-client-lifecycle-prd.md`
**Architecture:** `docs/architecture/domain-client-lifecycle-architecture.md`
**Squad:** `squads/client-lifecycle/`

---

## User Story

> Como gestor da Sparkle,
> quero que o sistema calcule automaticamente um health score para cada cliente com base em sinais objetivos,
> para que eu saiba quais clientes estao saudaveis, quais precisam de atencao e quais estao em risco de churn.

---

## Contexto Tecnico

**Por que agora:** Sem health score, a gestao de clientes e reativa — so sabemos que algo vai mal quando o cliente reclama ou cancela. O health score transforma gestao de clientes em proativa.

**Dependencia:** Story 1.1 (tabela `client_health` deve existir)

**Estado atual:**
- Nao existe modulo `runtime/client_health/`
- Nao ha calculo automatizado de saude do cliente
- Dados de volume, pagamento e acesso existem espalhados em tabelas diversas

**Estado alvo:**
- Modulo `runtime/client_health/` com router, calculator e __init__
- 4 endpoints REST funcionais
- Cron semanal registrado
- Formula de health score com 5 sinais ponderados

**Modulo a criar:** `runtime/client_health/`

```
runtime/client_health/
    __init__.py
    router.py        # FastAPI endpoints
    calculator.py    # Logica de calculo do health score
```

**Formula do Health Score (5 sinais ponderados):**

| Sinal | Peso | Descricao | Score 100 | Score 0 |
|-------|------|-----------|-----------|---------|
| volume | 30% | Msgs processadas pela Zenya nos ultimos 7 dias | >= media historica | 0 msgs |
| payment | 25% | Status do pagamento | Em dia | Inadimplente 30d+ |
| access | 20% | Ultimo acesso/interacao do cliente | Ultimos 3 dias | 30d+ sem acesso |
| support | 15% | Tickets/reclamacoes abertos | 0 tickets | 3+ tickets abertos |
| checkin | 10% | Respondeu ultimo checkin | Respondeu | Ignorou 2+ checkins |

**Classificacao:**
- 80-100: `healthy` (verde)
- 60-79: `attention` (amarelo)
- 40-59: `risk` (laranja)
- 0-39: `critical` (vermelho)

**Endpoints:**

```
GET  /health/{client_id}           — Score atual do cliente
GET  /health/all                   — Score de todos os clientes (dashboard)
POST /health/recalculate           — Forca recalculo de todos
GET  /health/{client_id}/history   — Historico de scores do cliente
```

**Cron:**
- `health_score_weekly`: executa toda segunda-feira as 08h BRT
- Recalcula score de TODOS os clientes ativos
- Persiste resultado na tabela `client_health`

**Registro no main.py:**
- Importar e registrar o router: `app.include_router(client_health_router, prefix="/health", tags=["client-health"])`
- Registrar cron no scheduler existente

---

## Acceptance Criteria

- [ ] **AC1** — Modulo `runtime/client_health/` criado com `__init__.py`, `router.py`, `calculator.py`
- [ ] **AC2** — Endpoint `GET /health/{client_id}` retorna score atual, classificacao e sinais do cliente
- [ ] **AC3** — Endpoint `GET /health/all` retorna lista de todos os clientes com seus scores e classificacoes
- [ ] **AC4** — Endpoint `POST /health/recalculate` forca recalculo de todos os clientes e retorna resumo
- [ ] **AC5** — Endpoint `GET /health/{client_id}/history` retorna historico de scores com paginacao
- [ ] **AC6** — Formula de calculo usa os 5 sinais com pesos corretos: volume 30%, payment 25%, access 20%, support 15%, checkin 10%
- [ ] **AC7** — Classificacao correta: 80-100 healthy, 60-79 attention, 40-59 risk, 0-39 critical
- [ ] **AC8** — Cron `health_score_weekly` registrado para segunda-feira 08h BRT
- [ ] **AC9** — Resultado do calculo persiste na tabela `client_health` com todos os campos preenchidos
- [ ] **AC10** — Router registrado no `main.py` com prefix `/health`

---

## Integration Verifications

- [ ] Endpoints respondem com status 200 e JSON valido
- [ ] Score calculado esta entre 0 e 100
- [ ] Classificacao corresponde corretamente ao range do score
- [ ] Cron aparece na lista de crons registrados (`GET /system/crons`)
- [ ] Dados persistem corretamente na tabela `client_health`
- [ ] Client inexistente retorna 404 nos endpoints com `{client_id}`
- [ ] `GET /health/all` funciona mesmo sem nenhum score calculado (retorna lista vazia)
- [ ] Recalculo nao duplica registros — cria novo registro por calculo (historico)

---

## File List

| Arquivo | Acao |
|---------|------|
| `runtime/client_health/__init__.py` | CRIAR |
| `runtime/client_health/router.py` | CRIAR |
| `runtime/client_health/calculator.py` | CRIAR |
| `main.py` | MODIFICAR (registrar router e cron) |
