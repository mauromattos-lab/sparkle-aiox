---
epic: EPIC-CLIENT-LIFECYCLE — Gestão do Ciclo de Vida do Cliente
story: LIFECYCLE-3.3
title: "Scripts de Abordagem para Upsell (Fase 5)"
status: NEEDS_FIX
priority: Média
executor: "@dev (implementação) + @analyst (conteúdo dos scripts)"
sprint: Client Lifecycle Wave 3
prd: docs/prd/domain-client-lifecycle-prd.md
architecture: docs/architecture/domain-client-lifecycle-architecture.md
squad: squads/client-lifecycle/
depends_on: [LIFECYCLE-2.x (Wave 2 completa), LIFECYCLE-1.2 (health score)]
unblocks: [LIFECYCLE-3.4]
estimated_effort: 3-4h de agente (@dev + @analyst)
---

# Story 3.3 — Scripts de Abordagem para Upsell (Fase 5)

**Sprint:** Client Lifecycle Wave 3
**Status:** `NEEDS_FIX`
**Sequência:** 3 de 4
**PRD:** `docs/prd/domain-client-lifecycle-prd.md`
**Architecture:** `docs/architecture/domain-client-lifecycle-architecture.md`
**Squad:** `squads/client-lifecycle/`

---

## User Story

> Como Mauro (CEO da Sparkle),
> quero ter scripts pré-aprovados de abordagem para cada tipo de oportunidade de upsell,
> para que quando o sistema detectar uma oportunidade eu receba o script pronto com contexto do cliente e possa enviar com mínimo esforço.

---

## Contexto Técnico

**Por que agora:** O health score engine (Wave 1) e o sistema de detecção de oportunidades (Wave 2) já identificam quando um cliente está pronto para upsell. O que falta é a "munição" — scripts prontos que Mauro possa usar sem precisar pensar na abordagem. Isso fecha o loop entre detecção e ação.

**Estado atual:**
- Health score engine calcula score por cliente (Story 1.2)
- Oportunidades de upsell são detectadas mas não há scripts associados
- Mauro aborda clientes de forma ad-hoc, sem scripts padronizados
- Friday já é canal de comunicação com Mauro

**PRD ref:** F5-FR4 (scripts pré-aprovados)

**Dependências:**
- Health score funcional (Story 1.2)
- Detecção de oportunidades funcional (Wave 2)
- Friday funcional para entrega de scripts com contexto

**Biblioteca de scripts — 4 tipos:**

1. **Upgrade de tier** — foco nas features que o cliente desbloquearia (relatórios, automações avançadas, integrações)
2. **Cross-sell tráfego** — benchmark do nicho + projeção de ROI baseada em dados reais de clientes similares
3. **Cross-sell conteúdo** — exemplos de conteúdo que converte no nicho do cliente
4. **Referral** — proposta de desconto mútuo (referrer + referred)

**Estrutura de cada script:**
- Opening (quebra-gelo contextualizado)
- Value proposition (benefício específico para o cliente)
- Soft CTA (chamada para ação não agressiva)
- Objection handlers (2-3 objeções comuns e respostas)

**Variáveis de template:**
- `{client_name}` — nome do cliente
- `{business_name}` — nome do negócio
- `{current_plan}` — plano atual
- `{health_score}` — score atual
- `{months_active}` — meses como cliente
- `{niche}` — nicho de atuação
- `{zenya_name}` — nome da Zenya do cliente

---

## Acceptance Criteria

- [ ] **AC1** — Scripts existem para todos os 4 tipos de upsell: upgrade tier, cross-sell tráfego, cross-sell conteúdo, referral
- [ ] **AC2** — Cada script contém as 4 seções obrigatórias: opening, value proposition, soft CTA, objection handlers
- [ ] **AC3** — Variáveis de template (`{client_name}`, `{business_name}`, `{current_plan}`, `{health_score}`, `{months_active}`) populam corretamente com dados reais do cliente
- [ ] **AC4** — Friday entrega o script para Mauro com contexto completo: nome do cliente, score, motivo da oportunidade, há quanto tempo é cliente
- [ ] **AC5** — Mauro pode customizar o script antes de enviar (edit flow via Friday)
- [ ] **AC6** — Scripts são armazenados de forma estruturada (Supabase ou `runtime/expansion/scripts.py`) e versionados
- [ ] **AC7** — Quando oportunidade é detectada, o script correto é selecionado automaticamente com base no tipo de oportunidade

---

## Integration Verifications

- [ ] Health score do cliente está acessível para popular variável `{health_score}`
- [ ] Dados do cliente (nome, negócio, plano, meses ativo, nicho) estão disponíveis para popular variáveis
- [ ] Friday recebe e exibe script formatado com contexto — Mauro consegue ler, editar e aprovar
- [ ] Detecção de oportunidade (Wave 2) faz handoff correto para o módulo de scripts com tipo de upsell identificado
- [ ] Scripts renderizados não contêm variáveis não-resolvidas (ex: `{client_name}` literal)
- [ ] Teste com dados de cliente fictício valida todos os 4 tipos de script

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `runtime/expansion/scripts.py` | Criar | Engine de scripts: storage, seleção, renderização |
| `runtime/expansion/scripts_library.py` | Criar | Biblioteca com os 4 tipos de script |
| `runtime/expansion/script_renderer.py` | Criar | Renderizador de variáveis de template |
| `runtime/lifecycle/upsell_script_trigger.py` | Criar | Trigger que conecta detecção de oportunidade ao script |
| `tests/test_scripts.py` | Criar | Testes: renderização, seleção por tipo, variáveis |
| `tests/test_script_renderer.py` | Criar | Testes: edge cases de renderização, variáveis faltantes |
