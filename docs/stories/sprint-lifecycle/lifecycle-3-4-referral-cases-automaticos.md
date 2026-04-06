---
epic: EPIC-CLIENT-LIFECYCLE — Gestão do Ciclo de Vida do Cliente
story: LIFECYCLE-3.4
title: "Programa de Referral e Cases Automáticos (Fase 6)"
status: NEEDS_FIX
priority: Média
executor: "@dev (implementação) + @analyst (estrutura de cases)"
sprint: Client Lifecycle Wave 3
prd: docs/prd/domain-client-lifecycle-prd.md
architecture: docs/architecture/domain-client-lifecycle-architecture.md
squad: squads/client-lifecycle/
depends_on: [LIFECYCLE-2.x (Wave 2 completa), LIFECYCLE-1.2 (health score), LIFECYCLE-3.3 (scripts)]
unblocks: []
estimated_effort: 5-6h de agente (@dev + @analyst)
---

# Story 3.4 — Programa de Referral e Cases Automáticos (Fase 6)

**Sprint:** Client Lifecycle Wave 3
**Status:** `NEEDS_FIX`
**Sequência:** 4 de 4
**PRD:** `docs/prd/domain-client-lifecycle-prd.md`
**Architecture:** `docs/architecture/domain-client-lifecycle-architecture.md`
**Squad:** `squads/client-lifecycle/`

---

## User Story

> Como Sparkle (sistema),
> quero identificar promotores (NPS 9-10) para propor referral com desconto mútuo e gerar cases automaticamente a partir de métricas reais de clientes saudáveis,
> para que o crescimento orgânico seja sistematizado e o material de vendas se construa sozinho.

---

## Contexto Técnico

**Por que agora:** Com health score, milestones e NPS já funcionando, o sistema tem dados suficientes para identificar quem são os promotores e quais clientes têm histórias de sucesso documentáveis. Automatizar referral e cases fecha o flywheel de crescimento: cliente feliz gera referral que gera novo cliente que gera novo case.

**Estado atual:**
- NPS é coletado (Wave 1-2) mas não aciona nenhuma ação automática
- Referrals são informais (boca a boca) sem tracking
- Cases são inexistentes — Mauro não tem tempo de criar
- Brain tem namespace `sparkle-ops` para armazenamento de conhecimento operacional

**PRD refs:** F6-FR2 (referral), F6-FR3 (cases automáticos)

**Dependências:**
- Health score funcional (Story 1.2)
- NPS coletado e armazenado (Wave 2)
- Brain namespace `sparkle-ops` acessível
- Scripts de referral (Story 3.3)
- Z-API para envio de propostas

---

### Parte A — Programa de Referral

**Mecânica:**
- Clientes com NPS 9-10 (promotores) recebem proposta de referral
- Incentivo: 10% de desconto para quem indica (referrer) E para o indicado (referred)
- Tracking completo: quem indicou, quem foi indicado, status da conversão
- Desconto aplicado automaticamente quando indicado converte

**Dados necessários:**
- Extensão da tabela `leads` com campo `referred_by` (FK para `clients`)
- Tabela `referrals` com: referrer_id, referred_lead_id, status (proposed/accepted/converted/expired), discount_applied, created_at

### Parte B — Cases Automáticos

**Critérios para geração de case:**
- Health score > 70 por 6+ meses consecutivos
- Cliente autorizou uso de dados (flag `case_authorized` em `clients`)

**Dados do case (puxados automaticamente):**
- Métricas before/after: volume de atendimentos, TTV, satisfação
- Contexto: nicho, tamanho do negócio, desafio original
- Resultados: métricas concretas com números reais
- Quote: extraída de feedback positivo ou NPS comment

**Estrutura do case:**
1. Contexto (quem é o cliente, nicho, desafio)
2. Desafio (dor antes da Zenya)
3. Solução (o que foi implementado)
4. Resultados (métricas reais before/after)
5. Quote do cliente

**Armazenamento:**
- Brain namespace `sparkle-ops` com tag `case`
- Disponível para: propostas automáticas (Story 3.1), nurturing sequences, landing page

---

## Acceptance Criteria

### Referral
- [ ] **AC1** — Proposta de referral é enviada automaticamente via Z-API para clientes com NPS 9-10 (promotores)
- [ ] **AC2** — Tracking de referral funciona end-to-end: proposta enviada, lead indicado registrado com `referred_by`, status atualizado em cada etapa
- [ ] **AC3** — Desconto de 10% é aplicado automaticamente para referrer e referred quando o indicado converte em cliente
- [ ] **AC4** — Tabela `referrals` registra todo o ciclo: proposed, accepted, converted, expired

### Cases Automáticos
- [ ] **AC5** — Case é gerado automaticamente para clientes com health > 70 por 6+ meses E flag `case_authorized = true`
- [ ] **AC6** — Case contém métricas reais: before/after de volume de atendimentos, TTV e satisfação — sem dados inventados
- [ ] **AC7** — Case é armazenado no Brain namespace `sparkle-ops` com tag `case` e metadata (client_id, niche, generated_at)
- [ ] **AC8** — Cases são consumidos pela engine de propostas (Story 3.1) para incluir case de cliente similar
- [ ] **AC9** — Case só é gerado se cliente autorizou (`case_authorized`). Sem autorização, nenhum dado é usado.

---

## Integration Verifications

- [ ] NPS score está acessível e atualizado para identificar promotores (9-10)
- [ ] Z-API envia proposta de referral formatada — testar com número de teste
- [ ] Tabela `leads` aceita campo `referred_by` sem quebrar queries existentes
- [ ] Tabela `referrals` criada com constraints corretas (FK para clients e leads)
- [ ] Health score histórico está disponível para verificar "6+ meses > 70"
- [ ] Brain aceita escrita no namespace `sparkle-ops` com tag `case`
- [ ] Brain retorna cases por nicho quando consultado (para Story 3.1)
- [ ] Engine de propostas (Story 3.1) consome cases do Brain corretamente
- [ ] Flag `case_authorized` existe na tabela `clients` e é respeitada

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `runtime/expansion/referral.py` | Criar | Engine de referral: detecção promotores, proposta, tracking |
| `runtime/expansion/case_generator.py` | Criar | Gerador automático de cases a partir de métricas reais |
| `runtime/expansion/case_templates.py` | Criar | Templates de estrutura de case por nicho |
| `migrations/XXX_referral_program.sql` | Criar | Tabela referrals + campo referred_by em leads |
| `migrations/XXX_case_authorization.sql` | Criar | Campo case_authorized em clients |
| `tests/test_referral.py` | Criar | Testes: proposta, tracking, desconto, ciclo completo |
| `tests/test_case_generator.py` | Criar | Testes: critérios, métricas reais, Brain storage |
