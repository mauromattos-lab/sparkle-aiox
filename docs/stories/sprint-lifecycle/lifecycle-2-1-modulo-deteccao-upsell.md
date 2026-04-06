---
epic: EPIC-CLIENT-LIFECYCLE — Gestão do Ciclo de Vida do Cliente
story: LIFECYCLE-2.1
title: "Módulo de Detecção de Upsell (Fase 5)"
status: NEEDS_FIX
priority: Alta
executor: "@dev (implementação)"
sprint: Client Lifecycle Wave 2
prd: docs/prd/domain-client-lifecycle-prd.md
architecture: docs/architecture/domain-client-lifecycle-architecture.md
squad: squads/client-lifecycle/
depends_on: [LIFECYCLE-1.2, LIFECYCLE-1.4]
unblocks: [LIFECYCLE-3.3]
estimated_effort: 4-5h de agente (@dev)
---

# Story 2.1 — Módulo de Detecção de Upsell (Fase 5)

**Sprint:** Client Lifecycle Wave 2
**Status:** `DONE`
**Sequência:** 1 de 4
**PRD:** `docs/prd/domain-client-lifecycle-prd.md`
**Architecture:** `docs/architecture/domain-client-lifecycle-architecture.md`
**Squad:** `squads/client-lifecycle/`

---

## User Story

> Como Orion (orquestrador),
> quero detectar automaticamente oportunidades de upsell e cross-sell com base no health score e histórico do cliente,
> para que a Sparkle expanda receita de forma orgânica, sem depender de Mauro identificar oportunidades manualmente.

---

## Contexto técnico

**Dependência crítica:** Wave 1 deve estar completa — health scores precisam existir e estar sendo calculados semanalmente (`health_score_weekly` cron).

**Estado atual:** Não existe nenhum módulo de expansão. Oportunidades de upsell são identificadas manualmente por Mauro em conversas com clientes.

**Estado alvo:** Módulo `runtime/expansion/` com detecção automática semanal, scripts de abordagem pré-aprovados, e notificação para Friday quando oportunidade é detectada.

### Arquivos a criar

- `runtime/expansion/__init__.py` — module init
- `runtime/expansion/router.py` — FastAPI router com endpoints
- `runtime/expansion/detector.py` — lógica de detecção de oportunidades
- `runtime/expansion/scripts.py` — scripts de abordagem pré-aprovados por tipo de oportunidade

### Regras de detecção (detector.py)

| Condição | Tipo de oportunidade |
|----------|---------------------|
| health > 80 AND volume > 500 msgs/mês por 2+ meses consecutivos | `upgrade_tier` |
| Cliente tem Zenya MAS NÃO tem tráfego pago | `cross_sell_traffic` |
| Cliente tem tráfego pago MAS NÃO tem Zenya | `cross_sell_zenya` |

### Regras de veto (timing)

- **NUNCA** propor upsell nos primeiros 45 dias de contrato
- **NUNCA** propor upsell após reclamação registrada (enquanto não resolvida)
- **SOMENTE** propor após pelo menos 1 win documentado (milestone atingido ou health score subiu)

### Persistência

Tabela `upsell_opportunities` (migration 015):
- `id`, `client_id`, `opportunity_type`, `detected_at`, `health_score_at_detection`, `volume_at_detection`, `status` (detected/approached/converted/rejected/vetoed), `approach_script_used`, `approached_at`, `outcome_at`, `notes`

### Cron

- Nome: `upsell_detection_weekly`
- Horário: Segunda-feira 11h BRT (após `health_score_weekly`)
- Ação: executa detector para todos os clientes ativos

---

## Acceptance Criteria

- [ ] **AC1** — Detector identifica oportunidade `upgrade_tier` quando health > 80 e volume > 500/mês por 2+ meses
- [ ] **AC2** — Detector identifica oportunidade `cross_sell_traffic` quando cliente tem Zenya mas não tráfego
- [ ] **AC3** — Detector identifica oportunidade `cross_sell_zenya` quando cliente tem tráfego mas não Zenya
- [ ] **AC4** — Veto de timing funciona: cliente com < 45 dias de contrato NUNCA gera oportunidade
- [ ] **AC5** — Veto de reclamação funciona: cliente com reclamação aberta não gera oportunidade
- [ ] **AC6** — Veto de win funciona: cliente sem nenhum win documentado não gera oportunidade
- [ ] **AC7** — Scripts de abordagem existem para cada tipo de oportunidade em `scripts.py`
- [ ] **AC8** — Cron `upsell_detection_weekly` registrado e executando às segundas 11h BRT
- [ ] **AC9** — Oportunidades persistem na tabela `upsell_opportunities`
- [ ] **AC10** — Friday é notificada com contexto quando oportunidade é detectada
- [ ] **AC11** — `GET /expansion/opportunities` retorna lista de oportunidades (filtros: status, client_id, type)
- [ ] **AC12** — `POST /expansion/{client_id}/approach` registra abordagem e retorna script apropriado

---

## Integration Verifications

- [ ] Health score engine (Wave 1) está funcional e gerando scores semanais
- [ ] Tabela `upsell_opportunities` existe (migration 015 aplicada)
- [ ] Friday notification endpoint está acessível
- [ ] Cron scheduler do Runtime aceita registro do novo cron
- [ ] Dados de serviços contratados por cliente estão acessíveis (Zenya sim/não, tráfego sim/não)

---

## File List

| Arquivo | Ação |
|---------|------|
| `runtime/expansion/__init__.py` | Criar |
| `runtime/expansion/router.py` | Criar |
| `runtime/expansion/detector.py` | Criar |
| `runtime/expansion/scripts.py` | Criar |
| `runtime/main.py` | Modificar (registrar router) |
| `runtime/cron/registry.py` | Modificar (registrar cron) |
