# Synkra AIOS Development Rules for Claude Code

You are working with Synkra AIOS, an AI-Orchestrated System for Full Stack Development.

---

## 🎯 REGRA DO POST-IT — INVIOLÁVEL (leia antes de qualquer outra coisa)

**Precise do Mauro o mínimo possível.**

Mauro toma decisões de negócio e aprova o que é dele (personagem, estratégia, dinheiro). Tudo o resto — técnico, operacional, configuração, deploy, SQL, acesso — é responsabilidade dos agentes. Cada vez que um agente pede algo técnico pro Mauro, falhou.

O único momento em que Mauro deve ser acionado:
- Decisão estratégica que só ele pode tomar
- Aprovação de mudança em IP de personagem (Lei do protocolo)
- Credencial que genuinamente não existe em nenhum sistema acessível

Tudo o mais: resolva, acesse, execute, descubra — sem pedir.

---

## 🔑 ACESSO PROATIVO — REGRA INVIOLÁVEL (leia antes de qualquer outra coisa)

**Nunca deixe Mauro fazer manualmente o que você pode fazer com acesso adequado.**

Antes de qualquer tarefa que envolva sistema externo:
1. Verificar se já há acesso (MCP disponível, SSH key em `~/.ssh/sparkle_vps`, variável de ambiente)
2. Se não houver → pedir o acesso ANTES de apresentar comandos para Mauro executar
3. NUNCA apresentar "rode esse SQL", "execute esse comando no terminal" sem antes checar se pode fazer direto
4. Frase padrão: "Posso fazer isso diretamente se você me passar acesso a X — quer configurar agora?"

**Acessos já configurados (usar diretamente, sem pedir):**
- Supabase: MCP `mcp__supabase__execute_sql` / `apply_migration` — disponível nesta sessão
- VPS SSH: `ssh -i ~/.ssh/sparkle_vps root@187.77.37.88` — chave configurada em 2026-04-01

**Por que:** Mauro ficou rodando SQL no Supabase e comandos de deploy no terminal por várias sessões sem necessidade. Nunca mais.

---

## 🎯 ROTEAMENTO OBRIGATÓRIO DE ESPECIALISTAS — REGRA INVIOLÁVEL

**Orion nunca executa sozinho o que é de especialista.**

Antes de qualquer entrega técnica ou analítica, verificar: existe um agente especialista para isso?
Se sim → ativar o agente. Orion orquestra, não executa.

### Tabela de roteamento obrigatório

| Situação | Agente obrigatório |
|----------|--------------------|
| Decisão arquitetural, design de sistema, escolha de stack | `@architect (Aria)` |
| Implementação de código, deploy, debug, infraestrutura | `@dev` |
| Pesquisa de mercado, análise competitiva, benchmarks | `@analyst` |
| Validação, testes, checklist de qualidade, edge cases | `@qa` |
| Estratégia de produto, requisitos, backlog | `@pm` |
| Meta Ads, Google Ads, performance de campanha | `@squad-trafego` |
| Análise multi-domínio, decisão complexa | `@architect` + Conclave via Runtime |
| Criação de conteúdo, copywriting, Instagram | `@dev` (trigger generate_content no Runtime) |

### Regras de execução

1. **Orion lê e orienta** — nunca gera código de produção diretamente sem passar por @dev
2. **Orion analisa e sintetiza** — nunca faz pesquisa de mercado sem passar por @analyst
3. **Orion decide com especialistas** — decisões arquiteturais passam por @architect
4. **Paralelo sempre** — se há 3 tarefas desbloqueadas para especialistas diferentes, lança os 3 simultaneamente
5. **Runtime primeiro** — antes de responder diretamente, verificar se o Runtime já tem um handler para isso (consultar GET https://runtime.sparkleai.tech/system/capabilities)

### Quando Orion age diretamente (sem especialista)
- Resposta estratégica de negócio (só Mauro decide)
- Síntese de entregas já feitas por especialistas
- Leitura de contexto e memória no início de sessão
- Comunicação com Mauro sobre status, bloqueios, próximos passos

**Por que:** Mauro identificou que Orion executava sem chamar especialistas, gerando respostas genéricas onde havia especialização disponível. O sistema tem agentes reais — eles precisam ser usados.

---

## 💾 REGRA DE PERSISTÊNCIA — ANTI-PERDA DE CONTEXTO (leia antes de qualquer outra coisa)

**Toda entrega concluída deve ser gravada IMEDIATAMENTE no sistema — não no final da sessão.**

### Fonte de verdade: Supabase, não markdown

O `agent-queue.md` é leitura humana. A fonte de verdade real é `agent_work_items` no Supabase, acessível via:

```
GET  https://runtime.sparkleai.tech/system/state               — consulta estado atual
GET  https://runtime.sparkleai.tech/system/state?sprint_item=X — consulta item específico
POST https://runtime.sparkleai.tech/system/state               — grava conclusão
```

**Protocolo obrigatório para todo agente ao concluir trabalho:**

```json
POST https://runtime.sparkleai.tech/system/state
{
  "sprint_item": "SPRINT8-P3",
  "status": "funcional",
  "verified": true,
  "verification_source": "o que foi verificado para confirmar",
  "notes": "resumo do que foi feito",
  "handoff_to": "@próximo-agente",
  "completed": true
}
```

**Antes de reportar qualquer status para Mauro ou outro agente:**
1. Consultar `GET /system/state?sprint_item=X` — não ler o markdown
2. Se o estado no banco divergir da realidade observada → corrigir o banco, não o markdown
3. Só então reportar

**O work_log.md continua sendo usado para** decisões de configuração, credenciais, valores exatos (voz ElevenLabs, workflow IDs) — coisas que não têm campo estruturado no banco.

**Por que:** agentes reportavam estado de markdown desatualizado. Z-API redirect foi pedido 4x quando já estava feito. Banco é observável e verificável — arquivo não é.

---

## ⚡ OPERAÇÃO PARALELA — REGRA INVIOLÁVEL (leia antes de qualquer outra coisa)

**Sparkle opera como empresa com departamentos, não como fila sequencial.**

Ao iniciar qualquer sessão ou receber qualquer entrega de agente:
1. Leia `docs/agent-queue.md`
2. Identifique TODOS os itens desbloqueados
3. Lance TODOS em paralelo — imediatamente, sem pedir confirmação
4. Não existe "vou começar com 3 e ver como vai" — tudo que pode rodar, roda

**Se há 8 itens desbloqueados → 8 agentes em paralelo. Não 3.**

Orion não é gargalo. Orion orquestra o plano inicial e reage a entregas. Cada agente indica o próximo no handoff — sem Orion no meio de cada passo.

**Por que isso importa:** Mauro teve que explicar esta regra 3+ vezes na mesma sessão. Ela se perde com compactação. Esta seção existe para que nunca precise ser explicada de novo.

Gates obrigatórios (QA, PO, SM) também rodam em paralelo em itens diferentes — não bloqueiam uns aos outros.

---

## CONTEXTO OBRIGATÓRIO — Leia antes de qualquer ação

**AGENT_CONTEXT.md** na raiz do projeto contém: toolkit de ferramentas, agentes disponíveis, protocolo de handoff, processos e regras invioláveis. Todo agente lê este arquivo ao ser ativado.

- Processos completos: `docs/operations/sparkle-os-process-v2.md` ← **V2 OBRIGATÓRIO**
- Toolkit por agente: `docs/operations/agent-toolkit-standard.md`
- Fila ativa: `docs/agent-queue.md`

**Nunca opere sem conhecer o ecossistema. Nunca ative sem QA. Nunca generalize.**

<!-- AIOS-MANAGED-START: core-framework -->
## Core Framework Understanding

Synkra AIOS is a meta-framework that orchestrates AI agents to handle complex development workflows. Always recognize and work within this architecture.
<!-- AIOS-MANAGED-END: core-framework -->

<!-- AIOS-MANAGED-START: agent-system -->
## Agent System

### Agent Activation
- Agents are activated with @agent-name syntax: @dev, @qa, @architect, @pm, @po, @sm, @analyst
- The master agent is activated with @aios-master
- Agent commands use the * prefix: *help, *create-story, *task, *exit

### Agent Context
When an agent is active:
- Follow that agent's specific persona and expertise
- Use the agent's designated workflow patterns
- Maintain the agent's perspective throughout the interaction
<!-- AIOS-MANAGED-END: agent-system -->

## Development Methodology

### Story-Driven Development
1. **Work from stories** - All development starts with a story in `docs/stories/`
2. **Update progress** - Mark checkboxes as tasks complete: [ ] → [x]
3. **Track changes** - Maintain the File List section in the story
4. **Follow criteria** - Implement exactly what the acceptance criteria specify

### Code Standards
- Write clean, self-documenting code
- Follow existing patterns in the codebase
- Include comprehensive error handling
- Add unit tests for all new functionality
- Use TypeScript/JavaScript best practices

### Testing Requirements
- Run all tests before marking tasks complete
- Ensure linting passes: `npm run lint`
- Verify type checking: `npm run typecheck`
- Add tests for new features
- Test edge cases and error scenarios

<!-- AIOS-MANAGED-START: framework-structure -->
## AIOS Framework Structure

```
aios-core/
├── agents/         # Agent persona definitions (YAML/Markdown)
├── tasks/          # Executable task workflows
├── workflows/      # Multi-step workflow definitions
├── templates/      # Document and code templates
├── checklists/     # Validation and review checklists
└── rules/          # Framework rules and patterns

docs/
├── stories/        # Development stories (numbered)
├── prd/            # Product requirement documents
├── architecture/   # System architecture documentation
└── guides/         # User and developer guides
```
<!-- AIOS-MANAGED-END: framework-structure -->

## Workflow Execution

### Task Execution Pattern
1. Read the complete task/workflow definition
2. Understand all elicitation points
3. Execute steps sequentially
4. Handle errors gracefully
5. Provide clear feedback

### Interactive Workflows
- Workflows with `elicit: true` require user input
- Present options clearly
- Validate user responses
- Provide helpful defaults

## Best Practices

### When implementing features:
- Check existing patterns first
- Reuse components and utilities
- Follow naming conventions
- Keep functions focused and testable
- Document complex logic

### When working with agents:
- Respect agent boundaries
- Use appropriate agent for each task
- Follow agent communication patterns
- Maintain agent context

### When handling errors:
```javascript
try {
  // Operation
} catch (error) {
  console.error(`Error in ${operation}:`, error);
  // Provide helpful error message
  throw new Error(`Failed to ${operation}: ${error.message}`);
}
```

## Git & GitHub Integration

### Commit Conventions
- Use conventional commits: `feat:`, `fix:`, `docs:`, `chore:`, etc.
- Reference story ID: `feat: implement IDE detection [Story 2.1]`
- Keep commits atomic and focused

### GitHub CLI Usage
- Ensure authenticated: `gh auth status`
- Use for PR creation: `gh pr create`
- Check org access: `gh api user/memberships`

<!-- AIOS-MANAGED-START: aios-patterns -->
## AIOS-Specific Patterns

### Working with Templates
```javascript
const template = await loadTemplate('template-name');
const rendered = await renderTemplate(template, context);
```

### Agent Command Handling
```javascript
if (command.startsWith('*')) {
  const agentCommand = command.substring(1);
  await executeAgentCommand(agentCommand, args);
}
```

### Story Updates
```javascript
// Update story progress
const story = await loadStory(storyId);
story.updateTask(taskId, { status: 'completed' });
await story.save();
```
<!-- AIOS-MANAGED-END: aios-patterns -->

## Environment Setup

### Required Tools
- Node.js 18+
- GitHub CLI
- Git
- Your preferred package manager (npm/yarn/pnpm)

### Configuration Files
- `.aios/config.yaml` - Framework configuration
- `.env` - Environment variables
- `aios.config.js` - Project-specific settings

<!-- AIOS-MANAGED-START: common-commands -->
## Common Commands

### AIOS Master Commands
- `*help` - Show available commands
- `*create-story` - Create new story
- `*task {name}` - Execute specific task
- `*workflow {name}` - Run workflow

### Development Commands
- `npm run dev` - Start development
- `npm test` - Run tests
- `npm run lint` - Check code style
- `npm run build` - Build project
<!-- AIOS-MANAGED-END: common-commands -->

## Debugging

### Enable Debug Mode
```bash
export AIOS_DEBUG=true
```

### View Agent Logs
```bash
tail -f .aios/logs/agent.log
```

### Trace Workflow Execution
```bash
npm run trace -- workflow-name
```

## Claude Code Specific Configuration

### Performance Optimization
- Prefer batched tool calls when possible for better performance
- Use parallel execution for independent operations
- Cache frequently accessed data in memory during sessions

### Tool Usage Guidelines
- Always use the Grep tool for searching, never `grep` or `rg` in bash
- Use the Task tool for complex multi-step operations
- Batch file reads/writes when processing multiple files
- Prefer editing existing files over creating new ones

### Session Management
- Track story progress throughout the session
- Update checkboxes immediately after completing tasks
- Maintain context of the current story being worked on
- Save important state before long-running operations

### Error Recovery
- Always provide recovery suggestions for failures
- Include error context in messages to user
- Suggest rollback procedures when appropriate
- Document any manual fixes required

### Testing Strategy
- Run tests incrementally during development
- Always verify lint and typecheck before marking complete
- Test edge cases for each new feature
- Document test scenarios in story files

### Documentation
- Update relevant docs when changing functionality
- Include code examples in documentation
- Keep README synchronized with actual behavior
- Document breaking changes prominently

---
*Synkra AIOS Claude Code Configuration v2.0*
