---
epic: EPIC-ONBOARDING — Zenya Atendente Onboarding Pipeline
story: ONB-2
title: Intake Automatico — Scrape + Formulario WhatsApp
status: Done
priority: P0 — Bloqueador (ONB-3 depende dos dados coletados aqui)
executor: @dev (implementacao)
sprint: Sprint 9 (2026-04-07+)
architecture: docs/architecture/zenya-onboarding-architecture.md
depends_on: []
unblocks: [ONB-3]
estimated_effort: 8-12h @dev
---

# Story ONB-2 — Intake Automatico: Scrape + Formulario WhatsApp

## Story

**Como** pipeline de onboarding,
**Quero** coletar informacoes do negocio do cliente de forma automatica (scrape de site e Instagram) e complementar com um formulario curto via WhatsApp,
**Para que** a configuracao da Zenya seja baseada em dados reais do negocio, nao em palpites, e o cliente precise responder no maximo 5-8 perguntas.

---

## Contexto Tecnico

**Por que agora:** A qualidade da Zenya depende diretamente da qualidade dos dados de intake. O benchmark mostra que 67% dos chatbots falham por base de conhecimento insuficiente. O modelo hibrido (scrape automatico + micro-formulario) reduz a friccao do cliente em ~70% comparado com formularios longos.

**O que ja existe:**
- `brain_ingest` handler — funcional para scrape de site (testado no SUB-6)
- `extract_client_dna` handler — funcional (8 categorias de DNA)
- Apify Instagram Actor — disponivel via Docker MCP
- Z-API — configurado e funcional para envio de mensagens

**O que falta (escopo desta story):**
1. Handler `intake_form_whatsapp` que envia perguntas sequenciais via Z-API e salva respostas
2. Handler `scrape_instagram` que usa Apify para extrair dados do perfil Instagram do cliente
3. Templates de perguntas por vertical (confeitaria, saude, educacao, e-commerce, generico)
4. Consolidacao de dados em `client_intake` (tabela nova ou JSONB)
5. Integracao com o pipeline de onboarding (disparo automatico apos gate 1)

**Decisao de PM:** Formulario via WhatsApp (perguntas diretas, uma por vez). Nao Google Forms, nao formulario web. O cliente ja esta no WhatsApp — mandar link externo e friccao.

**Benchmark:** Maximo 8 perguntas. Mais que isso, PME nao responde (taxa de completude cai de 70% para 20%).

---

## Templates de Perguntas por Vertical

### Template Generico (fallback)

1. Qual o horario de funcionamento do seu negocio?
2. Quais sao os 3 servicos/produtos mais procurados?
3. Qual o diferencial do seu negocio (o que voce responde quando perguntam "por que voce e diferente")?
4. Tem alguma pergunta que os clientes SEMPRE fazem? Qual?
5. Quando um cliente quer falar com voce diretamente, como prefere ser contatado?

### Template Confeitaria/Gastronomia

1. Qual o horario de funcionamento e entrega?
2. Quais os 3 produtos mais vendidos?
3. Voce trabalha com encomendas? Qual o prazo minimo?
4. Tem cardapio digital ou tabela de precos? (se sim, pode enviar aqui)
5. Qual pergunta os clientes SEMPRE fazem?
6. Faz entrega propria ou usa app?

### Template Saude/Estetica/Otica

1. Qual o horario de atendimento?
2. Quais os 3 servicos mais procurados?
3. Aceita convenio/plano? Quais?
4. Como funciona o agendamento hoje?
5. Qual pergunta os clientes SEMPRE fazem?

### Template Educacao

1. Qual o horario de funcionamento e atendimento?
2. Quais cursos/series voce oferece?
3. Como funciona a matricula?
4. Qual o canal principal de comunicacao com pais/alunos?
5. Qual pergunta os pais SEMPRE fazem?

### Template E-commerce

1. Quais os 3 produtos mais vendidos?
2. Qual o prazo medio de entrega?
3. Aceita troca/devolucao? Como funciona?
4. Quais formas de pagamento aceita?
5. Qual pergunta os clientes SEMPRE fazem no WhatsApp?

---

## Criterios de Aceitacao

### Scrape automatico (site)

- [x] **AC-1.1:** Quando fase `intake` inicia, o sistema dispara automaticamente `brain_ingest` com `source_type=website` e `source_ref=site_url` do cliente
- [x] **AC-1.2:** Se site_url esta vazio ou inacessivel, step falha graciosamente e flaga `scrape_site_failed=true` no context — nao bloqueia o pipeline
- [x] **AC-1.3:** Dados do scrape sao salvos em `brain_raw_ingestions` e `brain_chunks` com `client_id` correto

### Scrape automatico (Instagram)

- [x] **AC-2.1:** Se `instagram_url` esta no context, o sistema dispara scrape via Apify Actor (Instagram Profile Scraper)
- [x] **AC-2.2:** Dados extraidos: bio, posts recentes (ultimos 10), hashtags frequentes, horarios de postagem
- [x] **AC-2.3:** Dados do Instagram sao ingeridos no Brain como chunks com `source_type=instagram`
- [x] **AC-2.4:** Se `instagram_url` esta vazio, step e pulado silenciosamente (nao e obrigatorio)

### Formulario WhatsApp

- [x] **AC-3.1:** Task type `intake_form_whatsapp` registrado no task registry
- [x] **AC-3.2:** O handler envia perguntas uma por vez via Z-API para o telefone do cliente, esperando resposta antes de enviar a proxima
- [x] **AC-3.3:** O template de perguntas e selecionado automaticamente baseado no `business_type` do cliente (confeitaria, saude, educacao, e-commerce, ou generico como fallback)
- [x] **AC-3.4:** Respostas do cliente sao salvas em `client_intake` (JSONB no campo `intake_data` de `onboarding_workflows` fase intake)
- [x] **AC-3.5:** Se cliente nao responde uma pergunta em 24h, lembrete automatico: "Oi [nome], estamos configurando sua Zenya! So falta responder a pergunta anterior para continuarmos."
- [x] **AC-3.6:** Se cliente nao responde apos 2 lembretes (48h), marcar intake como `partial` e continuar com dados disponiveis. Friday alerta Mauro.
- [x] **AC-3.7:** Se telefone do cliente esta vazio, step e pulado. Log warning. Pipeline continua so com dados de scrape.

### Consolidacao

- [x] **AC-4.1:** Apos scrape (site + Instagram) e formulario (mesmo que parcial), sistema consolida tudo em `client_intake` no context da `onboarding_workflows`
- [x] **AC-4.2:** O consolidador gera um `intake_summary` (JSON) com: dados do site, dados do Instagram, respostas do formulario, e um campo `completeness_score` (0-100%) baseado em quantas fontes foram coletadas
- [x] **AC-4.3:** `completeness_score >= 30%` (pelo menos 1 fonte com dados) marca `intake_complete = true` e gate 2 pode passar

### Paralelismo

- [x] **AC-5.1:** Scrape de site, scrape de Instagram, e envio do formulario rodam em PARALELO (nao sequencial)
- [x] **AC-5.2:** Consolidacao roda assim que QUALQUER fonte retornar dados (enriquecimento progressivo — nao espera todas)

---

## Definition of Done

1. Todas as ACs de 1 a 5 marcadas como `[x]`
2. Teste com cliente sintetico usando `https://sparkleai.tech` como site e sem Instagram: scrape funciona, formulario e enviado (ou pulado se sem telefone), intake_complete = true
3. Templates de perguntas por vertical estao salvos no codigo (nao hardcoded em handler — configuravel)
4. Nenhum dado de cliente real foi modificado
5. Nenhuma mensagem Z-API foi enviada para numero real
6. @qa validou consolidacao via queries no Supabase

---

## O que NAO esta no escopo

- Entrevista conversacional com agente IA (Fase 2)
- Upload de documentos pelo cliente (Fase 2)
- Formulario web / painel Mission Control (Fase 2)
- Scrape de Google Business (Fase 2)
- Scrape de TikTok ou outras redes (Fase 3)

---

## Arquivos Afetados

| Arquivo | Operacao |
|---------|----------|
| `sparkle-runtime/runtime/tasks/handlers/intake_form_whatsapp.py` (NOVO) | Handler de formulario WhatsApp |
| `sparkle-runtime/runtime/tasks/handlers/scrape_instagram.py` (NOVO) | Handler de scrape Instagram via Apify |
| `sparkle-runtime/runtime/onboarding/intake_templates.py` (NOVO) | Templates de perguntas por vertical |
| `sparkle-runtime/runtime/onboarding/consolidator.py` (NOVO) | Consolidador de intake |
| `sparkle-runtime/runtime/tasks/registry.py` | Registrar `intake_form_whatsapp`, `scrape_instagram` |

---

## Tabelas Afetadas

| Tabela | Operacao |
|--------|----------|
| `onboarding_workflows` | UPDATE (intake_data JSONB, intake_complete flag) |
| `brain_raw_ingestions` | INSERT (scrape site e Instagram) |
| `brain_chunks` | INSERT (chunks de site e Instagram) |
| `runtime_tasks` | INSERT (tasks de intake) |

---

*Story criada por Morgan (@pm) em 2026-04-05.*
