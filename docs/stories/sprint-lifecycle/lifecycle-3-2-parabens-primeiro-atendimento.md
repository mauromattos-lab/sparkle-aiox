---
epic: EPIC-CLIENT-LIFECYCLE — Gestão do Ciclo de Vida do Cliente
story: LIFECYCLE-3.2
title: "Parabéns no Primeiro Atendimento Real (Fase 3)"
status: DONE
priority: Alta
executor: "@dev (implementação)"
sprint: Client Lifecycle Wave 3
prd: docs/prd/domain-client-lifecycle-prd.md
architecture: docs/architecture/domain-client-lifecycle-architecture.md
squad: squads/client-lifecycle/
depends_on: [LIFECYCLE-2.x (Wave 2 completa), LIFECYCLE-1.4 (milestones)]
unblocks: [LIFECYCLE-3.4]
estimated_effort: 2-3h de agente (@dev)
---

# Story 3.2 — Parabéns no Primeiro Atendimento Real (Fase 3)

**Sprint:** Client Lifecycle Wave 3
**Status:** `DONE`
**Sequência:** 2 de 4
**PRD:** `docs/prd/domain-client-lifecycle-prd.md`
**Architecture:** `docs/architecture/domain-client-lifecycle-architecture.md`
**Squad:** `squads/client-lifecycle/`

---

## User Story

> Como cliente da Sparkle que acabou de ter seu primeiro atendimento real via Zenya,
> quero receber uma mensagem de parabéns celebrando esse marco,
> para que eu me sinta valorizado e confiante de que o investimento está funcionando.

---

## Contexto Técnico

**Por que agora:** O primeiro atendimento real é o momento de maior validação emocional para o cliente. Celebrar esse marco automaticamente reforça o valor percebido, reduz churn precoce e cria um touchpoint positivo sem custo operacional para Mauro.

**Estado atual:**
- Eventos de atendimento Zenya já são registrados em `zenya_events` (ou tabela equivalente)
- Milestones são rastreados em `client_milestones` (Wave 1 — Story 1.4)
- Z-API está funcional para envio de mensagens
- Friday está funcional como interface com Mauro
- Não existe detecção de "primeiro atendimento real" vs mensagens de teste/internas

**PRD ref:** F3-FR2 (webhook Z-API detecta 1a mensagem real)

**Dependências:**
- `zenya_events` populada com eventos de atendimento
- `client_milestones` disponível para registro (Story 1.4)
- Z-API funcional para envio de mensagens
- Friday funcional para notificação de Mauro

**Decisão de design:**
- "Mensagem real" = mensagem de um número que NÃO é do cliente dono, NÃO é de números internos Sparkle, NÃO contém padrões de teste ("teste", "testing", "oi é teste")
- TTV (Time-to-Value) = dias entre `contract_start_date` e `first_real_message_date`
- Milestone `first_real_message` registrado com timestamp e TTV calculado

**Templates de mensagem:**

Para o cliente:
```
Parabéns {nome}! Sua {nome_zenya} acabou de atender o primeiro cliente! 
Em {ttv} dias do contrato ao primeiro atendimento real. Isso é incrível! 🎉
```

Para Mauro (via Friday):
```
{cliente} teve primeiro atendimento real! TTV = {ttv} dias.
```

---

## Acceptance Criteria

- [ ] **AC1** — Sistema detecta corretamente a primeira mensagem REAL em `zenya_events`, excluindo: mensagens de teste, mensagens internas, mensagens do próprio cliente dono
- [ ] **AC2** — Mensagem de parabéns é enviada ao cliente dono via Z-API com nome personalizado, nome da Zenya e TTV calculado
- [ ] **AC3** — Friday notifica Mauro com nome do cliente e TTV em dias
- [ ] **AC4** — Milestone `first_real_message` é registrado em `client_milestones` com timestamp, TTV e metadata do atendimento
- [ ] **AC5** — TTV é calculado corretamente como diferença em dias entre `contract_start_date` e data da primeira mensagem real
- [ ] **AC6** — Detecção não dispara para mensagens de teste (regex de padrões comuns: "teste", "testing", "oi é teste", números internos)
- [ ] **AC7** — Se milestone `first_real_message` já existe para o cliente, não dispara novamente (idempotência)

---

## Integration Verifications

- [ ] `zenya_events` contém eventos com dados suficientes para distinguir mensagem real de teste (remetente, conteúdo, metadata)
- [ ] `client_milestones` aceita registro de `first_real_message` com campos TTV e metadata
- [ ] Z-API envia mensagem de parabéns formatada corretamente — testar com número de teste
- [ ] Friday recebe e exibe notificação de TTV para Mauro
- [ ] Listener/webhook está ativo e processando eventos de `zenya_events` em tempo real ou near-real-time
- [ ] Números internos Sparkle estão configurados em lista de exclusão

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `runtime/lifecycle/first_message_detector.py` | Criar | Detector de primeira mensagem real |
| `runtime/lifecycle/congratulations.py` | Criar | Engine de envio de parabéns + notificação Friday |
| `runtime/lifecycle/exclusion_patterns.py` | Criar | Padrões de exclusão (teste, internos) |
| `migrations/XXX_first_message_milestone.sql` | Criar | Índice e constraints para milestone first_real_message |
| `tests/test_first_message_detector.py` | Criar | Testes: real vs teste vs interno |
| `tests/test_congratulations.py` | Criar | Testes: envio, idempotência, TTV |
