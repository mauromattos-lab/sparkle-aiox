---
epic: Pipeline Comercial Sparkle v1
story: PC-1.6
title: Follow-up D0→D+7 — Sequência pós-demo automática
status: Ready for Dev
priority: Alta
executor: "@dev (n8n novo WF) -> @qa -> @po"
sprint: Sprint Pipeline (Semana 2)
depends_on: [PC-1.2 (leads no Supabase com bant_summary), PC-1.4 (notificação Friday)]
unblocks: [PC-1.7 (CRM rastreia estágio follow-up)]
estimated_effort: "5-6h (@dev 4h + @qa 2h)"
prd: docs/prd/pipeline-comercial-prd.md
arch_decision: |
  Novo workflow n8n "PC-1.6 Follow-up Pipeline".
  Trigger: webhook disparado manualmente pelo Mauro (ou por PC-1.7 quando demo_completed_at é preenchido).
  Sequência: D0 (até 2h), D+2, D+4, D+7 — usando AI Agent para personalizar cada mensagem com
  base em leads.bant_summary.
  Envio: Z-API número +5512982201239 (Zenya Vendedora) — lead reconhece o número.
  Parada: quando lead responde (qualquer mensagem) → cancelar próximas mensagens da sequência.
  Máximo 4 toques. 4 ângulos distintos.
---

# Story PC-1.6 — Follow-up D0→D+7

## Story

**Como** Mauro (vendedor),
**Quero** que leads que passaram pela demo recebam follow-up automático e personalizado nos 7 dias seguintes,
**Para que** eu não perca leads quentes por esquecimento ou falta de tempo.

---

## Contexto Técnico

**Estado atual:**
- Existe um workflow "Sparkle Prospect Follow-up" que verifica leads estagnados, mas:
  - Usa staging/fonte diferente (não integrado com `leads` table do pipeline)
  - Não tem a sequência D0→D+7 com ângulos distintos
  - Não personaliza usando BANT do lead
- `leads` table tem: `demo_completed_at`, `bant_summary`, `next_followup_at`, `status`, `phone`, `name`, `business_type`

**O que esta story implementa:**

**Workflow: "PC-1.6 — Follow-up Pipeline"**

```
Trigger (webhook/schedule)
  └→ Buscar leads com demo_completed_at preenchido e status != "fechado" e status != "perdido"
       └→ Para cada lead, verificar qual mensagem enviar (D0/D2/D4/D7)
            └→ Gerar mensagem personalizada (AI Agent com bant_summary)
                 └→ Enviar via Z-API
                      └→ Atualizar next_followup_at + incrementar followup_count
```

**Sequência de mensagens (4 ângulos):**

| Dia | Ângulo | Gatilho |
|-----|--------|---------|
| D0 (até 2h após demo) | Proposta + problema do lead | `demo_completed_at` preenchido |
| D+2 | Valor ("o que mais te chamou atenção?") | 2 dias sem resposta |
| D+4 | Prova social (case do nicho identificado) | 4 dias sem resposta |
| D+7 | Encerramento leve | 7 dias sem resposta |

**Personalização via BANT:**
- D0: usa `bant_summary.necessity` para nomear o problema na proposta
- D+2: usa `business_type` para contextualizar o valor
- D+4: gera case fictício (mas plausível) do mesmo `business_type`
- D+7: mensagem padrão com nome do lead

**Parada da sequência:**
- Quando lead responde qualquer mensagem → `status = "respondeu"` → próximas mensagens canceladas
- Quando `demo_scheduled_at` é preenchido → `status = "demo_agendada"` → sequência não dispara

---

## Critérios de Aceitação

### Sequência D0

- [ ] **AC-1:** Quando `demo_completed_at` é preenchido para um lead, D0 é enviado em até 2h
- [ ] **AC-2:** Mensagem D0 usa `bant_summary.necessity` — menciona o problema específico do lead
- [ ] **AC-3:** Mensagem D0 inclui link de proposta ou CTA claro (responder para confirmar interesse)

### Sequência D+2, D+4, D+7

- [ ] **AC-4:** D+2 enviado se lead não respondeu, com ângulo de valor contextualizado
- [ ] **AC-5:** D+4 enviado se lead ainda não respondeu, com ângulo de prova social do nicho
- [ ] **AC-6:** D+7 enviado como último toque — tom de encerramento leve, sem pressão
- [ ] **AC-7:** Cada mensagem tem ângulo diferente — não são repetições

### Parada inteligente

- [ ] **AC-8:** Se lead responde qualquer mensagem da sequência, próximas mensagens NÃO são enviadas
- [ ] **AC-9:** `leads.status` é atualizado para "respondeu" quando lead responde
- [ ] **AC-10:** Máximo 4 mensagens por lead — sequência não pode exceder D+7

### Qualidade

- [ ] **AC-11:** Mensagens chegam em horário comercial (8h-20h) — D0 pode ser exceção se demo foi no horário
- [ ] **AC-12:** Tom natural de WhatsApp — não parecer disparo em massa
- [ ] **AC-13:** Se `bant_summary` está incompleto, usar fallback genérico sem quebrar fluxo

### Teste

- [ ] **AC-14:** @qa testa sequência completa com lead de teste (não cliente real)
- [ ] **AC-15:** @qa verifica que resposta do lead cancela as próximas mensagens

---

## Definition of Done

- [ ] Todos os ACs passando
- [ ] Workflow salvo e ativo no n8n
- [ ] Testado com número de teste — nenhum cliente real impactado
- [ ] `work_log.md` atualizado com ID do novo workflow

---

## Tarefas

- [ ] **T1:** @dev — Criar workflow "PC-1.6 Follow-up Pipeline" no n8n
- [ ] **T2:** @dev — Implementar query Supabase para buscar leads com follow-up pendente
- [ ] **T3:** @dev — Criar nó AI Agent para personalizar cada mensagem (D0/D2/D4/D7) com BANT
- [ ] **T4:** @dev — Implementar envio via Z-API (+5512982201239)
- [ ] **T5:** @dev — Implementar atualização de `next_followup_at` e controle de sequência
- [ ] **T6:** @dev — Implementar detector de resposta (webhook Chatwoot → cancelar sequência)
- [ ] **T7:** @dev — Adicionar restrição de horário comercial
- [ ] **T8:** @qa — Testar sequência completa + parada por resposta + não-impacto em clientes reais

---

## Dependências

**Depende de:**
- PC-1.2 (leads com bant_summary no Supabase)
- `demo_completed_at` ser preenchido — manual pelo Mauro inicialmente (via Friday ou Supabase)

**Desbloqueia:**
- PC-1.7 (rastrear estágio follow-up no pipeline view)

---

## Nota de implementação

O campo `demo_completed_at` precisa ser preenchido para disparar D0. No início, isso pode ser manual (Mauro preenche via Friday: "friday, demo com [nome] concluída"). Uma automação mais sofisticada (detectar via Calendly) é incremento futuro.

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| n8n WF-PC16 (novo) | Criar | Workflow de follow-up sequencial D0→D+7 |
