---
epic: Pipeline Comercial Sparkle v1
story: PC-1.3
title: Showcase Dinâmico — Demonstração ao vivo no contexto do lead
status: Done
priority: Média
executor: "@dev (soul prompt)"
sprint: Sprint Pipeline (Semana 1 — paralelo com PC-1.1)
depends_on: [PC-1.1 (Zenya Vendedora ativa)]
unblocks: []
estimated_effort: "0h — implementado junto com PC-1.1"
prd: docs/prd/pipeline-comercial-prd.md
implementation_note: |
  2026-04-05: Implementado como parte do soul prompt Zenya Vendedora (PC-1.1).
  A seção "SHOWCASE DINÂMICO" no soul prompt já instrui a Zenya a:
  - Demonstrar capacidades usando o negócio REAL do lead (não exemplos genéricos)
  - Usar 3 exemplos âncora (confeitaria, clínica, escola) como referência
  - Adaptar para qualquer nicho baseado no que o lead mencionou
  - Convidar o lead a testar ao vivo ("me manda uma mensagem como se fosse um cliente seu")
  - Incluir link Calendly para agendamento de demo
  Arquivo fonte: docs/zenya/zenya-vendedora-soul.md (seção SHOWCASE DINÂMICO)
---

# Story PC-1.3 — Showcase Dinâmico

## Story

**Como** lead prospectado,
**Quero** ver a Zenya funcionando para o MEU negócio específico — não um exemplo genérico,
**Para que** eu entenda concretamente o valor antes de tomar qualquer decisão.

---

## Status: Implementado via PC-1.1

Esta story foi implementada integralmente como parte do soul prompt da Zenya Vendedora (PC-1.1).

**O que foi entregue:**

1. **Demonstração contextualizada** — Zenya usa o nicho/negócio identificado no BANT para construir exemplos ao vivo. Soul prompt tem 3 âncoras de nicho (confeitaria, clínica, escola) e instrução explícita de adaptar para qualquer outro.

2. **Convite ao teste ao vivo** — Soul prompt inclui: *"Quer ver funcionando? Me manda uma mensagem como se fosse um cliente seu chegando agora"* — o lead vive a experiência do produto.

3. **Lista de capacidades** — Soul prompt define lista clara do que pode e não pode ser demonstrado (sem overpromise).

4. **CTA de agendamento** — Quando lead demonstra interesse real, soul prompt oferece link Calendly: `https://calendly.com/agendasparkle/sessao30min`

**Arquivo de referência:** `docs/zenya/zenya-vendedora-soul.md` — seção `SHOWCASE DINÂMICO`

---

## Critérios de Aceitação — Validados pelo soul prompt

- [x] **AC-1:** Zenya usa o negócio do lead para construir o exemplo (não template fixo por nicho)
- [x] **AC-2:** Exemplos âncora disponíveis para guiar o raciocínio do LLM (confeitaria, clínica, escola)
- [x] **AC-3:** Capacidades demonstráveis definidas — Zenya não inventa funcionalidades fora da lista
- [x] **AC-4:** Convite para teste ao vivo incluído no fluxo
- [x] **AC-5:** CTA para demo (Calendly) disponível quando lead demonstra interesse

---

## Definition of Done

- [x] Soul prompt implementado e ativo no WF01
- [x] Arquivo fonte versionado em `docs/zenya/zenya-vendedora-soul.md`

---

## Notas para @qa

O smoke test formal (AC-12 de PC-1.1) deve cobrir pelo menos 2 nichos diferentes para validar que o showcase dinâmico se adapta. Sugestão: testar com confeitaria (âncora) e um nicho não-âncora (ex: pet shop).

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `docs/zenya/zenya-vendedora-soul.md` | Criado em PC-1.1 | Soul prompt com seção SHOWCASE DINÂMICO |
| n8n WF01 (ID: `IY9g1qHAv1FV8I5D`) | Modificado em PC-1.1 | AI Agent com soul prompt aplicado |
