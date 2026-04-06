---
epic: Pipeline Comercial Sparkle v1
story: PC-1.7
title: CRM Pipeline — View de estágios e consulta via Friday
status: Done
priority: Média
executor: "@dev (Supabase view + Runtime endpoint) -> @qa -> @po"
sprint: Sprint Pipeline (Semana 2-3)
depends_on: [PC-1.2 (leads com BANT), PC-1.4 (notificações), PC-1.6 (follow-up rastreia estágio)]
unblocks: []
estimated_effort: "3-4h (@dev 2-3h + @qa 1h)"
prd: docs/prd/pipeline-comercial-prd.md
arch_decision: |
  Tabela `leads` já tem TODOS os campos necessários (bant_score, bant_summary, channel, status,
  demo_scheduled_at, demo_completed_at, proposal_sent, proposal_value, closed_at, loss_reason,
  next_followup_at). NÃO criar `commercial_pipeline` separada — seria redundante.
  Entregar:
  1. View SQL `pipeline_view` no Supabase (organiza leads por estágio)
  2. Endpoint GET /cockpit/pipeline no Runtime (Friday pode consultar)
  3. Handler Friday: perguntas como "quais leads aguardando proposta?" respondem com dados reais
---

# Story PC-1.7 — CRM Pipeline: View e Consulta via Friday

## Story

**Como** Mauro,
**Quero** conseguir perguntar para a Friday "quais leads estão em que estágio?" e receber uma resposta real,
**Para que** eu tenha visão do pipeline a qualquer momento sem abrir Supabase ou n8n.

---

## Contexto Técnico

**Estado atual:**
- Tabela `leads` tem todos os campos do pipeline (dados confirmados via Supabase MCP)
- `commercial_pipeline` table: NÃO NECESSÁRIA — `leads` já cobre tudo
- Friday tem capacidade de consultar o Runtime via endpoints (cockpit, reports)
- **Gap:** Não existe endpoint que agrupa leads por estágio, nem handler Friday para consultas de pipeline

**Mapeamento de estágios (via `leads.status`):**

| Status | Estágio | Critério |
|--------|---------|----------|
| `novo` | Novo Lead | Acabou de entrar |
| `qualificado` | Qualificado | bant_score = "Alto" ou "Medio" |
| `demo_agendada` | Demo Agendada | demo_scheduled_at preenchido |
| `proposta_enviada` | Proposta Enviada | proposal_sent = true |
| `fechado` | Cliente | closed_at preenchido, sem loss_reason |
| `perdido` | Perdido | loss_reason preenchido |

**O que esta story implementa:**

1. **View SQL `pipeline_view`** — Supabase view que organiza leads por estágio com contagem e detalhes:
   ```sql
   CREATE VIEW pipeline_view AS
   SELECT
     status AS stage,
     COUNT(*) AS total,
     ARRAY_AGG(JSON_BUILD_OBJECT(
       'name', COALESCE(name, 'Lead sem nome'),
       'phone', phone,
       'business_type', business_type,
       'bant_score', bant_score,
       'next_followup_at', next_followup_at,
       'days_in_stage', EXTRACT(DAY FROM NOW() - updated_at)
     )) AS leads
   FROM leads
   WHERE status NOT IN ('perdido')
   GROUP BY status;
   ```

2. **Endpoint GET /cockpit/pipeline** no Runtime — retorna pipeline_view como JSON. Friday consulta este endpoint.

3. **Handler Friday "pipeline_query"** — interpreta perguntas em linguagem natural sobre o pipeline:
   - "Quais leads aguardando proposta?" → filtra proposta_enviada
   - "Tem follow-up pra fazer hoje?" → filtra next_followup_at ≤ hoje
   - "Quantos leads qualificados?" → conta qualificado
   - "Quem fechou recentemente?" → filtra fechado, últimos 30 dias

4. **Notificação de fechamento** (FR15 do PRD) — quando `status = "fechado"` é detectado, Friday notifica Mauro e aciona checklist de onboarding.

---

## Critérios de Aceitação

### View e endpoint

- [ ] **AC-1:** View `pipeline_view` criada no Supabase com leads agrupados por estágio
- [ ] **AC-2:** GET /cockpit/pipeline retorna JSON com estágios + leads por estágio
- [ ] **AC-3:** Endpoint funcional em ≤ 2 segundos

### Consulta via Friday

- [ ] **AC-4:** Friday responde corretamente para: "quais leads aguardando proposta?"
- [ ] **AC-5:** Friday responde corretamente para: "tem follow-up pra fazer hoje?"
- [ ] **AC-6:** Friday responde corretamente para: "quantos leads qualificados temos?"
- [ ] **AC-7:** Respostas da Friday incluem nomes/números dos leads (não só contagem)

### Notificação de fechamento

- [ ] **AC-8:** Quando `leads.status` é atualizado para "fechado", Friday notifica Mauro no WhatsApp
- [ ] **AC-9:** Notificação de fechamento inclui nome do lead, valor da proposta e instrução para iniciar onboarding
- [ ] **AC-10:** Checklist de onboarding é referenciado na mensagem (link para doc ou instrução para acionar Onboarding PRD)

### Operabilidade celular

- [ ] **AC-11:** Toda a interação com o pipeline pode ser feita pelo WhatsApp via Friday — zero abertura de Supabase

---

## Definition of Done

- [ ] Todos os ACs passando
- [ ] View `pipeline_view` criada no Supabase
- [ ] Endpoint /cockpit/pipeline no Runtime ativo
- [ ] Handler Friday testado com pelo menos 3 perguntas diferentes
- [ ] `work_log.md` atualizado

---

## Tarefas

- [ ] **T1:** @dev — Criar view `pipeline_view` no Supabase via migration
- [ ] **T2:** @dev — Criar endpoint GET /cockpit/pipeline no Runtime (router cockpit)
- [ ] **T3:** @dev — Implementar handler Friday para consultas de pipeline (proactive.py ou novo handler)
- [ ] **T4:** @dev — Implementar detector de fechamento + notificação Friday
- [ ] **T5:** @qa — Testar 5 perguntas diferentes para Friday sobre pipeline
- [ ] **T6:** @qa — Testar notificação de fechamento

---

## Dependências

**Depende de:**
- PC-1.2 (leads com BANT no Supabase — sem isso, pipeline fica vazio)
- PC-1.4 (status atualizados corretamente)
- PC-1.6 (next_followup_at preenchido)

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `supabase/migrations/pipeline_view.sql` | Criar | View pipeline_view |
| `sparkle-runtime/runtime/cockpit/router.py` | Modificar | Adicionar GET /pipeline |
| `sparkle-runtime/runtime/friday/proactive.py` | Modificar | Handler consultas pipeline |
