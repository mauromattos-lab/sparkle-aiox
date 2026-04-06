---
epic: Pipeline Comercial Sparkle v1
story: PC-1.4
title: Notificação Friday — Alerta Mauro quando lead qualificado pede contato
status: Closed
priority: Alta
executor: "@dev (n8n WF01 + WF05) -> @qa -> @po"
sprint: Sprint Pipeline (Semana 1-2)
depends_on: [PC-1.1 (Zenya ativa), PC-1.2 (BANT score no Supabase)]
unblocks: [PC-1.5 (Script B2 usa contexto desta notificação)]
estimated_effort: "2-3h (@dev 1-2h + @qa 1h)"
prd: docs/prd/pipeline-comercial-prd.md
arch_decision: |
  Caminho C: Notificação via WF01 → WF05 (já existente — "05. Escalada para Z-API → Mauro").
  Dois gatilhos independentes:
  1. Lead pede contato humano ("falar com alguém") → já implementado via WF05
  2. Score BANT = "Alto" → NOVO: disparar notificação com contexto completo
  Destino: WhatsApp do Mauro via Z-API (número da Friday, já configurado em WF05).
  Mensagem: template com nome, score, resumo BANT e link Chatwoot da conversa.
---

# Story PC-1.4 — Notificação Friday: Alerta de Lead Qualificado

## Story

**Como** Mauro (vendedor),
**Quero** receber no meu WhatsApp um aviso quando a Zenya identifica um lead de score Alto,
**Para que** eu entre na conversa com contexto completo — sem ter que ler todo o histórico.

---

## Contexto Técnico

**Estado atual:**
- WF05 ("05. Escalada para Z-API → Mauro") existe e envia mensagem para Mauro quando lead pede falar com humano
- WF01 detecta a frase de trigger e chama WF05
- PC-1.2 implementará extração de BANT + score no Supabase
- **Gap:** Não existe notificação automática quando score = "Alto" (independente do lead pedir contato)

**O que esta story implementa:**

**Gatilho 1 — Lead pede contato humano (já existente, melhorar):**
- Trigger atual: keywords como "falar com alguém", "quero falar com o dono"
- Melhoria: incluir o contexto BANT na mensagem enviada a Mauro (atualmente envia só o nome/número)

**Gatilho 2 — Score BANT = Alto (NOVO):**
- Quando o nó de extração (PC-1.2) retorna `bant_score = "Alto"`, disparar notificação para Mauro
- Sem interação do lead — automático, silencioso

**Template da notificação (ambos os gatilhos):**
```
🎯 Lead qualificado — [NOME ou "Lead sem nome"]

📊 Score: [Alto/Médio]
🏪 Negócio: [business_type] — [business_name ou "não identificado"]
📱 WhatsApp: [phone]

💬 Resumo BANT:
• Dor: [necessity]
• Urgência: [timing]
• Decisor: [authority]

🔗 Conversa no Chatwoot: [link]

_Zenya está no chat — use /abertura-handoff para entrar_
```

**Roteamento:**
- Notificação vai para o WhatsApp pessoal do Mauro via Z-API (mesmo endpoint que WF05 já usa)
- Link Chatwoot: `https://app.chatwoot.com/app/accounts/{account_id}/conversations/{conversation_id}`

---

## Critérios de Aceitação

### Gatilho por pedido de contato humano (melhoria de WF05)

- [ ] **AC-1:** Quando lead diz "quero falar com alguém" (ou variações), Mauro recebe notificação
- [ ] **AC-2:** Notificação inclui: nome (se identificado), número WhatsApp, score BANT atual (mesmo que Indeterminado), link Chatwoot
- [ ] **AC-3:** Zenya responde ao lead com a frase padrão: *"Vou avisar o responsável agora e fico aqui à sua disposição enquanto isso"*

### Gatilho por score Alto (novo)

- [ ] **AC-4:** Quando score BANT = "Alto" é detectado pela primeira vez para um lead, Mauro recebe notificação automática
- [ ] **AC-5:** Notificação de score Alto NÃO é disparada repetidamente para o mesmo lead — apenas na primeira vez que o score atingir "Alto"
- [ ] **AC-6:** Notificação de score Alto usa o mesmo template com os campos BANT preenchidos

### Qualidade da mensagem

- [ ] **AC-7:** Campos null no BANT não aparecem como "null" na mensagem — são omitidos ou substituídos por "não identificado"
- [ ] **AC-8:** Link Chatwoot é válido e aponta para a conversa correta
- [ ] **AC-9:** Notificação chega ao Mauro em ≤ 30 segundos após trigger

### Não-regressão

- [ ] **AC-10:** Fluxo principal da Zenya (responder ao lead) não é atrasado pela notificação — envio assíncrono ou em paralelo

---

## Definition of Done

- [x] Todos os ACs passando
- [x] Testado com número de teste (não número real do Mauro sem autorização)
- [x] WF01 e WF05 atualizados e salvos
- [x] `work_log.md` atualizado

---

## Tarefas

- [ ] **T1:** @dev — Mapear como WF01 atualmente chama WF05 (webhook, sub-workflow ou Execute Workflow)
- [ ] **T2:** @dev — Adicionar campos BANT ao payload enviado de WF01 para WF05
- [ ] **T3:** @dev — Atualizar template de mensagem em WF05 para incluir contexto BANT
- [ ] **T4:** @dev — Adicionar no WF01 (após nó de extração BANT do PC-1.2) condicional: se score = "Alto" E primeiro registro → chamar WF05
- [ ] **T5:** @dev — Implementar deduplicação de notificação (verificar se lead já foi notificado — via campo em Supabase ou Set node)
- [ ] **T6:** @qa — Testar gatilho manual + gatilho score Alto + verificar não-duplicação

---

## Dependências

**Depende de:**
- PC-1.1 (WF01 + WF05 existentes)
- PC-1.2 (nó de extração BANT deve existir para o gatilho de score)

**Desbloqueia:**
- PC-1.5 Canal B2 (Script do Mauro usa o contexto enviado por esta notificação)

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| n8n WF01 (ID: `IY9g1qHAv1FV8I5D`) | Modificar | Adicionar trigger score Alto → WF05 |
| n8n WF05 (ID: `cdqNUH8xoLy9gJCT`) | Modificar | Atualizar template de notificação com contexto BANT |
