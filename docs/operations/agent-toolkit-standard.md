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

## Community Skills — Instalar

```bash
# Code Reviewer — revisão automática de código gerado por agentes
npx skills add anthropics/claude-code --skill code-reviewer

# Frontend Design — UI/UX para landing, portal, dashboards
npx skills add vercel-labs/agent-skills --skill frontend-design

# Browser Use — scraping dinâmico via browser
npx skills add anthropics/claude-code --skill browser-use
```

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

*Atualizar este documento quando novos MCPs ou skills forem adicionados.*
*Orion deve referenciar este documento ao escrever prompts de agentes.*
