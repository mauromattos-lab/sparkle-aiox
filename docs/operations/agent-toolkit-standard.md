# Agent Toolkit Standard — Sparkle AIOX

**Versão:** 1.0 | **Autor:** Orion | **Data:** 2026-03-29
**Uso obrigatório:** Incluir contexto relevante deste documento em TODO prompt de agente.

> Este documento resolve o problema de 25% de utilização de capacidade.
> Agentes não usam ferramentas que não sabem que existem.

---

## MCPs Disponíveis — USE ATIVAMENTE

### EXA (busca web real-time)
**Quando usar:** TODA pesquisa de mercado, concorrentes, preços, benchmarks, tecnologias, notícias.
**Nunca substituir por:** ler arquivos locais quando a informação precisa ser atual.

```
mcp__docker-gateway__web_search_exa
```

**Exemplos de uso:**
- @analyst pesquisando players BR: use EXA, não só arquivos locais
- @architect avaliando tecnologia: use EXA para benchmarks atuais
- @devops verificando status de MCP: use EXA para release notes

---

### Context7 (documentação de bibliotecas em tempo real)
**Quando usar:** TODA vez que @dev ou @architect precisar de API reference, tipos, exemplos de código.
**Nunca substituir por:** conhecimento desatualizado da versão de treinamento.

```
mcp__docker-gateway__resolve-library-id  → obter ID da biblioteca
mcp__docker-gateway__get-library-docs    → buscar documentação
```

**Exemplos de uso:**
- @dev implementando endpoint n8n: consultar Context7 para versão atual da API
- @architect desenhando com Next.js 14: consultar Context7 para App Router
- @dev usando Supabase SDK: Context7 para métodos atuais

---

### Apify (web scraping, social media, dados estruturados)
**Quando usar:** Extrair dados de qualquer website, Instagram, TikTok, LinkedIn, e-commerce.
**Workaround bug de secrets:** As credenciais estão hardcoded em `~/.docker/mcp/catalogs/docker-mcp.yaml`.

```
mcp__docker-gateway__search-actors       → descobrir Actor disponível
mcp__docker-gateway__call-actor          → executar scraper
mcp__docker-gateway__get-actor-output    → obter resultados
mcp__docker-gateway__apify-slash-rag-web-browser  → browsing com RAG
```

**Exemplos de uso:**
- @analyst scraping Instagram de concorrente: use Apify Instagram scraper Actor
- @analyst extraindo cardápio de site de cliente: use Apify
- @devops enriquecendo prospect com dados da web: use Apify

---

### Playwright (browser automation, screenshots, testes)
**Quando usar:** Screenshots de páginas, testes E2E, preencher formulários, validar UI.

```
mcp__playwright__*
```

**Exemplos de uso:**
- @qa validando landing page visualmente: screenshot via Playwright
- @qa testando fluxo de login do portal: Playwright automação
- @ux verificando responsividade: Playwright em diferentes viewports

---

### Supabase MCP (banco de dados)
**Quando usar:** TODA operação no banco — queries, migrations, verificações.

```
mcp__supabase__execute_sql          → queries SQL
mcp__supabase__apply_migration      → executar migration
mcp__supabase__list_tables          → ver tabelas existentes
mcp__supabase__get_logs             → logs do Supabase
```

**Project ID:** `gqhdspayjtiijcqklbys`

---

## Groq — Inferência Barata no n8n
**Quando usar:** Workflows n8n com tarefas low-criticidade (classificação simples, formatação, triagem).
**Não usar para:** decisões complexas, geração criativa, análise profunda.

- Credencial configurada no n8n: Groq API (ID: `VYmnIoOkqduRywZL`)
- Custo: $0,05/M tokens (vs ~$3/M do GPT-4o)
- Modelo recomendado: `llama-3.1-8b-instant`

---

## Mega Brain — Conceitos a Implementar

### Pipeline de Ingestão (PRIORIDADE FASE 2)
Qualquer formato de entrada → conhecimento estruturado para KB da Zenya.
- Cliente manda áudio, PDF, cardápio, catálogo → processa → insere na `zenya_knowledge_base`
- Base: `github.com/thiagofinch/mega-brain` — repositório público, clonar e adaptar

### DNA Schemas (PRIORIDADE FASE 2)
Cada cliente Zenya deve ter um "DNA do negócio":
- 5 dimensões: Identidade, Produtos/Serviços, Público, Tom de Voz, Regras Operacionais
- Armazenado no Supabase, versionado, usado para personalização automática

### Cargo Agents (CRIAR COMO SQUADS)
Agentes por função de negócio — mais específicos que os agentes AIOS genéricos:
- **Aquisição**: captura leads, qualifica, nutre
- **Conversão**: proposta, follow-up, fechamento
- **Entrega**: onboarding, configuração, go-live
- **Otimização**: análise de dados, ajuste de performance
- **Financeiro**: billing, inadimplência, relatório de caixa

---

## Community Skills — Status Real

> Os comandos `npx skills add` documentados anteriormente eram aspiracionais e não existem como pacotes reais.
> O sistema de skills do Claude Code usa arquivos `.md` — os agentes AIOS já estão instalados como skills em `~/.claude/settings.json`.

### Skills disponíveis agora (via `/skill-name` ou `@agente`):

| Skill | Invocação | Função |
|-------|-----------|--------|
| @dev | `AIOS:agents:dev` | Implementação, código, workflows |
| @qa | `AIOS:agents:qa` | Validação e testes |
| @analyst | `AIOS:agents:analyst` | Pesquisa e dados |
| @architect | `AIOS:agents:architect` | Arquitetura de sistema |
| @devops | `AIOS:agents:devops` | Infraestrutura, CI/CD, MCP |
| @po | `AIOS:agents:po` | Product Owner |
| @sm | `AIOS:agents:sm` | Scrum Master, gestão de fila |
| @ux | `AIOS:agents:ux-design-expert` | UX, design, copy |
| @squad-creator | `AIOS:agents:squad-creator` | Criação de squads AIOS |

### Para adicionar novo agente/skill:

Criar arquivo `.md` em `~/.claude/skills/` com o formato:
```markdown
---
name: nome-do-skill
description: descrição de quando usar
---

# Conteúdo do skill / prompt do agente
```

Depois referenciar em `~/.claude/settings.json` na seção `skills`.

---

## Roteamento de Modelos — Opus / Sonnet / Haiku / Groq

**Regra de ouro:** Use o modelo mais barato que entrega a qualidade necessária. Opus para pensar, Sonnet para construir, Haiku para carregar, Groq para triar.

| Tipo de Task | Modelo | Justificativa |
|-------------|--------|---------------|
| Decisão arquitetural, planejamento estratégico, síntese de múltiplas perspectivas | **Opus** (claude-opus-4-6) | Alta complexidade, não repetitivo, erro tem impacto grande |
| Implementação de código, geração de copy, análise profunda, geração de workflows | **Sonnet** (claude-sonnet-4-6) | Equilíbrio qualidade/custo, maioria das tarefas |
| Verificação de formato, extração simples de dados, geração de resumo curto, tarefas repetitivas | **Haiku** (claude-haiku-4-5) | Baixo custo, alta velocidade, sem necessidade de raciocínio profundo |
| Classificação binária, triagem de mensagens, detecção de intent simples (n8n) | **Groq** (llama-3.1-8b-instant) | $0,05/M tokens, latência < 1s, dentro do n8n via credencial configurada |

### Por agente — modelo padrão

| Agente | Modelo Primário | Modelo para Tasks Simples |
|--------|----------------|--------------------------|
| Orion | Sonnet (orquestração) | — |
| @architect (Aria) | Opus (decisão arquitetural) | Sonnet (documentação) |
| @analyst (Nova) | Sonnet (pesquisa + síntese) | Haiku (extração de dados) |
| @dev (Zeus) | Sonnet (código) | Haiku (verificações) |
| @qa (Shield) | Sonnet (análise de qualidade) | Haiku (checklists mecânicos) |
| @ux | Sonnet (design + copy) | — |
| @devops (Forge) | Sonnet (infra) | Haiku (health checks) |
| @po / @pm / @sm | Sonnet (planejamento) | — |
| Zenya (produção, n8n) | Groq (triagem) → Sonnet (resposta complexa) | — |

### Quando escalar para Opus

Escale para Opus quando a task atender 2+ dos seguintes critérios:
- Decisão irreversível (arquitetura, contratação de agente, mudança constitucional)
- Múltiplas perspectivas precisam ser sintetizadas (5+ fontes de input)
- Erro tem custo de > 2h de retrabalho para corrigir
- Task não tem padrão anterior para seguir (genuinamente inédita)

---

## Use or Lose — Critério de Ativação Obrigatória

**Princípio:** Nenhuma ferramenta, MCP, agente ou skill existe para ser "um arquivo legal na estrutura". Se foi adicionado, tem critério de uso.

### Critério por tipo

| Tipo | Critério de uso ativo | Ação se não usado |
|------|-----------------------|-------------------|
| MCP (EXA, Apify, Context7, etc.) | Usado em ≥ 1 task real por semana | @devops revisa: ainda necessário? Se não → remover |
| Agente especialista | Recebe ≥ 1 task por mês | @sm revisa: escopo ainda existe? Se não → deprecar |
| Skill de agente | Invocada em ≥ 1 situação real por mês | @squad-creator revisa: skill ainda relevante? |
| Template de projeto | Instanciado ≥ 1 vez em 60 dias | @sm revisa: simplificar ou remover |

### Checklist mensal (responsável: @sm)

```
[ ] Verificar uso de cada MCP nos logs do mês
[ ] Verificar tasks por agente no Supabase (agent_workload view)
[ ] Listar ferramentas com zero uso
[ ] Para cada item zerado: propor remoção ou justificativa de retenção
[ ] Apresentar relatório para Orion/Mauro na Weekly Ops
```

### Quando adicionar nova ferramenta/agente

Antes de adicionar: responder estas 3 perguntas:
1. **Quem vai usar?** — agente específico identificado, não "pode ser útil pra todos"
2. **Para qual task concreta?** — exemplo real, não hipotético
3. **O que acontece se não tivermos?** — impacto mensurável, não "seria mais fácil"

Se não conseguir responder as 3: não adicionar agora.

---

## Regras de Aplicação por Tipo de Agente

| Agente | Ferramentas obrigatórias |
|--------|--------------------------|
| @analyst | EXA (pesquisa web), Supabase MCP (dados internos) |
| @dev | Context7 (docs), Supabase MCP (banco), Playwright (testes) |
| @architect | EXA (benchmarks), Context7 (APIs), WebFetch (specs) |
| @qa | Playwright (testes visuais), Supabase MCP (validar dados) |
| @devops | Supabase MCP, EXA (release notes, status pages) |
| @ux | Playwright (screenshots), EXA (referências visuais) |
| @po | EXA (pesquisa de mercado, competitors) |

---

## Inference.sh — DECISÃO: NÃO USAR AGORA

**Avaliado em 2026-03-27. Veredicto permanente:**
inference.sh é runtime de agentes, NÃO é inferência barata.
Premature para a Sparkle. Reavaliar quando tiver 20+ clientes.

**Para inferência barata:** usar Groq (já configurado no n8n).

---

---

## Histórico de Atualizações

| Data | Autor | Mudança |
|------|-------|---------|
| 2026-03-29 | Orion | Versão inicial — MCPs, Groq, Mega Brain, Community Skills, Regras por agente |
| 2026-03-30 | @architect (Aria) | Adicionado: roteamento de modelos (Opus/Sonnet/Haiku/Groq por tipo de task); critério Use or Lose com checklist mensal e critério de adição de nova ferramenta |

*Atualizar este documento quando novos MCPs, skills ou agentes forem adicionados.*
*Orion deve referenciar este documento ao escrever prompts de agentes.*
*Todo agente lê este documento via `required_reading` no agent_registry.*
