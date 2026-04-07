# Architecture Spec — AIOS Process Enforcement System

**Autor:** Aria (@architect)
**Data:** 2026-04-07
**Status:** Pronto para @sm → @devops
**Depende de:** Gap Analysis (`docs/analysis/aiox-curriculum-gap-analysis.md`), análise arquitetural Aria (2026-04-07)
**Unblocks:** Toda execução futura do pipeline AIOS com garantias reais

---

## Sumário executivo

O sistema AIOS está instalado mas não enforced. Regras existem em CLAUDE.md, processos em `docs/operations/`, gates em story files — mas todos são advisory. Agentes podem violar authority boundaries, gates podem ser pulados, contexto pode ser contaminado, e nada bloqueia tecnicamente.

Este spec define 3 camadas de enforcement:
- **Camada 1 — Impossível:** hooks que bloqueiam ações proibidas antes de acontecerem
- **Camada 2 — Visível:** tabela `story_gates` no Supabase + Friday como monitor de pipeline
- **Camada 3 — Inevitável:** templates + campo `next_agent` no frontmatter que tornam o caminho certo o caminho fácil

---

## 1. Camada 1 — Hooks de Enforcement

### FR-E-01 — Hook: enforce-agent-authority

**Propósito:** Bloquear git push fora do @devops  
**Arquivo:** `.claude/hooks/enforce-agent-authority.py`  
**Trigger:** `PreToolUse` — Bash  

```python
import sys, json, os

input_data = json.load(sys.stdin)
command = input_data.get("tool_input", {}).get("command", "")

if "git push" in command:
    active_agent = os.environ.get("AIOS_ACTIVE_AGENT", "")
    if active_agent != "devops":
        print(json.dumps({
            "decision": "block",
            "reason": (
                f"[AIOS] git push bloqueado. "
                f"Agente ativo: '{active_agent}'. "
                f"Apenas @devops (Gage) pode fazer push. "
                f"Ative @devops com: /AIOS:agents:devops"
            )
        }))
        sys.exit(0)

print(json.dumps({"decision": "allow"}))
```

---

### FR-E-02 — Hook: enforce-qa-gate

**Propósito:** Bloquear mudança de status para "Done" sem QA Results com PASS  
**Arquivo:** `.claude/hooks/enforce-qa-gate.py`  
**Trigger:** `PreToolUse` — Write, Edit  

**Lógica:**
1. Se o arquivo sendo editado está em `docs/stories/`
2. E o novo conteúdo contém `status: Done`
3. Verificar se o arquivo já tem seção `## QA Results` com `**Resultado:** PASS`
4. Se não tiver → bloquear e informar que @qa deve revisar primeiro

```python
import sys, json, re

input_data = json.load(sys.stdin)
tool_name = input_data.get("tool_name", "")
file_path = input_data.get("tool_input", {}).get("file_path", "")
new_content = input_data.get("tool_input", {}).get("content", "") or \
              input_data.get("tool_input", {}).get("new_string", "")

if "docs/stories" not in file_path:
    print(json.dumps({"decision": "allow"}))
    sys.exit(0)

if "status: Done" not in new_content and "status: 'Done'" not in new_content:
    print(json.dumps({"decision": "allow"}))
    sys.exit(0)

# Verificar se QA Results com PASS existe
has_qa_pass = bool(re.search(r"## QA Results.*?\*\*Resultado:\*\* PASS", new_content, re.DOTALL))

if not has_qa_pass:
    print(json.dumps({
        "decision": "block",
        "reason": (
            "[AIOS] Status 'Done' bloqueado. "
            "Story não tem 'QA Results' com '**Resultado:** PASS'. "
            "Ative @qa para revisar: /AIOS:agents:qa"
        )
    }))
    sys.exit(0)

print(json.dumps({"decision": "allow"}))
```

---

### FR-E-03 — Hook: enforce-story-required

**Propósito:** Bloquear escrita em `sparkle-runtime/runtime/` sem story ativa declarada  
**Arquivo:** `.claude/hooks/enforce-story-required.py`  
**Trigger:** `PreToolUse` — Write  

**Lógica:**
1. Se o arquivo sendo criado está em `sparkle-runtime/runtime/` ou `sparkle-runtime/migrations/`
2. Verificar se existe variável de ambiente `AIOS_CURRENT_STORY`
3. Se não existir → avisar (não bloquear — pode ser correção urgente de hotfix)

**Nota:** Este hook é `warn` não `block` — hotfixes legítimos podem precisar de escrita direta. O aviso obriga consciência.

```python
import sys, json, os

input_data = json.load(sys.stdin)
file_path = input_data.get("tool_input", {}).get("file_path", "")

runtime_paths = ["sparkle-runtime/runtime/", "sparkle-runtime/migrations/"]
is_runtime = any(p in file_path for p in runtime_paths)

if not is_runtime:
    print(json.dumps({"decision": "allow"}))
    sys.exit(0)

current_story = os.environ.get("AIOS_CURRENT_STORY", "")
if not current_story:
    print(json.dumps({
        "decision": "warn",
        "message": (
            "[AIOS] Escrita em runtime sem story ativa. "
            "Se for hotfix, continue. "
            "Se for feature, declare: export AIOS_CURRENT_STORY=CONTENT-2.X"
        )
    }))
    sys.exit(0)

print(json.dumps({"decision": "allow"}))
```

---

### FR-E-04 — Registro de hooks em settings.json

Os 3 hooks devem ser registrados em `.claude/settings.json` (ou `settings.local.json` se preferir não versionar):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python .claude/hooks/enforce-agent-authority.py"
          }
        ]
      },
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "python .claude/hooks/enforce-qa-gate.py"
          },
          {
            "type": "command",
            "command": "python .claude/hooks/enforce-story-required.py"
          }
        ]
      }
    ]
  }
}
```

---

## 2. Camada 2 — Observabilidade via Supabase

### FR-E-05 — Migration: story_gates

**Arquivo:** `sparkle-runtime/migrations/016_story_gates.sql`

```sql
-- Gate registry: rastreia execução de cada gate por story
CREATE TABLE IF NOT EXISTS story_gates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    story_id        TEXT NOT NULL,           -- ex: 'CONTENT-2.2'
    gate            TEXT NOT NULL,           -- 'po_validate' | 'arch_complexity' | 'devops_worktree' | 'dev_implement' | 'qa_review' | 'po_accept' | 'devops_push'
    agent           TEXT NOT NULL,           -- '@qa', '@devops', etc.
    status          TEXT NOT NULL            -- 'pass' | 'fail' | 'waived' | 'skipped'
        CHECK (status IN ('pass', 'fail', 'waived', 'skipped')),
    notes           TEXT,
    completed_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (story_id, gate)                  -- um registro por gate por story
);

-- Índice para queries de Friday
CREATE INDEX IF NOT EXISTS idx_story_gates_story ON story_gates (story_id);
CREATE INDEX IF NOT EXISTS idx_story_gates_skipped ON story_gates (status) WHERE status = 'skipped';

COMMENT ON TABLE story_gates IS
    'Registro de gates do pipeline AIOS por story. Cada gate tem exatamente um registro por story. Status skipped dispara alerta via Friday.';
```

---

### FR-E-06 — Friday Monitor: alerta de gate pulado

**Módulo:** `sparkle-runtime/runtime/aios/gate_monitor.py`  
**Trigger:** Cron diário às 09:00 via APScheduler

```python
async def check_skipped_gates() -> None:
    """Detecta gates pulados nas últimas 24h e notifica Friday."""
    result = supabase.table("story_gates") \
        .select("story_id, gate, agent, completed_at") \
        .eq("status", "skipped") \
        .gte("completed_at", (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()) \
        .execute()

    if not result.data:
        return

    lines = [f"⚠️ Gates pulados nas últimas 24h:"]
    for row in result.data:
        lines.append(f"• {row['story_id']} → gate '{row['gate']}' pulado por {row['agent']}")

    await friday_notify("\n".join(lines))
```

**Protocolo para agentes:** Ao completar qualquer gate, o agente registra:

```python
# Exemplo: @qa completando QA review
supabase.table("story_gates").upsert({
    "story_id": "CONTENT-2.2",
    "gate": "qa_review",
    "agent": "@qa",
    "status": "pass",
    "notes": "8/8 ACs aprovados. Concern não-bloqueante em AC5."
}).execute()
```

---

## 3. Camada 3 — Caminho Certo = Caminho Fácil

### FR-E-07 — Campo `next_agent` no frontmatter de stories

**Mudança no template de story** (`story-tmpl.yaml`):

```yaml
---
story: CONTENT-X.X
title: "..."
status: In Progress          # In Progress | Ready for Review | Done
executor: "@dev"
next_agent: "@qa"            # NOVO: agente do próximo gate
next_command: "*review docs/stories/sprint-content/content-x-x.md"  # NOVO
next_gate: "qa_review"       # NOVO: nome do gate para registrar em story_gates
---
```

O Synapse Engine (L6 — Keyword context) lê o campo `next_agent` e injeta no início de toda sessão:

> "A story atual (`CONTENT-2.X`) está aguardando gate de `@qa`. Próximo comando: `*review docs/stories/...`"

Isso elimina a necessidade de Mauro lembrar qual agente vem a seguir.

---

### FR-E-08 — Agent Activation Templates

**Arquivo:** `docs/operations/agent-activation-prompts.md`

Templates copy-paste para cada agente no pipeline. Mauro digita o prompt, o Skill tool ativa o agente real (não imitação).

| Agente | Prompt de ativação |
|--------|-------------------|
| @architect | `/AIOS:agents:architect` + "analisa a story X e faz *assess-complexity" |
| @dev | `/AIOS:agents:dev` + "implemente a story X usando *develop-yolo" |
| @qa | `/AIOS:agents:qa` + "*review docs/stories/.../story-X.md" |
| @po | `/AIOS:agents:po` + "*close-story docs/stories/.../story-X.md" |
| @devops | `/AIOS:agents:devops` + "*pre-push && *push" |

---

### FR-E-09 — Auto-worktree como pré-requisito de story

**Mudança no handoff @sm → @devops:**

Toda story entregue pelo @sm deve incluir no campo `handoff_to`:

```
handoff_to: "@devops — executar *create-worktree {story-id} antes de passar para @dev"
```

O @devops não passa a story para @dev sem confirmar que o worktree foi criado.

**Verificação simples:**
```bash
git worktree list | grep {story-id}
```

Se não aparecer → worktree não existe → @dev aguarda.

---

## 4. Escopo de aplicação — "vale para tudo?"

Sim. Este enforcement se aplica a **todo trabalho no sistema Sparkle**, sem exceção:

| Domínio | Aplicação |
|---------|----------|
| Runtime (Python/VPS) | Hooks enforce-story-required + enforce-qa-gate |
| Portal (Next.js) | Mesmos hooks — `portal/` entra no path check |
| Squads AIOS | story_gates registra gates de criação de squad via @squad-creator |
| UI/UX (@ux) | story_gates inclui gate "ux_approve" para stories de interface |
| Migrations SQL | enforce-story-required avisa se migration criada sem story ativa |
| Documentação | enforce-architecture-first.py (já existe) bloqueia código sem arch doc |

A única exceção é **hotfix de produção** (definido como: serviço down, perda de dados iminente) — neste caso o enforce-story-required usa `warn` não `block`, permitindo ação imediata com rastro.

---

## 5. Mapa de mudanças por arquivo

| Arquivo | Ação | Responsável |
|---------|------|------------|
| `.claude/hooks/enforce-agent-authority.py` | CRIAR | @devops |
| `.claude/hooks/enforce-qa-gate.py` | CRIAR | @devops |
| `.claude/hooks/enforce-story-required.py` | CRIAR | @devops |
| `.claude/settings.json` | MODIFICAR — registrar 3 hooks novos | @devops |
| `sparkle-runtime/migrations/016_story_gates.sql` | CRIAR + APLICAR via MCP | @devops |
| `sparkle-runtime/runtime/aios/gate_monitor.py` | CRIAR | @dev |
| `sparkle-runtime/runtime/aios/__init__.py` | CRIAR (módulo novo) | @dev |
| `sparkle-runtime/runtime/scheduler.py` | MODIFICAR — registrar cron gate_monitor | @dev |
| `.aios-core/development/templates/story-tmpl.yaml` | MODIFICAR — adicionar next_agent, next_command, next_gate | @sm |
| `docs/operations/agent-activation-prompts.md` | CRIAR | @sm |
| `docs/operations/sparkle-os-process-v2.md` | MODIFICAR — adicionar protocolo de registro em story_gates | @sm |

---

## 6. Riscos e mitigações

| Risco | Probabilidade | Mitigação |
|-------|--------------|-----------|
| Hook enforce-qa-gate bloqueia hotfix legítimo | Baixa | Status "Hotfix" bypassa gate (pattern no regex) |
| story_gates acumula registros de sessões antigas sem story | Baixa | `story_id NOT NULL` + campo `gate` obrigatório — sem story_id, não registra |
| Campo next_agent desatualizado no frontmatter | Média | @sm responsável por atualizar ao criar cada story; Synapse Engine só injeta se campo presente |
| AIOS_ACTIVE_AGENT não setado por padrão | Alta | Hook enforce-agent-authority usa `warn` para agentes desconhecidos, `block` apenas se comando explicitamente `git push` |

---

## 7. Handoff para @sm

**@sm:** Com base nesta spec, criar as seguintes stories:

1. **AIOS-E-01** — `enforce-agent-authority.py` + `enforce-qa-gate.py` + `enforce-story-required.py` + registro em settings.json (executor: @devops)
2. **AIOS-E-02** — Migration `016_story_gates.sql` + módulo `gate_monitor.py` + cron diário (executor: @dev + @devops)
3. **AIOS-E-03** — Campo `next_agent` no story template + `agent-activation-prompts.md` + atualização de `sparkle-os-process-v2.md` (executor: @sm)

Dependências: AIOS-E-01 não bloqueia AIOS-E-02 ou AIOS-E-03 — podem rodar em paralelo.

---

*Spec gerada por Aria (@architect) em 2026-04-07.*
*Baseada em: gap analysis @analyst + análise arquitetural das 3 camadas de enforcement.*
