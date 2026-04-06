---
epic: EPIC-CLIENT-LIFECYCLE — Gestao do Ciclo de Vida do Cliente
story: LIFECYCLE-1.4
title: "Milestones e TTV Tracking"
status: DONE
priority: Alta
executor: "@dev (implementacao)"
sprint: Client Lifecycle Wave 1
prd: docs/prd/domain-client-lifecycle-prd.md
architecture: docs/architecture/domain-client-lifecycle-architecture.md
squad: squads/client-lifecycle/
depends_on: [LIFECYCLE-1.1]
unblocks: []
estimated_effort: 4-6h de agente (@dev)
---

# Story 1.4 — Milestones e TTV Tracking

**Sprint:** Client Lifecycle Wave 1
**Status:** `DONE`
**Sequência:** 4 de 4
**PRD:** `docs/prd/domain-client-lifecycle-prd.md`
**Architecture:** `docs/architecture/domain-client-lifecycle-architecture.md`
**Squad:** `squads/client-lifecycle/`

---

## User Story

> Como gestor da Sparkle,
> quero rastrear marcos importantes na jornada de cada cliente e medir o Time-to-Value (TTV),
> para que eu saiba exatamente quanto tempo leva ate o cliente extrair valor real da Zenya e possa otimizar o processo de onboarding.

---

## Contexto Tecnico

**Por que agora:** Sem milestones rastreados, nao sabemos se o cliente ja teve seu "aha moment", quanto tempo levou do contrato ate a primeira mensagem real, ou se o onboarding realmente gerou valor. TTV e a metrica mais importante para provar ROI do onboarding.

**Dependencia:** Story 1.1 (tabela `client_milestones` deve existir)

**Estado atual:**
- Modulo `runtime/onboarding/service.py` existe e gerencia o fluxo de onboarding
- Nao ha rastreamento de milestones
- Nao ha calculo de TTV
- Endpoint `GET /onboarding/{id}/status` retorna status do onboarding mas sem milestones

**Estado alvo:**
- Metodo `track_milestone()` adicionado ao service de onboarding
- 4 tipos de milestone rastreados
- TTV calculado automaticamente
- Endpoint de status extendido com milestones e TTV
- Mensagem de parabens enviada em marcos-chave

**Milestone Types:**

| Tipo | Trigger | Descricao |
|------|---------|-----------|
| `zenya_active` | Zenya responde primeira mensagem real | Zenya esta viva e funcionando |
| `first_real_message` | Primeira mensagem de um cliente real (nao teste) | Primeiro uso real do sistema |
| `first_week_report` | 7 dias apos zenya_active com volume > 0 | Primeira semana completa de operacao |
| `aha_moment_30d` | 30 dias apos zenya_active com health score >= 60 | Cliente atingiu valor sustentavel |

**TTV Calculation:**
- TTV = dias entre `contract_date` (de zenya_clients) e `achieved_at` do milestone `first_real_message`
- Armazenado no campo `ttv_days` do milestone `first_real_message`
- Se `first_real_message` ainda nao aconteceu, TTV = null

**Extensao do endpoint existente:**

```
GET /onboarding/{id}/status
```

Response atual + novos campos:
```json
{
    "...campos existentes...",
    "milestones": [
        {
            "type": "zenya_active",
            "achieved_at": "2026-04-01T14:30:00Z",
            "ttv_days": null
        },
        {
            "type": "first_real_message",
            "achieved_at": "2026-04-02T09:15:00Z",
            "ttv_days": 3
        }
    ],
    "ttv_days": 3
}
```

**Mensagens de parabens (via Z-API):**

No milestone `zenya_active` (para o gestor):
```
🎉 *Go-Live confirmado!*

A Zenya de {nome_cliente} esta ativa e respondendo!
Primeiro marco alcancado. 🚀
```

No milestone `first_real_message` (para o gestor):
```
🎯 *Primeiro contato real!*

{nome_cliente} recebeu a primeira mensagem real de um cliente.
TTV: {ttv_days} dias do contrato ao primeiro uso real.
```

---

## Acceptance Criteria

- [ ] **AC1** — Metodo `track_milestone(client_id, milestone_type, metadata)` adicionado ao service de onboarding
- [ ] **AC2** — Milestone types implementados: zenya_active, first_real_message, first_week_report, aha_moment_30d
- [ ] **AC3** — Milestones persistem na tabela `client_milestones` com todos os campos preenchidos
- [ ] **AC4** — Constraint UNIQUE(client_id, milestone_type) respeitado — mesmo milestone nao duplica
- [ ] **AC5** — TTV calculado corretamente: dias entre contract_date e first_real_message.achieved_at
- [ ] **AC6** — TTV armazenado no campo `ttv_days` do milestone `first_real_message`
- [ ] **AC7** — Endpoint `GET /onboarding/{id}/status` retorna array `milestones[]` e campo `ttv_days`
- [ ] **AC8** — Mensagem de parabens enviada via Z-API no milestone `zenya_active` (go-live)
- [ ] **AC9** — Mensagem de parabens enviada via Z-API no milestone `first_real_message` com TTV
- [ ] **AC10** — Milestones ja alcancados nao geram mensagem duplicada (idempotencia)

---

## Integration Verifications

- [ ] `track_milestone()` insere corretamente na tabela `client_milestones`
- [ ] Tentativa de inserir milestone duplicado nao gera erro (upsert ou catch de unique violation)
- [ ] TTV retorna null quando `first_real_message` ainda nao foi alcancado
- [ ] TTV retorna valor correto em dias (inteiro, arredondado para cima)
- [ ] Endpoint de status mantem backward compatibility (campos existentes inalterados)
- [ ] Z-API recebe chamada de envio com formato correto nas mensagens de parabens
- [ ] Metadata JSONB aceita dados arbitrarios sem falha
- [ ] Cliente sem nenhum milestone retorna `milestones: []` e `ttv_days: null`

---

## File List

| Arquivo | Acao |
|---------|------|
| `runtime/onboarding/service.py` | MODIFICAR (adicionar track_milestone) |
| `runtime/onboarding/router.py` | MODIFICAR (extender endpoint de status) |
| `runtime/client_health/calculator.py` | MODIFICAR (trigger aha_moment_30d) |
