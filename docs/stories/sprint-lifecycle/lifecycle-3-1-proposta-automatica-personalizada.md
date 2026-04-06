---
epic: EPIC-CLIENT-LIFECYCLE — Gestão do Ciclo de Vida do Cliente
story: LIFECYCLE-3.1
title: "Proposta Automática Personalizada (Fase 2)"
status: NEEDS_FIX
priority: Alta
executor: "@dev (implementação) + @architect (template engine design)"
sprint: Client Lifecycle Wave 3
prd: docs/prd/domain-client-lifecycle-prd.md
architecture: docs/architecture/domain-client-lifecycle-architecture.md
squad: squads/client-lifecycle/
depends_on: [LIFECYCLE-2.x (Wave 2 completa)]
unblocks: [LIFECYCLE-3.2, LIFECYCLE-3.3]
estimated_effort: 4-5h de agente (@dev)
---

# Story 3.1 — Proposta Automática Personalizada (Fase 2)

**Sprint:** Client Lifecycle Wave 3
**Status:** `NEEDS_FIX`
**Sequência:** 1 de 4
**PRD:** `docs/prd/domain-client-lifecycle-prd.md`
**Architecture:** `docs/architecture/domain-client-lifecycle-architecture.md`
**Squad:** `squads/client-lifecycle/`

---

## User Story

> Como Mauro (CEO da Sparkle),
> quero que propostas comerciais sejam geradas automaticamente com base nos dados BANT do lead e no nicho de atuação,
> para que eu pare de criar propostas manualmente e possa apenas revisar/aprovar antes do envio.

---

## Contexto Técnico

**Por que agora:** Atualmente Mauro cria cada proposta manualmente, consumindo tempo que deveria ir para estratégia. Com os dados de BANT (Budget, Authority, Need, Timeline) já coletados nas Waves anteriores e o contexto do lead no Brain, o sistema tem tudo que precisa para gerar propostas personalizadas automaticamente.

**Estado atual:**
- Propostas são criadas manualmente por Mauro
- Dados BANT já são coletados no pipeline de leads (Wave 1-2)
- Brain já possui contexto de nicho e histórico de clientes similares
- Z-API já está integrado para envio de mensagens WhatsApp
- Friday já é interface de comunicação com Mauro

**PRD ref:** F2-FR1 (geração automática de proposta)

**Dependências:**
- Wave 2 completa (dados BANT estruturados, pipeline de leads funcional)
- Brain namespace `sparkle-ops` com dados de clientes por nicho
- Templates de proposta por nicho configurados
- Z-API funcional para envio

**Decisão de design:**
- Templates por nicho: confeitaria, escola, ótica, ecommerce, clínica, consultório, varejo genérico
- Cada template inclui: saudação personalizada, dor endereçada, features Zenya relevantes ao nicho, preço, case de cliente similar
- Proposta pode ser entregue via WhatsApp (Z-API) ou link PDF
- Friday faz preview para Mauro antes do envio (approve/edit flow)

---

## Acceptance Criteria

- [ ] **AC1** — Proposta é gerada automaticamente a partir dos dados BANT do lead (budget, authority, need, timeline) sem intervenção manual
- [ ] **AC2** — Template de nicho correto é aplicado (confeitaria, escola, ótica, ecommerce, etc.) com features Zenya relevantes para aquele segmento
- [ ] **AC3** — Case study de cliente similar (mesmo nicho ou nicho próximo) é incluído na proposta automaticamente, puxado do Brain
- [ ] **AC4** — Friday exibe preview da proposta para Mauro com opções de aprovar, editar ou rejeitar antes do envio
- [ ] **AC5** — Proposta é enviada ao lead via Z-API (WhatsApp) ou como link PDF, conforme preferência configurada
- [ ] **AC6** — Proposta gerada é registrada no histórico do lead com timestamp, versão e status (enviada/aprovada/rejeitada)
- [ ] **AC7** — Se Mauro edita a proposta, a versão editada é salva como novo template candidato para o nicho (aprendizado contínuo)

---

## Integration Verifications

- [ ] Brain retorna contexto de nicho e cases de clientes similares via namespace `sparkle-ops`
- [ ] Dados BANT do lead estão completos e acessíveis na tabela `leads` ou `lead_qualification`
- [ ] Z-API envia mensagem formatada (WhatsApp) sem erro — testar com número de teste, NUNCA com lead real
- [ ] Friday recebe e exibe preview corretamente — Mauro consegue aprovar/editar/rejeitar
- [ ] PDF é gerado corretamente quando opção PDF é selecionada
- [ ] Templates de pelo menos 3 nichos existentes (confeitaria, escola, ótica) estão configurados e testados

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `runtime/expansion/proposals.py` | Criar | Engine de geração de propostas |
| `runtime/expansion/templates/` | Criar | Diretório com templates por nicho |
| `runtime/expansion/templates/confeitaria.md` | Criar | Template proposta — nicho confeitaria |
| `runtime/expansion/templates/escola.md` | Criar | Template proposta — nicho escola |
| `runtime/expansion/templates/otica.md` | Criar | Template proposta — nicho ótica |
| `runtime/expansion/templates/ecommerce.md` | Criar | Template proposta — nicho ecommerce |
| `runtime/expansion/templates/generic.md` | Criar | Template proposta — fallback genérico |
| `migrations/XXX_proposal_history.sql` | Criar | Tabela de histórico de propostas |
| `tests/test_proposals.py` | Criar | Testes unitários da engine de propostas |
