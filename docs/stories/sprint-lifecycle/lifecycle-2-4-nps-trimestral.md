---
epic: EPIC-CLIENT-LIFECYCLE — Gestão do Ciclo de Vida do Cliente
story: LIFECYCLE-2.4
title: "NPS Trimestral (Fase 6)"
status: DONE
priority: Média
executor: "@dev (implementação)"
sprint: Client Lifecycle Wave 2
prd: docs/prd/domain-client-lifecycle-prd.md
architecture: docs/architecture/domain-client-lifecycle-architecture.md
squad: squads/client-lifecycle/
depends_on: [LIFECYCLE-1.1]
unblocks: [LIFECYCLE-3.4]
estimated_effort: 3-4h de agente (@dev)
---

# Story 2.4 — NPS Trimestral (Fase 6)

**Sprint:** Client Lifecycle Wave 2
**Status:** `DONE`
**Sequência:** 4 de 4
**PRD:** `docs/prd/domain-client-lifecycle-prd.md`
**Architecture:** `docs/architecture/domain-client-lifecycle-architecture.md`
**Squad:** `squads/client-lifecycle/`

---

## User Story

> Como Sparkle (sistema de advocacy),
> quero coletar NPS trimestralmente via WhatsApp e acionar fluxos automáticos com base na classificação,
> para que promotores gerem indicações, detratores sejam tratados antes de churnar, e eu tenha uma métrica real de satisfação.

---

## Contexto técnico

**Estado atual:** Não existe nenhuma coleta estruturada de NPS. Satisfação do cliente é percebida informalmente por Mauro em conversas.

**Estado alvo:** Módulo `runtime/advocacy/` com coleta automática via WhatsApp, classificação NPS, fluxos diferenciados por score, e cálculo de NPS global.

### Arquivos a criar

- `runtime/advocacy/__init__.py` — module init
- `runtime/advocacy/router.py` — FastAPI router com endpoints
- `runtime/advocacy/nps.py` — lógica de coleta, classificação e fluxos

### Coleta via WhatsApp (Z-API)

Mensagem enviada: "Oi [nome]! De 0 a 10, o quanto você recomendaria a Sparkle para um amigo ou colega? Responda com o número."

**Regras de elegibilidade** (TODAS devem ser verdadeiras):
- Cliente ativo há > 30 dias
- Último NPS coletado há 80+ dias (ou nunca coletado)
- Cliente NÃO está em intervenção de churn (success-guardian ativo)
- Onboarding completo (milestone onboarding_complete atingido)

### Classificação e fluxos

| Score | Classificação | Ação automática |
|-------|--------------|-----------------|
| 9-10 | Promoter | Enviar proposta de indicação com benefício |
| 7-8 | Passive | Perguntar "O que podemos melhorar?" |
| 0-6 | Detractor | Escalar para success-guardian. **ZERO ofertas comerciais.** |

### Cálculo NPS global

```
NPS = %Promoters - %Detractors
```

Calculado sobre todos os clientes que responderam nos últimos 90 dias.

### Persistência

Tabela `client_nps`:
- `id`, `client_id`, `score`, `classification` (promoter/passive/detractor), `collected_at`, `feedback_text`, `follow_up_action`, `follow_up_completed_at`

### Cron

- Nome: `nps_quarterly`
- Horário: 1o dia de cada trimestre (Jan/Abr/Jul/Out), 10h BRT
- Ação: identifica clientes elegíveis e envia pesquisa

### Endpoints

| Método | Path | Descrição |
|--------|------|-----------|
| `GET` | `/advocacy/nps/{client_id}` | Histórico NPS do cliente |
| `POST` | `/advocacy/nps/collect` | Dispara coleta para clientes elegíveis |
| `GET` | `/advocacy/promoters` | Lista de promoters ativos (para campanhas de indicação) |

---

## Acceptance Criteria

- [ ] **AC1** — Pesquisa NPS é enviada via Z-API (WhatsApp) com mensagem padronizada
- [ ] **AC2** — Regras de elegibilidade são verificadas: > 30 dias ativo, > 80 dias desde último NPS, sem intervenção churn, onboarding completo
- [ ] **AC3** — Cliente não-elegível NÃO recebe pesquisa (todas as 4 regras checadas)
- [ ] **AC4** — Resposta numérica é parseada corretamente (0-10)
- [ ] **AC5** — Score 9-10 classificado como Promoter → dispara proposta de indicação
- [ ] **AC6** — Score 7-8 classificado como Passive → dispara pergunta de melhoria
- [ ] **AC7** — Score 0-6 classificado como Detractor → escala para success-guardian, SEM ofertas comerciais
- [ ] **AC8** — Cron `nps_quarterly` registrado e executa no 1o dia de cada trimestre às 10h BRT
- [ ] **AC9** — Respostas persistem na tabela `client_nps`
- [ ] **AC10** — NPS global calculado corretamente: %Promoters - %Detractors
- [ ] **AC11** — `GET /advocacy/nps/{client_id}` retorna histórico NPS do cliente
- [ ] **AC12** — `GET /advocacy/promoters` retorna lista de promoters ativos

---

## Integration Verifications

- [ ] Z-API está acessível para envio e recebimento de mensagens WhatsApp
- [ ] Webhook de resposta WhatsApp captura respostas numéricas e associa ao NPS pendente
- [ ] Tabela `client_nps` existe (migration necessária se não existir)
- [ ] Milestones de onboarding estão rastreados (dependência Wave 1 Story 1.4)
- [ ] Success-guardian (intervenção churn) tem status consultável para checagem de elegibilidade
- [ ] Cron scheduler aceita registro trimestral

---

## File List

| Arquivo | Ação |
|---------|------|
| `runtime/advocacy/__init__.py` | Criar |
| `runtime/advocacy/router.py` | Criar |
| `runtime/advocacy/nps.py` | Criar |
| `runtime/main.py` | Modificar (registrar router) |
| `runtime/cron/registry.py` | Modificar (registrar cron trimestral) |
