# Plano de Implementação — Sparkle AIOX
**Versão:** 1.0 | **Criado por:** @architect (Aria) | **Data:** 2026-04-01
**Referência:** [sparkle-constitution.md](architecture/sparkle-constitution.md) | [agent-queue.md](agent-queue.md)

> Este documento é o **como** — o Constitutional Document é o **porquê**.
> Cada item tem responsável, critério de pronto e dependência clara.
> Orion atualiza status aqui ao final de cada sessão de trabalho.

---

## Estado Atual

| O que está pronto | O que está pendente de deploy | O que ainda não existe |
|-------------------|-------------------------------|------------------------|
| Runtime async refactor ✅ | Runtime no VPS (Mauro ação) | Brain com dados reais |
| Brain Fase A handler ✅ | Z-API redirect (Mauro ação) | Fun Personalize integration |
| Constitutional Document v1.1 ✅ | QA re-review patches ✅ | Specialist agent template |
| Pipeline @dev → @qa → @devops ✅ | — | Proactive briefing |

---

## Pipeline Obrigatório

**Toda implementação de código segue este fluxo sem exceção:**

```
Orion (identifica + delega) → @dev (implementa) → @qa (revisa) → @devops (deploya)
```

- Orion **não escreve código diretamente** — identifica o que precisa ser feito e delega ao @dev
- @dev **não deploya** — entrega para @qa revisar
- @qa **não aprova sem testar** — verifica async consistency, lógica, schema
- @devops **não deploya sem @qa aprovado** — gate obrigatório

Se Orion fizer código inline, está violando este pipeline. O Mauro não deveria precisar supervisionar isso.

---

## Sprint 0 — Estabilização (Esta semana, até 2026-04-06)

**Meta:** Runtime rodando em produção. Friday responde pelo Runtime, não pelo n8n.

### S0-01 — Deploy Runtime no VPS
| Campo | Valor |
|-------|-------|
| **Responsável** | @devops + **Mauro** (ação manual) |
| **Agente** | @devops |
| **DoD** | `curl https://[runtime-url]/health` retorna `{"status":"ok"}` |
| **Dependência** | Mauro confirmar credenciais VPS disponíveis |

**Passos @devops:**
1. Verificar `docker-compose.yml` ou `Dockerfile` no Runtime
2. Fazer `git push` para VPS (via SSH ou Coolify)
3. Confirmar que Redis + ARQ worker sobem junto

**Ação Mauro:** Passar acesso SSH ou confirmar Coolify URL para @devops conectar.

---

### S0-02 — Redirecionar Z-API para Runtime
| Campo | Valor |
|-------|-------|
| **Responsável** | **Mauro** (ação manual no painel Z-API) |
| **Agente** | — |
| **DoD** | Mensagem de WhatsApp chega no `runtime/friday/webhook` e é respondida pelo Runtime |
| **Dependência** | S0-01 concluído |

**Ação Mauro:**
1. Painel Z-API → instância Sparkle → "Ao receber mensagem"
2. URL → `https://[runtime-url]/friday/webhook`
3. Desativar workflows n8n: Friday Brain, Friday Notifier, Sparkle Gateway
4. Manter apenas workflows de **cliente** (Plaka, Ensinaja, Confeitaria, Fun Personalize)

---

### S0-03 — Smoke Test End-to-End
| Campo | Valor |
|-------|-------|
| **Responsável** | @qa |
| **Agente** | @qa |
| **DoD** | 5 tipos de mensagem testados com sucesso via WhatsApp |
| **Dependência** | S0-01 + S0-02 |

**Checklist @qa:**
- [ ] Texto simples → Friday responde com `chat` handler
- [ ] "qual o MRR?" → `status_mrr` handler responde com valor correto
- [ ] "anota: teste de smoke" → `create_note` cria nota no Supabase
- [ ] Áudio → transcrição → resposta em áudio (TTS)
- [ ] "Brain, o que você sabe sobre Zenya?" → `brain_query` handler responde

---

## Sprint 1 — Brain Operacional (2026-04-07 a 2026-04-13)

**Meta:** Brain tem dados reais e responde perguntas úteis. Day 7 do 30 Day Proof.

### S1-01 — Carregar primeiros dados no Brain
| Campo | Valor |
|-------|-------|
| **Responsável** | @dev |
| **Agente** | @dev |
| **DoD** | `knowledge_base` tem ≥ 50 registros, Brain responde sobre pelo menos 3 temas |
| **Dependência** | S0-01 |

**@dev implementa handler `brain_ingest`:**
- Aceita texto + fonte + client_id via endpoint `POST /friday/message` com intent `brain_ingest`
- Divide em chunks (500 tokens)
- Gera embedding via OpenAI (se disponível) ou salva só o texto
- Insere na `knowledge_base`

**Dados iniciais para ingestar (Mauro cola via Friday):**
- SOUL.md da Zenya
- System prompts dos clientes ativos
- Constitutional Document (seções relevantes)
- Notas acumuladas no Supabase

---

### S1-02 — Intent `brain_ingest` no dispatcher
| Campo | Valor |
|-------|-------|
| **Responsável** | @dev |
| **Agente** | @dev |
| **DoD** | "Brain, aprende isso: [texto]" cria registro na knowledge_base |
| **Dependência** | — |

**@dev:**
1. Adiciona `brain_ingest` ao `INTENTS` em `dispatcher.py`
2. Regra de classificação: "aprende", "ingesta", "salva no brain", "registra no brain"
3. Extrai `content` e `source` do texto
4. Cria handler `runtime/tasks/handlers/brain_ingest.py`
5. Registra no `registry.py`

---

### S1-03 — QA Brain completo
| Campo | Valor |
|-------|-------|
| **Responsável** | @qa |
| **Agente** | @qa |
| **DoD** | Brain ingesta + consulta funcionam end-to-end via WhatsApp |
| **Dependência** | S1-01 + S1-02 + S0-02 |

---

## Sprint 2 — Clientes Pendentes (2026-04-07 a 2026-04-13, paralelo ao Sprint 1)

**Meta:** Fun Personalize operacional. Ensinaja e Confeitaria desbloqueados quando Mauro agir.

### S2-01 — Fun Personalize: Integração Loja Integrada no Runtime
| Campo | Valor |
|-------|-------|
| **Responsável** | @dev |
| **Agente** | @dev |
| **DoD** | Zenya Fun Personalize consulta pedidos via API Loja Integrada e responde clientes |
| **Dependência** | API key da Julia (já recebida — BLOCK-03) |

**@dev implementa:**
- Handler `loja_integrada_query` no Runtime
- Consulta pedidos por CPF/email via API Loja Integrada
- Integra ao fluxo Zenya da Julia (system prompt já existe no n8n)
- Endpoint para Zenya chamar: `POST /zenya/query-order`

**@qa valida:** consulta pedido real retorna status correto.

---

### S2-02 — Confeitaria Alexsandro: Go-live (quando Mauro agir)
| Campo | Valor |
|-------|-------|
| **Responsável** | **Mauro** → depois @dev |
| **Agente** | @dev (executa após ação do Mauro) |
| **Bloqueante** | Mauro criar instância Z-API e passar token |
| **DoD** | Zenya Alexsandro responde pelo WhatsApp do negócio |

**Sequência após Mauro passar o token:**
1. @dev cria Chatwoot inbox
2. @dev configura `id_conversa_alerta` e número escalonamento
3. @dev ativa workflows n8n
4. @qa valida conversa de teste

---

### S2-03 — Ensinaja Douglas: Go-live (quando Douglas responder)
| Campo | Valor |
|-------|-------|
| **Responsável** | **Mauro** → depois @dev |
| **Agente** | @dev (executa após ação do Mauro) |
| **Bloqueante** | Douglas responder com valores dos cursos e horários |

**Após Douglas responder:**
1. @dev atualiza KB com dados dos cursos
2. @dev ativa workflows n8n
3. @dev cria Google Sheets `ensina_leads`
4. @qa valida fluxo completo

---

## Sprint 3 — Maturidade do Runtime (2026-04-14 a 2026-04-20)

**Meta:** Friday faz briefings proativos. Day 20 do 30 Day Proof.

### S3-01 — Friday Briefing Diário Automático
| Campo | Valor |
|-------|-------|
| **Responsável** | @dev |
| **Agente** | @dev |
| **DoD** | Mauro recebe briefing às 8h todo dia pelo WhatsApp, sem pedir |
| **Dependência** | S0-02 (Runtime em produção) |

**Status:** Handler `daily_briefing` já existe e está correto. Falta apenas:
- Confirmar que o ARQ cron job está configurado em `worker.py` para 11h UTC (8h Brasília)
- Confirmar `MAURO_WHATSAPP` nas variáveis de ambiente do VPS
- @qa valida disparo manual antes de ativar o cron

---

### S3-02 — Friday Briefing Semanal Automático
| Campo | Valor |
|-------|-------|
| **Responsável** | @dev |
| **Agente** | @dev |
| **DoD** | Briefing semanal chega todo domingo às 8h |
| **Dependência** | S3-01 |

**Status:** Handler `weekly_briefing` já existe. Falta confirmar cron job no `worker.py`.

---

### S3-03 — Template de Agente Especialista (Supabase)
| Campo | Valor |
|-------|-------|
| **Responsável** | @architect → @dev |
| **Agente** | @architect → @dev (sequencial) |
| **DoD** | Novo agente pode ser criado via API sem alterar código — só inserir registro no Supabase |
| **Dependência** | — |

**@architect define schema:**
```sql
agents (
  id, name, system_prompt, model, max_tokens,
  client_id, tools jsonb, active bool, created_at
)
```

**@dev implementa:**
- `worker.py` lê agente do Supabase em runtime
- Endpoint `POST /agent/invoke` — chama agente por `agent_id`
- `@qa` valida criação de agente novo sem deploy

---

## Sprint 4 — Inteligência (2026-04-21 a 2026-04-30)

**Meta:** Primeiro ciclo de `gap_report`. Day 30 do 30 Day Proof.

### S4-01 — Observer Pattern: Aprendizado de Conversas
| Campo | Valor |
|-------|-------|
| **Responsável** | @dev |
| **Agente** | @dev |
| **DoD** | Após cada conversa Zenya, Brain extrai aprendizado e registra |
| **Dependência** | S1-01 (Brain operacional) |

**@dev implementa:**
- Trigger pós-conversa: chama `learn_from_conversation` handler (já existe)
- Handler extrai: intenção do cliente, produto consultado, dúvida não respondida
- Salva na `knowledge_base` com `source = "conversation_learning"`

---

### S4-02 — Gap Report: Primeira Geração
| Campo | Valor |
|-------|-------|
| **Responsável** | @dev |
| **Agente** | @dev |
| **DoD** | Friday envia para Mauro relatório de gaps semanais do Brain |
| **Dependência** | S4-01 (pelo menos 1 semana de dados) |

**@dev implementa handler `gap_report`:**
- Agrupa conversas onde Brain não tinha resposta
- Claude Opus analisa padrões: quais temas faltam no Brain?
- Gera lista priorizada de gaps
- Envia via WhatsApp para Mauro toda segunda-feira

---

## Backlog — Após Sprint 4

Itens identificados, sem data ainda:

| Item | Descrição | Quem |
|------|-----------|------|
| Character Runtime | Personagens como objetos Supabase (Finch, Pip) | @architect + @dev |
| Member State Engine | Track estado de 1000+ membros da comunidade | @architect + @dev |
| Vitalis Zenya | Upsell após análise de tráfego | Mauro (decisão comercial) |
| SparkleX | Plataforma de membros com IA | Fase futura |

---

## Como Usar Este Plano

**A cada sessão:**
1. Orion lê este arquivo + `agent-queue.md`
2. Identifica todos os itens desbloqueados (sem dependências pendentes)
3. Lança agentes em paralelo
4. Atualiza status aqui ao final

**Critério de conclusão de sprint:** todos os DoDs da sprint marcados como ✅

**Quando bloquear:** apenas quando há dependência explícita de Mauro (ação manual no painel) ou de dado externo (resposta de cliente)

---

*Aria — arquitetando o futuro 🏗️*
