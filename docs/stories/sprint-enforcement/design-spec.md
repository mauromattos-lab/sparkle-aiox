# Process Enforcement v1 — Design Spec Técnico

**Versão:** 1.0 | **Data:** 2026-04-05 | **Autor:** @architect (Aria)
**PRD:** `docs/prd/process-enforcement-prd.md`
**Gate:** spec_approved → handoff para @sm

---

## 1. Visão Geral da Arquitetura

### Componentes afetados

```
sparkle-runtime/runtime/
├── workflows/
│   ├── pipeline_enforcement.py   ← Story 1.1: novos PIPELINE_STEPS + migration
│   └── templates.py              ← Story 1.1: template aios_pipeline atualizado
├── pipeline/
│   └── router.py                 ← Story 1.2: gate verification + Story 1.3: validate-handoff endpoint
└── (novo) pipeline/
    └── handoff_validator.py      ← Story 1.3: lógica de validação isolada
```

**Não afetados:**
- `system_router.py` — `/system/state` não muda
- `agent_work_items` table — schema não muda
- `workflow_runs` table — schema não muda (migration só em código)
- Friday proactive — apenas novos `trigger_type` adicionados

---

## 2. Story 1.1 — Estender Pipeline para 7 Gates

### 2.1 Novos PIPELINE_STEPS

```python
# pipeline_enforcement.py — substituir PIPELINE_STEPS atual

PIPELINE_STEPS: list[dict] = [
    {"step": 0, "name": "prd_approved",    "agent": "@pm"},
    {"step": 1, "name": "spec_approved",   "agent": "@architect"},
    {"step": 2, "name": "stories_ready",   "agent": "@sm"},
    {"step": 3, "name": "dev_complete",    "agent": "@dev"},
    {"step": 4, "name": "qa_approved",     "agent": "@qa"},
    {"step": 5, "name": "po_accepted",     "agent": "@po"},
    {"step": 6, "name": "devops_deployed", "agent": "@devops"},
    {"step": 7, "name": "done",            "agent": "system"},
]

SCHEMA_VERSION = 2  # novo campo para detectar items antigos
```

### 2.2 Migration Strategy — Compatibilidade com workflow_runs existentes

**Princípio:** Zero SQL migration. Mapeamento em código, detectado por `schema_version` no context JSONB.

```python
# Mapeamento de steps antigos (v1) para novos (v2)
LEGACY_STEP_MAP: dict[int, int] = {
    0: 2,  # story_created     → stories_ready
    1: 3,  # dev_implementing  → dev_complete
    2: 4,  # qa_validating     → qa_approved
    3: 6,  # devops_deploying  → devops_deployed
    4: 7,  # done              → done
}

def is_legacy_run(run: dict) -> bool:
    """Detecta se workflow_run foi criado com schema v1."""
    context = run.get("context") or {}
    return context.get("schema_version", 1) < SCHEMA_VERSION

def normalize_step(run: dict) -> int:
    """Retorna o step normalizado para v2, independente do schema."""
    current = run.get("current_step", 0)
    if is_legacy_run(run):
        return LEGACY_STEP_MAP.get(current, current)
    return current
```

**Onde aplicar:** Em `_get_pipeline_run()` e `check_gates()`, chamar `normalize_step(run)` em vez de `run.get("current_step")` diretamente.

**Novos runs:** Ao criar um `workflow_run` via `/pipeline/advance` com step 0, inserir `schema_version: 2` no context.

### 2.3 Atualizar template aios_pipeline em templates.py

Adicionar os 5 novos steps (prd_approved, spec_approved, stories_ready, po_accepted, devops_deployed) ao template, mantendo os 4 existentes com nomes atualizados.

### 2.4 Riscos Story 1.1

| Risco | Probabilidade | Mitigação |
|-------|--------------|-----------|
| workflow_run existente com step 2 (qa_validating) mapeado para step 4 (qa_approved) — agente tenta avançar para step 3 (devops, antigo) mas agora é step 5 (po_accepted) | Médio | `is_legacy_run()` detecta e aplica mapa. Testes de regressão com runs antigos. |
| step name em string ("qa_validating") deixa de existir | Baixo | `NAME_TO_STEP` mantém aliases — adicionar `"qa_validating": 4` como alias legado |

---

## 3. Story 1.2 — Gate Verification obrigatório

### 3.1 Nova função em pipeline_enforcement.py

```python
async def verify_state_persisted(
    sprint_item: str | None,
    step_name: str,
    schema_version: int = 1,
) -> dict:
    """
    Verifica se agent_work_items tem registro verified=True para o sprint_item.
    Retorna dict com 'allowed' (bool) e 'reason' (str).
    
    Para runs legados (schema_version < 2): skip verification (opt-in).
    """
    # Items legados não têm sprint_item no context — skip gracefully
    if not sprint_item or schema_version < SCHEMA_VERSION:
        return {"allowed": True, "reason": "legacy_run_skipped", "skipped": True}

    try:
        result = await asyncio.to_thread(
            lambda: supabase.table("agent_work_items")
            .select("sprint_item,status,verified,handoff_to,updated_at")
            .eq("sprint_item", sprint_item)
            .single()
            .execute()
        )
    except Exception:
        result = None

    if not result or not result.data:
        return {
            "allowed": False,
            "reason": f"Estado não persistido. Execute POST /system/state com sprint_item='{sprint_item}' antes de avançar.",
            "error_code": "state_missing",
        }

    record = result.data
    if not record.get("verified", False):
        return {
            "allowed": False,
            "reason": f"verified=false em agent_work_items. Confirme a entrega antes de avançar.",
            "error_code": "state_unverified",
        }

    return {
        "allowed": True,
        "reason": "State verified",
        "record": record,
    }
```

### 3.2 Integração em router.py — POST /pipeline/advance

**Ponto de inserção:** Após `check_gates()`, antes de `record_transition()`.

```python
# Em pipeline_advance(), após gate_result = await check_gates(...)

# [NOVO] Verificar state persistence
sprint_item = (run.get("context") or {}).get("sprint_item")
schema_ver = (run.get("context") or {}).get("schema_version", 1)
state_result = await verify_state_persisted(sprint_item, current_step_name, schema_ver)

if not state_result["allowed"]:
    # Notificar Friday com tipo específico
    await notify_violation(
        item_id=item_id,
        current_step=current_step,
        attempted_step=target_index,
        agent=req.agent,
        violation_type="state_missing",  # novo param
    )
    raise HTTPException(
        status_code=422,
        detail={
            "error": state_result["error_code"],
            "message": state_result["reason"],
            "sprint_item": sprint_item,
            "action_required": f"POST /system/state com sprint_item='{sprint_item}' e verified=true",
        },
    )
```

### 3.3 Atualizar notify_violation — novo parâmetro violation_type

```python
async def notify_violation(
    item_id: str,
    current_step: int,
    attempted_step: int | str,
    agent: str,
    violation_type: str = "gate_skip",  # gate_skip | state_missing | handoff_invalid
) -> None:
```

Mensagem Friday diferenciada por tipo:
- `gate_skip`: "Pipeline violation bloqueada! Step pulado."
- `state_missing`: "Gate bloqueado! Estado não persistido no Supabase antes do avanço."
- `handoff_invalid`: "Gate bloqueado! Handoff com campos obrigatórios ausentes."

### 3.4 Deduplicação de notificações (NFR3)

```python
# Cache em memória por (item_id, violation_type) com TTL 5 min
_violation_cache: dict[str, float] = {}

def _should_notify(item_id: str, violation_type: str) -> bool:
    key = f"{item_id}:{violation_type}"
    now = time.time()
    if key in _violation_cache and now - _violation_cache[key] < 300:
        return False
    _violation_cache[key] = now
    return True
```

### 3.5 Riscos Story 1.2

| Risco | Probabilidade | Mitigação |
|-------|--------------|-----------|
| Items legados sem `sprint_item` no context quebram | Alta | `verify_state_persisted()` retorna `allowed=True` com `skipped=True` para schema_version < 2 |
| Latência adicional da query Supabase | Baixo | Query por PK (`sprint_item` indexado) — ~20-50ms. Dentro do NFR2 (200ms) |
| `agent_work_items` pode não ter o item ainda (sprint novo) | Médio | Mensagem de erro clara com action_required |

---

## 4. Story 1.3 — Handoff Schema Validation

### 4.1 Novo arquivo: pipeline/handoff_validator.py

```python
"""
Handoff Schema Validator — Story 1.3.

Valida o bloco de handoff obrigatório do sparkle-os-process-v2.
Armazena handoffs válidos em runtime_tasks para auditoria.
Garante one-time use via campo consumed.
"""
import uuid
import asyncio
from datetime import datetime, timezone
from pydantic import BaseModel
from typing import Optional

from runtime.db import supabase

# ── Schema de entrada ──────────────────────────────────────────────

class HandoffPayload(BaseModel):
    gate_concluido: str           # "Gate 4 — QA aprovado"
    status: str                   # "AGUARDANDO_PO"
    proximo: str                  # "@po"
    sprint_item: str              # "PROC-ENF-V1"
    entrega: list[str]            # mínimo 1 item
    supabase_atualizado: bool     # deve ser True
    prompt_para_proximo: str      # mínimo 100 chars

# ── Validação ──────────────────────────────────────────────────────

REQUIRED_FIELDS = [
    "gate_concluido", "status", "proximo",
    "sprint_item", "entrega", "supabase_atualizado", "prompt_para_proximo",
]

def validate_handoff(payload: HandoffPayload) -> tuple[bool, list[str]]:
    """Valida campos e regras de negócio. Retorna (valid, errors)."""
    errors = []

    if not payload.entrega:
        errors.append("entrega: deve ter pelo menos 1 item")
    if not payload.supabase_atualizado:
        errors.append("supabase_atualizado: deve ser true — execute POST /system/state antes")
    if len(payload.prompt_para_proximo) < 100:
        errors.append(f"prompt_para_proximo: muito curto ({len(payload.prompt_para_proximo)} chars, mínimo 100)")
    if not payload.proximo.startswith("@"):
        errors.append("proximo: deve referenciar um agente com @ (ex: '@po')")

    return len(errors) == 0, errors

async def store_handoff(payload: HandoffPayload) -> str:
    """Armazena handoff válido em runtime_tasks. Retorna handoff_validation_id."""
    validation_id = str(uuid.uuid4())
    
    await asyncio.to_thread(
        lambda: supabase.table("runtime_tasks").insert({
            "agent_id": "system",
            "task_type": "handoff_validation",
            "payload": {
                "handoff_validation_id": validation_id,
                "gate_concluido": payload.gate_concluido,
                "sprint_item": payload.sprint_item,
                "proximo": payload.proximo,
                "status": payload.status,
                "entrega": payload.entrega,
                "prompt_para_proximo": payload.prompt_para_proximo[:200],  # truncar para log
                "consumed": False,
            },
            "status": "done",
            "priority": 5,
        }).execute()
    )
    return validation_id

async def consume_handoff(handoff_validation_id: str) -> dict:
    """
    Marca handoff como consumido (one-time use).
    Retorna {'allowed': bool, 'reason': str}.
    """
    result = await asyncio.to_thread(
        lambda: supabase.table("runtime_tasks")
        .select("id,payload,status")
        .eq("task_type", "handoff_validation")
        .execute()
    )
    
    records = result.data or []
    match = next(
        (r for r in records
         if r.get("payload", {}).get("handoff_validation_id") == handoff_validation_id),
        None
    )
    
    if not match:
        return {"allowed": False, "reason": "handoff_validation_id não encontrado"}
    
    if match.get("payload", {}).get("consumed", False):
        return {"allowed": False, "reason": "handoff_validation_id já foi utilizado"}
    
    # Marcar como consumido
    payload = match["payload"]
    payload["consumed"] = True
    await asyncio.to_thread(
        lambda: supabase.table("runtime_tasks")
        .update({"payload": payload})
        .eq("id", match["id"])
        .execute()
    )
    
    return {"allowed": True, "reason": "Handoff válido e consumido"}
```

### 4.2 Novo endpoint: POST /pipeline/validate-handoff

```python
# Em pipeline/router.py — adicionar endpoint

from runtime.pipeline.handoff_validator import (
    HandoffPayload, validate_handoff, store_handoff, REQUIRED_FIELDS
)

@router.post("/validate-handoff")
async def pipeline_validate_handoff(payload: HandoffPayload):
    """
    Valida o bloco de handoff obrigatório do processo v2.
    Retorna handoff_validation_id se válido — usar no /pipeline/advance.
    """
    valid, errors = validate_handoff(payload)
    
    if not valid:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "handoff_invalid",
                "valid": False,
                "errors": errors,
                "missing_or_invalid_fields": [
                    e.split(":")[0] for e in errors
                ],
                "required_fields": REQUIRED_FIELDS,
            }
        )
    
    validation_id = await store_handoff(payload)
    
    return {
        "valid": True,
        "handoff_validation_id": validation_id,
        "sprint_item": payload.sprint_item,
        "proximo": payload.proximo,
        "message": f"Handoff válido. Use handoff_validation_id no POST /pipeline/advance.",
    }
```

### 4.3 Atualizar AdvanceRequest — campo opcional com enforcement por schema_version

```python
class AdvanceRequest(BaseModel):
    target_step: str | int
    agent: str
    handoff_validation_id: Optional[str] = None  # obrigatório para schema_version >= 2

# Em pipeline_advance(), após verify_state_persisted():
if schema_ver >= SCHEMA_VERSION and not req.handoff_validation_id:
    raise HTTPException(
        status_code=422,
        detail={
            "error": "handoff_required",
            "message": "handoff_validation_id obrigatório. Execute POST /pipeline/validate-handoff primeiro.",
            "action_required": "POST /pipeline/validate-handoff",
        }
    )

if req.handoff_validation_id:
    consume_result = await consume_handoff(req.handoff_validation_id)
    if not consume_result["allowed"]:
        raise HTTPException(
            status_code=422,
            detail={"error": "handoff_consumed", "message": consume_result["reason"]}
        )
```

### 4.4 Riscos Story 1.3

| Risco | Probabilidade | Mitigação |
|-------|--------------|-----------|
| Query de consume_handoff itera todos os `handoff_validation` — lento com volume | Médio | Adicionar index em `runtime_tasks(task_type, created_at)` — migration simples |
| `handoff_validation_id` expirado/perdido bloqueia agente | Médio | Adicionar `GET /pipeline/validate-handoff/{id}` para revalidar sem consumir |
| Items legados sem `handoff_validation_id` quebram | Alto | Verificação só obrigatória para `schema_version >= 2` — legados passam |

---

## 5. Contratos de API Completos

### POST /pipeline/advance (atualizado)

**Request:**
```json
{
  "target_step": "dev_complete",
  "agent": "@dev",
  "handoff_validation_id": "uuid-v4"  // obrigatório para items novos
}
```

**Responses:**
```json
// 200 OK
{ "item_id": "PROC-ENF-V1", "current_step": 3, "step_name": "dev_complete", "status": "running" }

// 422 — gate skip
{ "error": "pipeline_violation", "message": "Step dev_complete requer spec_approved concluido", "current_step": "prd_approved" }

// 422 — state missing
{ "error": "state_missing", "message": "Estado não persistido. Execute POST /system/state...", "action_required": "..." }

// 422 — handoff required
{ "error": "handoff_required", "message": "handoff_validation_id obrigatório. Execute POST /pipeline/validate-handoff primeiro." }

// 422 — handoff consumed
{ "error": "handoff_consumed", "message": "handoff_validation_id já foi utilizado" }
```

### POST /pipeline/validate-handoff (novo)

**Request:**
```json
{
  "gate_concluido": "Gate 3 — Dev completo",
  "status": "AGUARDANDO_QA",
  "proximo": "@qa",
  "sprint_item": "PROC-ENF-V1",
  "entrega": ["runtime/pipeline/pipeline_enforcement.py", "runtime/pipeline/router.py"],
  "supabase_atualizado": true,
  "prompt_para_proximo": "Você é @qa. O que foi feito: Story 1.1 implementada. PIPELINE_STEPS estendido para 7 gates. Migration de compatibilidade com runs legados via normalize_step()..."
}
```

**Responses:**
```json
// 200 OK
{ "valid": true, "handoff_validation_id": "550e8400-e29b-41d4-a716-446655440000", "sprint_item": "PROC-ENF-V1", "proximo": "@qa" }

// 422 — inválido
{ "error": "handoff_invalid", "valid": false, "errors": ["supabase_atualizado: deve ser true", "prompt_para_proximo: muito curto (45 chars, mínimo 100)"], "missing_or_invalid_fields": ["supabase_atualizado", "prompt_para_proximo"] }
```

### GET /pipeline/status/{item_id} (sem mudanças de contrato, resposta estendida)

```json
{
  "item_id": "PROC-ENF-V1",
  "current_step": 3,
  "step_name": "dev_complete",
  "schema_version": 2,
  "steps": [
    { "step": 0, "name": "prd_approved",    "completed": true },
    { "step": 1, "name": "spec_approved",   "completed": true },
    { "step": 2, "name": "stories_ready",   "completed": true },
    { "step": 3, "name": "dev_complete",    "completed": true },
    { "step": 4, "name": "qa_approved",     "completed": false },
    { "step": 5, "name": "po_accepted",     "completed": false },
    { "step": 6, "name": "devops_deployed", "completed": false },
    { "step": 7, "name": "done",            "completed": false }
  ],
  "last_handoff_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## 6. Sequência de Implementação por Story

```
Story 1.1:
  1. Atualizar PIPELINE_STEPS + LEGACY_STEP_MAP + SCHEMA_VERSION
  2. Adicionar is_legacy_run() + normalize_step()
  3. Atualizar _get_pipeline_run() para usar normalize_step()
  4. Atualizar check_gates() para usar normalize_step()
  5. Atualizar templates.py com novos steps
  → Deploy + smoke test IV1, IV2, IV3

Story 1.2:
  1. Adicionar verify_state_persisted() em pipeline_enforcement.py
  2. Atualizar notify_violation() com violation_type param
  3. Adicionar _should_notify() para deduplicação
  4. Inserir verify_state_persisted() em router.py /pipeline/advance
  → Deploy + smoke test IV1, IV2, IV3, IV4

Story 1.3:
  1. Criar pipeline/handoff_validator.py completo
  2. Adicionar POST /pipeline/validate-handoff em router.py
  3. Atualizar AdvanceRequest com handoff_validation_id
  4. Inserir consume_handoff() em /pipeline/advance
  → Deploy + smoke test IV1, IV2, IV3, IV4
```

---

## 7. Handoff para @sm

```
---
GATE_CONCLUÍDO: Gate 2 — Spec técnico aprovado
STATUS: AGUARDANDO_SM
PRÓXIMO: @sm
SPRINT_ITEM: PROC-ENF-V1

ENTREGA:
  - Design spec: docs/stories/sprint-enforcement/design-spec.md
  - PRD: docs/prd/process-enforcement-prd.md
  - Código base C2-B2: sparkle-runtime/runtime/workflows/pipeline_enforcement.py
  - Pipeline router: sparkle-runtime/runtime/pipeline/router.py

SUPABASE_ATUALIZADO: não aplicável (gate de planejamento — sem código implementado)

PROMPT_PARA_PRÓXIMO: |
  Você é @sm (River). Contexto direto.

  O QUE FOI FEITO:
  Design spec técnico criado para Process Enforcement v1 (3 stories).
  Toda a lógica de implementação está em docs/stories/sprint-enforcement/design-spec.md.
  O @dev deve seguir o design spec — não inventar arquitetura.

  SUA TAREFA:
  Criar os 3 arquivos de story detalhados em docs/stories/sprint-enforcement/:
  - story-1.1-extend-pipeline.md
  - story-1.2-gate-verification.md
  - story-1.3-handoff-validation.md

  Cada story deve ter: título, user story, acceptance criteria numerados (do PRD),
  integration verifications (IV1-IV4), referência ao design spec, e o bloco de
  handoff para @dev com PROMPT_PARA_PRÓXIMO completo.

  CRITÉRIOS DE SAÍDA DO SEU GATE:
  - [ ] 3 arquivos de story criados em docs/stories/sprint-enforcement/
  - [ ] Cada story referencia seção específica do design spec
  - [ ] Sequência de implementação documentada (1.1 → 1.2 → 1.3)
  - [ ] Handoff para @dev incluído em cada story

  SE aprovado: STATUS = stories_ready, PRÓXIMO = @dev (Story 1.1 primeiro)
  SE dúvida técnica: consultar design-spec.md antes de perguntar para @architect
---
```

---

*Process Enforcement v1 — Design Spec aprovado.*
*— Aria, arquitetando o futuro 🏗️*
