---
epic: EPIC-CLIENT-LIFECYCLE — Gestão do Ciclo de Vida do Cliente
story: LIFECYCLE-2.3
title: "Tracking de Conversão (Fase 2)"
status: DONE
priority: Alta
executor: "@dev (implementação)"
sprint: Client Lifecycle Wave 2
prd: docs/prd/domain-client-lifecycle-prd.md
architecture: docs/architecture/domain-client-lifecycle-architecture.md
squad: squads/client-lifecycle/
depends_on: [LIFECYCLE-2.2]
unblocks: [LIFECYCLE-2.4]
estimated_effort: 3-4h de agente (@dev)
---

# Story 2.3 — Tracking de Conversão (Fase 2)

**Sprint:** Client Lifecycle Wave 2
**Status:** `DONE`
**Sequência:** 3 de 4
**PRD:** `docs/prd/domain-client-lifecycle-prd.md`
**Architecture:** `docs/architecture/domain-client-lifecycle-architecture.md`
**Squad:** `squads/client-lifecycle/`

---

## User Story

> Como Mauro (CEO),
> quero rastrear automaticamente o funil proposta→aceite com métricas de tempo e touchpoints,
> para que eu saiba exatamente onde o pipeline trava e possa otimizar o processo de conversão.

---

## Contexto técnico

**PRD ref:** F2-FR2 (tracking proposta→aceite)

**Estado atual:** Não existe tracking estruturado de conversão. Propostas são enviadas mas não há registro de quando foram enviadas, quando o cliente respondeu, ou quanto tempo levou para converter. Propostas esquecidas não são detectadas.

**Estado alvo:** Tracking completo com timestamps em cada etapa do funil, cálculo automático de métricas de conversão, detecção de propostas estagnadas, e endpoint de métricas agregadas.

### Timestamps a rastrear

| Campo | Descrição |
|-------|-----------|
| `proposal_sent_at` | Quando a proposta foi enviada |
| `first_response_at` | Quando o lead respondeu pela primeira vez após proposta |
| `contract_signed_at` | Quando o contrato foi assinado |

### Métricas calculadas

| Métrica | Cálculo |
|---------|---------|
| `time_to_first_response` | `first_response_at - proposal_sent_at` |
| `time_to_convert` | `contract_signed_at - proposal_sent_at` |
| `touchpoints_count` | Quantidade de interações entre proposta e assinatura |
| `channel_source` | Canal de origem do lead (Instagram, WhatsApp, indicação, etc.) |

### Detecção de propostas estagnadas

| Condição | Ação |
|----------|------|
| > 7 dias sem resposta após proposta | Dispara última tentativa de contato |
| > 10 dias sem resposta | Marca como `lost` com motivo `no_response` |

### Persistência

Estender tabela de leads ou criar view `conversion_tracking`:
- Campos de timestamp na tabela principal
- View agregada para métricas (média de conversão, taxa por canal, etc.)

### Endpoint

`GET /pipeline/conversion-metrics`
- Filtros: `period` (7d/30d/90d), `channel_source`, `status`
- Retorna: média `time_to_convert`, taxa de conversão, propostas ativas, propostas stale, breakdown por canal

---

## Acceptance Criteria

- [ ] **AC1** — `proposal_sent_at` é registrado automaticamente quando proposta é enviada
- [ ] **AC2** — `first_response_at` é registrado quando lead responde pela primeira vez após proposta
- [ ] **AC3** — `contract_signed_at` é registrado quando contrato é assinado
- [ ] **AC4** — `time_to_convert` é calculado corretamente (diferença entre envio e assinatura)
- [ ] **AC5** — `touchpoints_count` é incrementado a cada interação pós-proposta
- [ ] **AC6** — `channel_source` é rastreado e associado ao lead
- [ ] **AC7** — Proposta com > 7 dias sem resposta dispara última tentativa de contato
- [ ] **AC8** — Proposta com > 10 dias sem resposta é marcada como `lost`
- [ ] **AC9** — `GET /pipeline/conversion-metrics` retorna dados agregados com filtros funcionais
- [ ] **AC10** — Métricas incluem: média time_to_convert, taxa de conversão, breakdown por canal

---

## Integration Verifications

- [ ] Pipeline de leads existente registra envio de proposta (ou pode ser estendido para registrar)
- [ ] Webhook ou listener de Z-API captura respostas de leads para registrar `first_response_at`
- [ ] Tabela de leads suporta novos campos de timestamp (ou migration adicional necessária)
- [ ] Fluxo de assinatura de contrato tem ponto de integração para registrar `contract_signed_at`

---

## File List

| Arquivo | Ação |
|---------|------|
| `runtime/pipeline/conversion.py` | Criar (tracking e métricas) |
| `runtime/pipeline/router.py` | Modificar (adicionar endpoint /conversion-metrics) |
| `runtime/pipeline/stale_detector.py` | Criar (detecção de propostas estagnadas) |
| `runtime/main.py` | Modificar (se necessário) |
