---
epic: Pipeline Comercial Sparkle v1
story: PC-1.5b
title: Template de Proposta Padrão — 1 página, enviada via WhatsApp
status: Done
priority: Alta
executor: "@pm (draft) -> Mauro (aprovação) -> @dev (automatizar envio em PC-1.6)"
sprint: Sprint Pipeline (Semana 2 — pré-requisito para PC-1.6 D0)
depends_on: []
unblocks: [PC-1.6 (D0 envia este template personalizado)]
estimated_effort: "1h (@pm 30min draft + Mauro 15min aprovação)"
prd: docs/prd/pipeline-comercial-prd.md
arch_decision: |
  Proposta é um documento de texto estruturado enviado via WhatsApp (não PDF por enquanto).
  Formato: 5 blocos fixos com placeholders para personalização por lead.
  PC-1.6 vai substituir os placeholders com dados de leads.bant_summary antes de enviar.
  Nenhuma integração externa necessária — tudo via Z-API send-text.
---

# Story PC-1.5b — Template de Proposta Padrão

## Story

**Como** Mauro (vendedor),
**Quero** um template de proposta pronto para personalizar e enviar no WhatsApp em menos de 2 minutos,
**Para que** nenhum lead qualificado fique sem proposta por falta de tempo ou preguiça de escrever.

---

## Contexto

FR11 do PRD define: proposta de 1 página com problema identificado, o que está incluído, resultado esperado em R$, investimento mensal e CTA de confirmação pelo WhatsApp.

A proposta é enviada em D0 (até 2h após a demo) pelo follow-up automatizado (PC-1.6). PC-1.6 preenche os placeholders com dados do `leads.bant_summary` antes de enviar.

---

## O template

```
Oi [NOME] 👋

Depois da nossa conversa, preparei um resumo do que conversamos e como posso ajudar.

---

🔍 *O que identificamos:*
[PROBLEMA — ex: "Você está perdendo atendimentos no WhatsApp fora do horário comercial, principalmente de novos clientes que entram em contato à noite."]

---

✅ *O que está incluído:*
• Zenya configurada para o seu negócio ([TIPO_NEGOCIO])
• Atendimento automático 24h no WhatsApp
• Agendamento/triagem de clientes
• Handoff para você quando necessário
• Suporte e ajustes nos primeiros 30 dias

---

📈 *Resultado esperado:*
[RESULTADO — ex: "Nenhum cliente sem resposta. Estimativa de recuperar 20-30% dos leads que hoje ficam sem atendimento fora do horário."]

---

💰 *Investimento:*
R$ [VALOR]/mês
Sem taxa de setup. Sem contrato mínimo.

---

Para confirmar, é só responder *"topo"* aqui mesmo.
Qualquer dúvida, pode perguntar 🙂
```

---

## Placeholders para PC-1.6 preencher automaticamente

| Placeholder | Fonte |
|-------------|-------|
| `[NOME]` | `leads.name` |
| `[PROBLEMA]` | gerado por LLM com base em `leads.bant_summary.necessity` |
| `[TIPO_NEGOCIO]` | `leads.business_type` |
| `[RESULTADO]` | gerado por LLM com base em `business_type` + `necessity` |
| `[VALOR]` | R$497 padrão (Mauro ajusta se necessário antes de enviar) |

---

## Critérios de Aceitação

- [ ] **AC-1:** Template aprovado por Mauro — tom, estrutura e CTA corretos
- [ ] **AC-2:** Template salvo em `docs/playbooks/pipeline-comercial-script-mauro.md` (seção "Proposta D0")
- [ ] **AC-3:** Placeholders claramente marcados com `[CAMPO]` para PC-1.6 substituir
- [ ] **AC-4:** Cabe em 1 tela de WhatsApp sem scroll excessivo (máx 30 linhas)
- [ ] **AC-5:** Mauro consegue editar manualmente em < 2 minutos antes de enviar

---

## Definition of Done

- [ ] AC-1 a AC-5 passando
- [ ] Template adicionado ao playbook existente
- [ ] PC-1.6 pode referenciar este template como entregável

---

## Tarefas

- [ ] **T1:** @pm — Redigir template acima e adicionar ao playbook `docs/playbooks/pipeline-comercial-script-mauro.md`
- [ ] **T2:** Mauro — Ler e aprovar (ok via mensagem na Friday)
- [ ] **T3:** @dev (PC-1.6) — Usar este template como base para o nó de personalização D0

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `docs/playbooks/pipeline-comercial-script-mauro.md` | Modificar | Adicionar seção "Proposta D0" com o template |
