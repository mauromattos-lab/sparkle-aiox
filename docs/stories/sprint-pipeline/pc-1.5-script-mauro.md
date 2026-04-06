---
epic: Pipeline Comercial Sparkle v1
story: PC-1.5
title: Script do Mauro — Playbook Canal B (Lead Frio) + Canal B2 (Handoff da Zenya)
status: Done
priority: Alta
executor: "@pm + Mauro (conteúdo) -> @qa (revisão) -> Mauro (aprovação final)"
sprint: Sprint Pipeline (Semana 1 — paralelo com PC-1.1)
depends_on: []
unblocks: [PC-1.4 (Notificação Friday — B2 usa o script), PC-1.6 (Follow-up — referencia o playbook)]
estimated_effort: "2-3h (@pm 1-2h draft + Mauro 30min revisão + @qa 30min checklist)"
prd: docs/prd/pipeline-comercial-prd.md
arch_decision: "Zero código. Playbook como documento + respostas rápidas no WhatsApp Business. Mauro executa manualmente com suporte da Friday para contexto B2."
---

# Story PC-1.5 — Script do Mauro: Playbook Canal B + Canal B2

## Story

**Como** Mauro (vendedor),
**Quero** scripts específicos para dois cenários — lead que chega direto no meu WhatsApp e lead que veio via handoff da Zenya —
**Para que** eu nunca improvise uma conversa de vendas e aproveite o contexto BANT já coletado quando disponível.

---

## Contexto Técnico

**Por que esta story independe de infraestrutura:** O script do Mauro é um artefato de processo, não de código. Os dois canais cobertos são:

- **Canal B (Lead Frio):** Lead chega direto no WhatsApp pessoal do Mauro sem nenhum contexto prévio. Mauro precisa de um script estruturado que caiba em 1 tela de celular e cubra abertura → BANT rápido → objeções → CTA.

- **Canal B2 (Handoff da Zenya):** Mauro recebe notificação via Friday com o contexto BANT já preenchido pela Zenya Vendedora. Mauro entra na conversa sabendo quem é o lead, qual a dor, o score e o nicho. O script para esse canal começa do ponto onde a Zenya parou — sem repetir qualificação.

**Entregáveis desta story:**
1. Documento `docs/playbooks/pipeline-comercial-script-mauro.md` — playbook completo com os dois scripts
2. Respostas rápidas configuradas no WhatsApp Business do Mauro (6 itens)
3. Etiquetas configuradas no WhatsApp Business (6 etiquetas do pipeline)

**Estrutura do playbook:**
```
CANAL B — Lead Frio
├── Abertura (1 mensagem, quebra-gelo)
├── BANT rápido (3 perguntas naturais)
├── Objeções (5 mais comuns + resposta em 1 frase)
└── CTA (oferecer demo ou encerrar com elegância)

CANAL B2 — Handoff da Zenya
├── Abertura contextualizada (usa nome + dor do contexto Friday)
├── Confirmação de interesse (1 pergunta)
└── CTA direto (agenda demo ou envia proposta)
```

**Respostas rápidas a configurar (/ no WA Business) — 8 itens:**
1. `/abertura-frio` — abertura Canal B
2. `/bant-1` — pergunta BANT sobre dor/necessidade
3. `/bant-2` — pergunta BANT sobre volume/urgência
4. `/bant-3` — pergunta BANT sobre decisão/orçamento implícito
5. `/abertura-handoff` — abertura Canal B2 (com placeholder [nome] e [dor])
6. `/cta-demo` — convite para demo com link Calendly
7. `/encerra-elegante` — encerramento para não-ICP
8. `/d0-proposta` — template proposta D0 (antecipa Story PC-1.6)

**Etiquetas WhatsApp Business a criar:**
- 🔵 `Novo Lead`
- 🟡 `Qualificado`
- 🟠 `Demo Agendada`
- 🔴 `Proposta Enviada`
- 🟢 `Cliente`
- ⚫ `Perdido`

---

## Critérios de Aceitação

### Playbook Canal B (Lead Frio)

- [ ] **AC-1:** Abertura em 1 mensagem curta — quebra-gelo que não começa com "Olá, sou Mauro da Sparkle..." (clichê). Tom direto e humano
- [ ] **AC-2:** 3 perguntas BANT em linguagem natural para dono de PME (não corporate, não formulário)
  - Budget implícito: sem perguntar "qual seu orçamento?" diretamente
  - Authority: identifica se é o decisor sem ser invasivo
  - Need: descobre a dor em atendimento WhatsApp
- [ ] **AC-3:** 5 objeções cobertas com resposta em 1 frase cada:
  - "É caro" → calcula ROI ao vivo
  - "Preciso pensar" → descobre o que falta
  - "Já tenho um bot" → diferencia Zenya de fluxo genérico
  - "Meus clientes não gostam de robô" → showcaseia naturalidade
  - "E se der problema?" → explica handoff humano
- [ ] **AC-4:** CTA claro: qualificado → oferecer demo em link Calendly; não-ICP → encerrar com elegância (sem desanimar, sem insistir)
- [ ] **AC-5:** Script completo cabe em 1 tela de celular (≤ 30 segundos de leitura)

### Playbook Canal B2 (Handoff da Zenya)

- [ ] **AC-6:** Abertura usa contexto recebido via Friday: nome do lead + dor identificada no BANT — Mauro não começa do zero
- [ ] **AC-7:** Abertura não repete perguntas que a Zenya já fez (confirma contexto, não requalifica)
- [ ] **AC-8:** Fluxo vai direto para oferta de demo ou proposta (≤ 3 mensagens até CTA)
- [ ] **AC-9:** Script inclui instrução sobre como ler a notificação Friday: quais campos usar e como

### Respostas Rápidas e Etiquetas

- [ ] **AC-10:** 8 respostas rápidas configuradas no WhatsApp Business do Mauro e acessíveis com `/`
- [ ] **AC-11:** 6 etiquetas de pipeline criadas no WhatsApp Business e visíveis na tela de contatos
- [ ] **AC-12:** Mauro consegue atualizar etiqueta de um lead em menos de 5 segundos (sem abrir n8n ou Supabase)

### Aprovação

- [ ] **AC-13:** Mauro leu o playbook completo, testou as respostas rápidas em conversa simulada e aprovou por escrito (mensagem no WhatsApp da Friday)
- [ ] **AC-14:** @qa revisou o playbook e confirmou que nenhum script promete capacidade não existente no produto

---

## Definition of Done

- [ ] Todos os ACs passando
- [ ] `docs/playbooks/pipeline-comercial-script-mauro.md` criado e salvo no repo
- [ ] Respostas rápidas configuradas e testadas no celular do Mauro
- [ ] Etiquetas criadas e testadas no WhatsApp Business
- [ ] Mauro aprovou (AC-13)
- [ ] `work_log.md` atualizado

---

## Tarefas

- [ ] **T1:** @pm — Redigir draft do Playbook Canal B (abertura + BANT + 5 objeções + CTA) com base na pesquisa @analyst
- [ ] **T2:** @pm — Redigir draft do Playbook Canal B2 (abertura contextualizada + CTA direto) com base na notificação Friday do PC-1.4
- [ ] **T3:** @pm — Criar as 6 respostas rápidas formatadas para WhatsApp Business (`/comando` + texto)
- [ ] **T4:** Mauro — Configurar respostas rápidas no WhatsApp Business (Settings → Quick Replies)
- [ ] **T5:** Mauro — Criar as 6 etiquetas de pipeline (Settings → Labels)
- [ ] **T6:** Mauro — Testar playbook Canal B em conversa simulada com alguém da confiança
- [ ] **T7:** Mauro — Revisar e aprovar o playbook Canal B2 (só pode testar após PC-1.4 estar pronto)
- [ ] **T8:** @qa — Checar se alguma resposta promete capacidade não existente no produto
- [ ] **T9:** Salvar playbook final em `docs/playbooks/pipeline-comercial-script-mauro.md`

---

## Dependências

**Esta story não bloqueia nada para iniciar.** Pode rodar em paralelo com PC-1.1 na Semana 1.

**Esta story desbloqueia:**
- PC-1.4 (Notificação Friday) — a notificação envia o contexto BANT que o Canal B2 usa
- PC-1.6 (Follow-up D0→D+7) — referencia o template de proposta D0 do playbook

**Nota sobre Canal B2:** O teste completo do Canal B2 (AC-7 a AC-9) só pode ser validado após PC-1.4 estar funcionando. Os ACs 1-6 e 10-14 são independentes.

---

## Pipeline AIOS

| Etapa | Agente | Entrega |
|-------|--------|---------|
| Draft do playbook | @pm (Morgan) | Documento com os dois scripts + respostas rápidas |
| Configuração WA Business | Mauro | Respostas rápidas + etiquetas ativas |
| Revisão de qualidade | @qa | Confirma que nenhum script overpromise |
| Aprovação | Mauro | AC-13 — aprovação por mensagem na Friday |

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `docs/playbooks/pipeline-comercial-script-mauro.md` | Criar | Playbook completo Canal B + B2 + respostas rápidas |
