# Agent Activation Prompts — Sparkle AIOX

**Versão:** 1.0 | **Data:** 2026-04-07
**Mantido por:** @sm (River)

> Este documento contém os prompts exatos para ativar cada agente AIOS corretamente via Skill tool.
> Copiar e colar no início da sessão. Nunca pedir ao Claude que "imite" um agente — sempre ativar o skill real.

---

## Regra de Ouro

```
/AIOS:agents:{nome-do-agente}
```

Digitar o slash command ativa o Skill tool com o YAML completo do agente — persona, comandos, workflows, checklists. Isso é diferente de pedir "aja como @qa" sem o skill ativo.

---

## Tabela de Ativação por Agente

| Agente | Slash Command | Quando usar |
|--------|--------------|-------------|
| @architect (Aria) | `/AIOS:agents:architect` | Decisões de arquitetura, spec técnica, avaliação de complexidade |
| @dev (Dex) | `/AIOS:agents:dev` | Implementação de código, debug, refatoração |
| @qa (Quinn) | `/AIOS:agents:qa` | Revisão de story, quality gate, validação de ACs |
| @po (Pax) | `/AIOS:agents:po` | Aceite de story, cruzamento FR vs entrega, backlog |
| @devops (Gage) | `/AIOS:agents:devops` | Deploy, infra, git push, PR, CI/CD, hooks |
| @sm (River) | `/AIOS:agents:sm` | Criação de stories, refinamento, processo ágil |
| @analyst (Atlas) | `/AIOS:agents:analyst` | Pesquisa, análise, benchmark, brownfield discovery |
| @pm (Morgan) | `/AIOS:agents:pm` | PRD, estratégia de produto, definição de escopo |

---

## Prompts Completos por Gate do Pipeline

### Gate 1 — @po valida story draft

```
/AIOS:agents:po

*validate-story-draft docs/stories/{sprint}/{story-file}.md
```

---

### Gate 2 — @architect avalia complexidade

```
/AIOS:agents:architect

*assess-complexity docs/stories/{sprint}/{story-file}.md
```

---

### Gate 3 — @devops cria worktree

```
/AIOS:agents:devops

*create-worktree {STORY-ID}
```

---

### Gate 4 — @dev implementa

```
/AIOS:agents:dev

Implemente a story: docs/stories/{sprint}/{story-file}.md
Use *develop-yolo para stories com 5+ ACs.
Use *develop para stories simples.
```

---

### Gate 5 — @qa revisa

```
/AIOS:agents:qa

*review docs/stories/{sprint}/{story-file}.md
```

---

### Gate 6 — @po aceite formal

```
/AIOS:agents:po

*close-story docs/stories/{sprint}/{story-file}.md
```

---

### Gate 7 — @devops push + PR

```
/AIOS:agents:devops

*pre-push
*push
*create-pr
```

---

## Pipeline Completo de Story (sequência dos 7 gates)

```
Gate 1: po_validate      → @po       → *validate-story-draft {story}
Gate 2: arch_complexity  → @architect → *assess-complexity {story}
Gate 3: devops_worktree  → @devops   → *create-worktree {STORY-ID}
Gate 4: dev_implement    → @dev      → *develop-yolo {story}
Gate 5: qa_review        → @qa       → *review {story}
Gate 6: po_accept        → @po       → *close-story {story}
Gate 7: devops_push      → @devops   → *pre-push && *push && *create-pr
```

**Gates paralelos possíveis:** Gate 1 + Gate 2 podem rodar simultaneamente (ambos são de planejamento, sem dependência entre si).

**Gates obrigatoriamente sequenciais:** Gate 3 deve preceder Gate 4. Gate 5 deve preceder Gate 6. Gate 6 deve preceder Gate 7.

---

## Registro de Gate em story_gates (obrigatório ao completar cada gate)

Após completar qualquer gate, o agente registra via MCP Supabase:

```sql
INSERT INTO story_gates (story_id, gate, agent, status, notes)
VALUES ('{STORY-ID}', '{gate}', '{@agente}', 'pass', '{observações}')
ON CONFLICT (story_id, gate)
DO UPDATE SET status = EXCLUDED.status, notes = EXCLUDED.notes, completed_at = now();
```

**Gates válidos:** `po_validate` | `arch_complexity` | `devops_worktree` | `dev_implement` | `qa_review` | `po_accept` | `devops_push`

**Status válidos:** `pass` | `fail` | `waived` | `skipped`

---

## Uso em Sessões Longas (multi-agente)

Quando uma sessão cobre múltiplos gates:

1. Ativar o agente via slash command
2. Executar o gate
3. Registrar em `story_gates`
4. Atualizar `next_agent` + `next_command` no frontmatter da story
5. Ativar próximo agente via slash command

Nunca acumular múltiplos agentes no mesmo contexto sem ativação explícita de cada um.

---

*Mantido por @sm (River) — atualizar sempre que um novo agente for adicionado ao ecossistema Sparkle.*
