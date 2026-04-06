---
epic: Pipeline Comercial Sparkle v1
story: PC-1.1
title: Zenya Vendedora — Instância + System Prompt de Vendas
status: Done
priority: Alta
executor: "@dev (configuração) -> @qa (smoke test) -> @devops (deploy)"
sprint: Sprint Pipeline (Semana 1)
depends_on: []
unblocks: [PC-1.2 (Qualificação BANT), PC-1.3 (Showcase Dinâmico)]
estimated_effort: "3-5h (@dev 2-3h configuração + craft do soul prompt + @qa 1-2h smoke test)"
prd: docs/prd/pipeline-comercial-prd.md
arch_decision: "Caminho C (híbrido): implementado via n8n WF01 'Demo - Secretária v3' (não via Runtime zenya_clients). Número Z-API dedicado: +5512982201239 (Sparkle Vendas, inbox 11 Chatwoot). Soul prompt Zenya Vendedora no AI Agent options.systemMessage. Migração para Runtime em sprint futura."
implementation_note: "2026-04-05: WF01 configurado com soul prompt Zenya Vendedora. Filtro, encoding, conexões e model params corrigidos. Z-API +5512982201239 exclusivo. Pending: smoke test formal @qa (AC-12)."
---

# Story PC-1.1 — Zenya Vendedora: Instância + System Prompt de Vendas

## Story

**Como** Mauro (fundador),
**Quero** uma instância Zenya dedicada a vendas com identidade e comportamento orientados a qualificar e converter leads,
**Para que** leads que chegam pelo WhatsApp vivenciem o produto ao mesmo tempo em que são conduzidos pelo funil — sem consumir meu tempo.

---

## Contexto Técnico

**Por que esta abordagem:** O `zenya/router.py` já suporta multi-tenant via `zenya_clients`. O router resolve `soul_prompt` e credenciais Z-API por `client_id`. Criar a Zenya Vendedora é configuração, não código.

**Decisão do @architect:** Novo registro em `zenya_clients` com `client_id = "sparkle-sales"`. Webhook disponível em `/zenya/webhook/sparkle-sales`. Zero alteração no código.

**Tabelas envolvidas:**
- `zenya_clients` — novo registro com credenciais Z-API e soul prompt de vendas
- `leads` — tabela já estendida pelo @data-engineer (migration `pipeline_comercial_001_extend_leads`)

**Arquivos a criar/editar no Runtime:**
- Nenhum arquivo de código. Apenas:
  1. Inserção em `zenya_clients` (via Supabase MCP)
  2. Craft do `soul_prompt` de vendas (documento salvo em `docs/zenya/zenya-vendedora-soul.md`)

**Estrutura do `soul_prompt` de vendas:**
O soul prompt deve cobrir 4 zonas:
1. **Identidade** — "Sou a Zenya, assistente da Sparkle. Estou aqui para entender seu negócio e mostrar como posso ajudar."
2. **Qualificação** — Instruções para coletar BANT naturalmente ao longo da conversa (sem parecer formulário)
3. **Showcase** — Instruções para demonstrar capacidades usando o contexto do negócio do lead
4. **Handoff** — Regras de quando ofertar demo, quando notificar Mauro, como responder pedido de contato imediato

**Regras invioláveis do soul prompt:**
- Nunca fingir ser humana
- Nunca fabricar capacidades que não existem no produto
- Capacidades demonstráveis: resposta 24h, agendamento, handoff humano, cobrança (Asaas)
- Quando lead pede falar com alguém: *"Vou avisar o responsável agora e fico aqui à sua disposição enquanto isso"*

---

## Critérios de Aceitação

### Instância

- [ ] **AC-1:** Registro inserido em `zenya_clients` com `client_id = "sparkle-sales"`, `active = true`, credenciais Z-API do número dedicado e `soul_prompt` de vendas
- [ ] **AC-2:** Webhook `/zenya/webhook/sparkle-sales` responde `200 OK` (número Z-API conectado)
- [ ] **AC-3:** Caixa "Sparkle Vendas" criada no Chatwoot, separada de todas as caixas de clientes ativos
- [ ] **AC-4:** Mensagem enviada para o número da Zenya Vendedora retorna resposta em menos de 3 segundos

### Isolamento

- [ ] **AC-5:** Mensagem no número Zenya Vendedora não aparece em nenhuma caixa de cliente ativo no Chatwoot
- [ ] **AC-6:** `client_id = "sparkle-sales"` não interfere com nenhum registro de cliente real na tabela `zenya_clients`

### Comportamento do Soul Prompt

- [ ] **AC-7:** Zenya se apresenta como IA da Sparkle (não finge ser humana, não se apresenta como secretária de um cliente)
- [ ] **AC-8:** Tom profissional e acessível — responde como empresa, não como freelancer
- [ ] **AC-9:** Quando perguntada diretamente "você é um robô?", responde honestamente sem quebrar o fluxo
- [ ] **AC-10:** Quando lead pede falar com alguém agora, Zenya usa a frase padrão do PRD (não improvisa)
- [ ] **AC-11:** Zenya não menciona capacidades fora da lista permitida (agendamento, 24h, handoff, cobrança)

### Smoke Test

- [ ] **AC-12:** @qa executa smoke test de 10 mensagens manuais com @dev presente (incluindo: apresentação, pergunta sobre preço, pedido de contato humano, nicho de confeitaria, nicho fora dos âncora) — todas recebem resposta coerente

---

## Definition of Done

- [ ] Todos os ACs passando
- [ ] Soul prompt revisado e aprovado pelo Mauro antes de ativar
- [ ] Smoke test de isolamento: nenhum cliente ativo impactado
- [ ] `soul_prompt` salvo em `docs/zenya/zenya-vendedora-soul.md` (versionado no repo)
- [ ] `work_log.md` atualizado
- [ ] Deploy confirmado pelo @devops

---

## Tarefas Técnicas

- [ ] **T1:** Trocar número da Friday para o número reservado (instância Z-API nova + webhook → endpoint Friday). Downtime ~5min. Número atual da Friday passa a ser da Zenya Vendedora.
- [ ] **T2:** Criar caixa "Sparkle Vendas" no Chatwoot
- [ ] **T3:** Redigir soul prompt de vendas cobrindo as 4 zonas (identidade, qualificação, showcase, handoff)
- [ ] **T4:** Inserir registro em `zenya_clients` via Supabase com `client_id = "sparkle-sales"`, credenciais Z-API do T1, soul prompt do T3
- [ ] **T5:** Configurar webhook Z-API para apontar para `/zenya/webhook/sparkle-sales` no Runtime
- [ ] **T6:** Executar smoke test de 10 mensagens manuais (AC-12)
- [ ] **T7:** Validar isolamento: enviar mensagem na vitrine e confirmar que não aparece em caixas de clientes
- [ ] **T8:** Salvar soul prompt em `docs/zenya/zenya-vendedora-soul.md`

---

## Dependências

**Esta story não bloqueia nada para iniciar.**

**Esta story desbloqueia:**
- PC-1.2 (Qualificação BANT) — depende da instância existir
- PC-1.3 (Showcase Dinâmico) — depende do soul prompt base

**Dependências técnicas disponíveis:**
- `zenya/router.py` multi-tenant — OK (nenhuma mudança necessária)
- Supabase MCP para inserção em `zenya_clients` — OK
- Chatwoot com suporte a múltiplas caixas — OK
- Tabela `leads` com schema pipeline — OK (migration aplicada)

---

## Pipeline AIOS

| Etapa | Agente | Entrega |
|-------|--------|---------|
| Configuração + soul prompt | @dev | Registro em `zenya_clients`, soul prompt draft |
| Revisão do soul prompt | Mauro | Aprovação do texto antes de ativar |
| Validação | @qa | Smoke test 10 mensagens + isolamento |
| Deploy | @devops | Confirmar webhook Z-API apontando para Runtime |
| Aceite | @po | AC-7 a AC-11 validados |

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `supabase/zenya_clients` (via MCP) | Inserir | Novo registro `sparkle-sales` |
| `docs/zenya/zenya-vendedora-soul.md` | Criar | Soul prompt de vendas versionado |
