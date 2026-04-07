---
epic: EPIC-CLIENT-LIFECYCLE — Gestão do Ciclo de Vida do Cliente
story: LIFECYCLE-2.2
title: "Routing de Leads Médio/Baixo (Fase 1)"
status: DONE
priority: Alta
executor: "@dev (implementação)"
sprint: Client Lifecycle Wave 2
prd: docs/prd/domain-client-lifecycle-prd.md
architecture: docs/architecture/domain-client-lifecycle-architecture.md
squad: squads/client-lifecycle/
depends_on: [LIFECYCLE-1.1]
unblocks: [LIFECYCLE-2.3]
estimated_effort: 4-5h de agente (@dev)
---

# Story 2.2 — Routing de Leads Médio/Baixo (Fase 1)

**Sprint:** Client Lifecycle Wave 2
**Status:** `DONE`
**Sequência:** 2 de 4
**PRD:** `docs/prd/domain-client-lifecycle-prd.md`
**Architecture:** `docs/architecture/domain-client-lifecycle-architecture.md`
**Squad:** `squads/client-lifecycle/`

---

## User Story

> Como Sparkle (sistema de vendas),
> quero rotear automaticamente leads de temperatura média e baixa para sequências de nurturing adequadas,
> para que nenhum lead seja perdido por falta de follow-up e Mauro só gaste tempo com leads HOT.

---

## Contexto técnico

**PRD ref:** F1-FR1 (routing automático por score BANT)

**Estado atual:** Apenas leads HOT (BANT >= 80) recebem atenção — proposta em 24h e notificação para Friday. Leads com BANT 40-79 (WARM) e BANT < 40 (COLD) ficam sem follow-up e são perdidos.

**Estado alvo:** Pipeline completo com 3 trilhas de routing automático, sequências de nurturing pré-configuradas, e re-qualificação automática de leads que aquecem.

### Trilhas de routing

| BANT Score | Temperatura | Ação |
|-----------|-------------|------|
| >= 80 | HOT | Proposta em 24h + Friday notification (JÁ EXISTE) |
| 40-79 | WARM | Sequência nurturing 3-5 dias com conteúdo de nicho |
| < 40 | COLD | Auto-nurturing longo, zero tempo de Mauro |

### Sequências de nurturing

**WARM (3-5 dias):**
- Dia 0: Case study relevante do nicho do lead
- Dia 2: Comparativo antes/depois de cliente similar
- Dia 5: Re-qualificação (perguntas BANT atualizadas)

**COLD (nurturing passivo):**
- Dia 0: Conteúdo educativo genérico sobre IA para negócios
- Dia 7: Segundo conteúdo educativo
- Dia 14: Re-qualificação leve (1 pergunta)
- Se não responde → arquivar após 30 dias

### Tracking de temperatura

Registrar mudanças de temperatura ao longo do tempo:
- `lead_id`, `previous_temp`, `new_temp`, `changed_at`, `trigger` (re-qualification/manual/new-info)
- Se WARM → HOT: notificar Friday imediatamente
- Se COLD → WARM: iniciar sequência WARM

### Arquivos

- `runtime/pipeline/nurturing.py` — Criar (lógica de sequências e routing WARM/COLD)
- Estender handler existente em `runtime/pipeline/` para integrar as novas trilhas

---

## Acceptance Criteria

- [ ] **AC1** — Lead com BANT 40-79 é roteado automaticamente para trilha WARM
- [ ] **AC2** — Lead com BANT < 40 é roteado automaticamente para trilha COLD
- [ ] **AC3** — Sequência WARM dispara: dia 0 (case study), dia 2 (comparativo), dia 5 (re-qualify)
- [ ] **AC4** — Sequência COLD dispara: dia 0, dia 7, dia 14 (re-qualify leve), dia 30 (arquivar)
- [ ] **AC5** — Re-qualificação recalcula BANT e pode mudar temperatura do lead
- [ ] **AC6** — Mudança WARM → HOT notifica Friday imediatamente
- [ ] **AC7** — Mudança COLD → WARM inicia sequência WARM automaticamente
- [ ] **AC8** — Histórico de mudanças de temperatura é persistido
- [ ] **AC9** — Lead HOT continua funcionando como antes (sem regressão)
- [ ] **AC10** — Mensagens de nurturing são enviadas via Z-API (WhatsApp)

---

## Integration Verifications

- [ ] Pipeline de leads existente (HOT path) não sofre regressão
- [ ] Z-API está acessível para envio de mensagens de nurturing
- [ ] Templates de conteúdo por nicho existem ou têm fallback genérico
- [ ] Tabela de leads suporta campos de temperatura e histórico
- [ ] Cron ou event trigger existe para disparar mensagens nos dias corretos

---

## File List

| Arquivo | Ação |
|---------|------|
| `runtime/pipeline/nurturing.py` | Criar |
| `runtime/pipeline/router.py` | Modificar (integrar routing WARM/COLD) |
| `runtime/pipeline/templates/` | Criar (templates de nurturing por nicho) |
| `runtime/main.py` | Modificar (se necessário registrar novos endpoints) |
