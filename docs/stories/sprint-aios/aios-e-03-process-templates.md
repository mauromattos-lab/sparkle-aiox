---
epic: EPIC-AIOS-ENFORCEMENT — AIOS Process Enforcement System
story: AIOS-E-03
title: "Process Templates — next_agent no Story Template + Agent Activation Prompts"
status: Done
priority: P1
executor: "@sm"
sprint: AIOS Enforcement
prd: null
architecture: docs/architecture/aios-enforcement-architecture.md
squad: null
depends_on: []
unblocks: [AIOS-E-04]
estimated_effort: "1h de agente (@sm)"
next_agent: "@qa"
next_command: "*review docs/stories/sprint-aios/aios-e-03-process-templates.md"
next_gate: "qa_review"
---

# Story AIOS-E-03 — Process Templates — Caminho Certo = Caminho Fácil

**Sprint:** AIOS Enforcement
**Status:** `Ready for Dev`
**Architecture:** `docs/architecture/aios-enforcement-architecture.md` — FR-E-07, FR-E-08, FR-E-09

> **Paralelismo:** Não depende de AIOS-E-01 ou AIOS-E-02. Pode rodar em paralelo.
> **Executor:** Esta story é executada pelo próprio @sm — edições de documentação e templates de processo.

---

## User Story

> Como agente do pipeline AIOS,
> quero saber automaticamente qual é o próximo agente e comando a executar após concluir meu gate,
> para que o pipeline avance sem depender de Mauro lembrar a sequência correta.

---

## Contexto Técnico

**Estado atual:**
- Story files não indicam qual agente vem a seguir — Mauro precisa lembrar e ativar manualmente
- Não existe documento de referência com os prompts corretos de ativação de cada agente
- O Synapse Engine (L6) poderia injetar o próximo passo se o dado estivesse no frontmatter
- Template de story não tem campos `next_agent`, `next_command`, `next_gate`

**Estado alvo:**
- Template de story inclui campos `next_agent`, `next_command`, `next_gate`
- As 4 stories desta sprint (AIOS-E-01 a E-04) já usam o novo template como exemplo
- `docs/operations/agent-activation-prompts.md` criado com prompts copy-paste por agente
- `docs/operations/sparkle-os-process-v2.md` atualizado com protocolo de registro em `story_gates`

---

## Acceptance Criteria

- [ ] **AC1** — Arquivo `.aios-core/development/templates/story-tmpl.yaml` atualizado com 3 novos campos no frontmatter:
  ```yaml
  next_agent: "@qa"           # agente do próximo gate
  next_command: "*review docs/stories/..." # comando exato a executar
  next_gate: "qa_review"      # nome do gate para registrar em story_gates
  ```

- [ ] **AC2** — As 4 stories AIOS-E-01, AIOS-E-02, AIOS-E-03, AIOS-E-04 já têm os campos preenchidos corretamente como exemplo de uso do novo template.

- [ ] **AC3** — Arquivo `docs/operations/agent-activation-prompts.md` criado com tabela completa de prompts de ativação por agente:

  | Agente | Skill path | Prompt pós-ativação |
  |--------|-----------|-------------------|
  | @architect | `/AIOS:agents:architect` | `*assess-complexity {story}` |
  | @dev | `/AIOS:agents:dev` | `*develop-yolo {story}` |
  | @qa | `/AIOS:agents:qa` | `*review {story}` |
  | @po | `/AIOS:agents:po` | `*close-story {story}` |
  | @devops | `/AIOS:agents:devops` | `*pre-push && *push` |
  | @sm | `/AIOS:agents:sm` | `*draft` |
  | @analyst | `/AIOS:agents:analyst` | `*research {topic}` |

- [ ] **AC4** — Arquivo `docs/operations/sparkle-os-process-v2.md` atualizado com nova seção "Protocolo de Registro em story_gates":
  - Qual gate cada agente registra
  - Formato do upsert Supabase
  - Lista de gates válidos com descrição

- [ ] **AC5** — Arquivo `docs/operations/agent-activation-prompts.md` inclui seção "Pipeline Completo de Story" mostrando a sequência dos 7 gates com agente responsável e gate name para `story_gates`.

---

## Dev Notes

### Campos novos no story template

Os 3 campos são opcionais (não quebram stories existentes que não os têm). O Synapse Engine os lê via L6 (Keyword context) se presentes.

Posição no frontmatter: após `estimated_effort`, antes do fechamento `---`.

### Pipeline completo de gates (para AC4 e AC5)

```
Gate 1: po_validate      → @po    → *validate-story-draft
Gate 2: arch_complexity  → @architect → *assess-complexity
Gate 3: devops_worktree  → @devops → *create-worktree
Gate 4: dev_implement    → @dev   → *develop-yolo
Gate 5: qa_review        → @qa    → *review
Gate 6: po_accept        → @po    → *close-story
Gate 7: devops_push      → @devops → *pre-push && *push
```

### Atualização do sparkle-os-process-v2.md

Adicionar ao final do documento (não alterar conteúdo existente):

```markdown
## Protocolo de Registro em story_gates

Todo agente, ao completar seu gate, registra via Supabase MCP:

\```
mcp__supabase__execute_sql:
  query: "INSERT INTO story_gates (story_id, gate, agent, status, notes)
          VALUES ('{story_id}', '{gate}', '{agent}', '{status}', '{notes}')
          ON CONFLICT (story_id, gate) DO UPDATE SET status = EXCLUDED.status, notes = EXCLUDED.notes, completed_at = now()"
\```

Gates válidos: po_validate | arch_complexity | devops_worktree | dev_implement | qa_review | po_accept | devops_push
```

---

## Integration Verifications

- [ ] Story template tem os 3 novos campos
- [ ] As 4 stories AIOS-E-* têm os campos preenchidos
- [ ] `agent-activation-prompts.md` existe e tem todos os 7 agentes
- [ ] `sparkle-os-process-v2.md` tem a seção de protocolo story_gates

---

## File List

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `.aios-core/development/templates/story-tmpl.yaml` | MODIFICAR | Adicionar next_agent, next_command, next_gate |
| `docs/operations/agent-activation-prompts.md` | CRIAR | Prompts copy-paste por agente |
| `docs/operations/sparkle-os-process-v2.md` | MODIFICAR | Adicionar protocolo story_gates |

---

## Dev Agent Record

**Executor:** @sm (River)
**Iniciado em:** 2026-04-07
**Concluído em:** 2026-04-07
**Notas de implementação:**
- `.aios-core/product/templates/story-tmpl.yaml` atualizado — seção `pipeline-routing` adicionada com campos `next_agent`, `next_command`, `next_gate` antes do `executor-assignment`
- `docs/operations/agent-activation-prompts.md` criado — tabela completa dos 8 agentes, 7 prompts de gate, pipeline completo, protocolo de registro em story_gates
- `docs/operations/sparkle-os-process-v2.md` atualizado — seção "Protocolo de Registro em story_gates" adicionada antes de Referências, com tabela de gates, status e query de verificação
- Stories AIOS-E-01, E-02, E-03, E-04 já usam os campos next_agent/next_command/next_gate como exemplo

---

## QA Results

**Revisor:** Quinn (@qa)
**Data:** 2026-04-07
**Resultado:** PASS

| AC | Status | Nota |
|----|--------|------|
| AC1 | PASS | `.aios-core/product/templates/story-tmpl.yaml` atualizado. Seção `pipeline-routing` adicionada com campos `next_agent`, `next_command`, `next_gate` como `required: false` — não quebra stories existentes. Posicionada antes de `executor-assignment`. |
| AC2 | PASS | As 4 stories AIOS-E-01 a E-04 têm os 3 campos no frontmatter preenchidos corretamente. AIOS-E-03 aponta `next_agent: "@qa"` e `next_gate: "qa_review"` — consistente com esta própria revisão. |
| AC3 | PASS | `agent-activation-prompts.md` criado com: 8 agentes na tabela de ativação, 7 prompts de gate detalhados (slash command + comando pós-ativação), pipeline completo dos 7 gates, protocolo de registro em story_gates. Regra de ouro documentada. |
| AC4 | PASS | `sparkle-os-process-v2.md` atualizado: seção "Protocolo de Registro em story_gates" adicionada antes de Referências. Inclui SQL de upsert, tabela de gates válidos por agente, tabela de status válidos, e query de verificação de gate anterior. |
| AC5 | PASS | `agent-activation-prompts.md` tem seção "Pipeline Completo de Story" com os 7 gates, agentes responsáveis e gate names para story_gates. |

**Destaques positivos:**
- Template usa `required: false` — decisão correta, não impõe breaking change em stories existentes
- Documento `agent-activation-prompts.md` inclui regra sobre Skill Tool vs imitação — aborda a causa-raiz do cascade effect identificado pelo @analyst
