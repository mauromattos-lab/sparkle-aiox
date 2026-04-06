---
epic: Pipeline Comercial Sparkle v1
story: PC-1.2
title: Qualificação BANT — Extração e persistência no Supabase
status: Ready for Dev
priority: Alta
executor: "@dev (n8n WF01 + Supabase) -> @qa -> @po"
sprint: Sprint Pipeline (Semana 1)
depends_on: [PC-1.1 (Zenya Vendedora ativa)]
unblocks: [PC-1.4 (Notificação Friday usa score BANT), PC-1.7 (CRM usa leads com BANT)]
estimated_effort: "3-4h (@dev 2-3h n8n + @qa 1h)"
prd: docs/prd/pipeline-comercial-prd.md
arch_decision: |
  Caminho C: BANT extraído via chamada LLM estruturada disparada ao final de cada resposta da Zenya.
  Fluxo: WF01 → após "Formatar texto" → HTTP Request (POST /leads upsert no Supabase) com score + resumo BANT extraído do histórico da conversa.
  Tabela alvo: `leads` (já extendida com colunas bant_score, bant_summary, channel, status, last_contact_at).
  Score: "Alto" / "Medio" / "Baixo" / "Indeterminado" (quando dados insuficientes).
  Trigger de extração: a cada mensagem onde o AI Agent já coletou ≥ 2 dos 4 sinais BANT.
---

# Story PC-1.2 — Qualificação BANT: Extração e Persistência

## Story

**Como** Mauro (vendedor),
**Quero** que cada conversa com a Zenya Vendedora gere automaticamente um score BANT e persista o lead no Supabase,
**Para que** eu sempre saiba quais leads são quentes sem ler as conversas manualmente.

---

## Contexto Técnico

**Estado atual:**
- WF01 "Demo - Secretária v3" está ativo com soul prompt Zenya Vendedora
- O soul prompt já instrui a Zenya a coletar os 4 sinais BANT (necessidade, volume, decisão, timing)
- A tabela `leads` no Supabase já tem: `bant_score`, `bant_summary`, `channel`, `status`, `last_contact_at`, `phone`, `name`, `business_name`, `business_type`, `source`
- **Gap:** A conversa acontece mas nenhum dado chega ao Supabase

**O que esta story implementa:**

1. **Nó de extração BANT** — após cada resposta da Zenya, um segundo prompt LLM (separado do AI Agent principal) analisa o histórico e retorna JSON estruturado:
   ```json
   {
     "name": "nome identificado ou null",
     "phone": "+55...",
     "business_name": "nome do negócio ou null",
     "business_type": "tipo de negócio (confeitaria, clínica, etc) ou null",
     "bant_score": "Alto|Medio|Baixo|Indeterminado",
     "bant_summary": {
       "necessity": "resumo da dor identificada ou null",
       "volume": "estimativa de volume/urgência ou null",
       "authority": "é decisor? (sim/não/incerto)",
       "timing": "urgência identificada ou null"
     },
     "has_sufficient_data": true
   }
   ```

2. **Upsert no Supabase** — HTTP Request POST para tabela `leads`, usando `phone` como chave de deduplicação. Se o lead já existe: atualiza bant_score, bant_summary, last_contact_at. Se não existe: cria registro com source = "zenya-vendedora", channel = "A".

3. **Condicional de escrita** — só escreve no Supabase quando `has_sufficient_data = true` (pelo menos 2 sinais BANT identificados). Evita registro de conversas incompletas.

**Arquitetura do nó de extração:**
- Tipo: "Prompt LLM" separado (não o AI Agent principal) — modelo `gpt-4o-mini` para custo baixo
- Input: últimas N mensagens do histórico da conversa
- Output: JSON estruturado acima
- Posição no fluxo: após "Formatar texto", antes do envio da resposta ao WhatsApp

---

## Critérios de Aceitação

### Extração BANT

- [ ] **AC-1:** Após conversa com ≥ 2 trocas de mensagens relevantes, o score BANT é extraído e persiste em `leads.bant_score` com valor "Alto", "Medio", "Baixo" ou "Indeterminado"
- [ ] **AC-2:** `leads.bant_summary` contém JSON com os 4 campos do BANT (necessity, volume, authority, timing) — campos sem dados ficam `null`, não em branco
- [ ] **AC-3:** Se já existe registro do lead (mesmo `phone`): update, não insert duplicado
- [ ] **AC-4:** Se é lead novo: cria com `source = "zenya-vendedora"`, `channel = "A"`, `status = "novo"`
- [ ] **AC-5:** Leads com dados insuficientes (< 2 sinais BANT) não geram registro no Supabase

### Dados básicos do lead

- [ ] **AC-6:** `leads.phone` = número do WhatsApp do lead (limpo, formato +55...)
- [ ] **AC-7:** `leads.name` preenchido quando identificado na conversa (pode ficar null se não identificado)
- [ ] **AC-8:** `leads.business_type` preenchido quando o nicho for mencionado
- [ ] **AC-9:** `leads.last_contact_at` atualizado a cada nova mensagem

### Qualidade

- [ ] **AC-10:** Extração não atrasa a resposta ao lead — deve ser assíncrona ou em paralelo com o envio (lead não pode esperar pelo Supabase write)
- [ ] **AC-11:** Falha no Supabase write não bloqueia o fluxo principal (erro tratado com `continue on error`)
- [ ] **AC-12:** @qa testa 5 cenários: confeitaria (ICP), clínica (ICP), empresa grande (não-ICP), conversa abortada no meio, lead que já existe

---

## Definition of Done

- [ ] Todos os ACs passando
- [ ] Nenhum lead de teste visível no Supabase (usar número de teste, limpar após)
- [ ] WF01 atualizado e salvo no n8n
- [ ] `work_log.md` atualizado com node ID do novo nó de extração

---

## Tarefas

- [ ] **T1:** @dev — Adicionar nó "Extrair BANT" ao WF01 (Call API OpenAI com structured output)
- [ ] **T2:** @dev — Adicionar nó "Upsert Lead Supabase" (HTTP Request → Supabase REST API)
- [ ] **T3:** @dev — Adicionar condicional `has_sufficient_data` antes do upsert
- [ ] **T4:** @dev — Garantir que falha no T2 não quebre o fluxo principal
- [ ] **T5:** @qa — Testar 5 cenários (AC-12)
- [ ] **T6:** @dev — Limpar dados de teste do Supabase

---

## Dependências

**Depende de:** PC-1.1 (WF01 ativo com soul prompt)

**Desbloqueia:**
- PC-1.4 (Notificação Friday — precisa do score BANT para disparar)
- PC-1.7 (CRM — precisa de leads com BANT no Supabase)

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| n8n WF01 (ID: `IY9g1qHAv1FV8I5D`) | Modificar | Adicionar nós de extração BANT + upsert Supabase |
