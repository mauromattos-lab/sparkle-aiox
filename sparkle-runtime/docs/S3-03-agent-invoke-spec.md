# S3-03 — Template de Agente Especialista (Supabase)
_Spec entregue por @architect (Aria) para @dev implementar._
_Data: 2026-04-01_

---

## Objetivo

Permitir que novos agentes sejam criados via inserção de linha no Supabase — sem alterar código.
Um agente é um registro na tabela `agents` com `system_prompt`, `model` e `tools` configurados.
O endpoint `POST /agent/invoke` consulta esse registro e chama Claude com os parâmetros do banco.

---

## Parte 1 — SQL: ALTER TABLE `agents`

Execute no SQL Editor do Supabase (projeto `gqhdspayjtiijcqklbys`).

```sql
-- S3-03: Expandir tabela agents para suportar template de agente especialista
-- Existente: agent_id (text PK), status (text), last_heartbeat (timestamptz)
-- Adicionar campos de configuração de agente

ALTER TABLE agents
  ADD COLUMN IF NOT EXISTS name            text,
  ADD COLUMN IF NOT EXISTS system_prompt   text,
  ADD COLUMN IF NOT EXISTS model           text        NOT NULL DEFAULT 'claude-haiku-4-5-20251001',
  ADD COLUMN IF NOT EXISTS max_tokens      integer     NOT NULL DEFAULT 1024,
  ADD COLUMN IF NOT EXISTS client_id       text,
  ADD COLUMN IF NOT EXISTS tools           jsonb       NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS active          boolean     NOT NULL DEFAULT true,
  ADD COLUMN IF NOT EXISTS created_at      timestamptz NOT NULL DEFAULT now();

-- Índice para lookup rápido por client_id (agentes por cliente)
CREATE INDEX IF NOT EXISTS idx_agents_client_id ON agents (client_id);

-- Índice para filtrar ativos (query mais comum no invoke)
CREATE INDEX IF NOT EXISTS idx_agents_active ON agents (active) WHERE active = true;

-- Comentários para documentar intenção das colunas
COMMENT ON COLUMN agents.name          IS 'Nome legível do agente (ex: "Zenya - Ensinaja")';
COMMENT ON COLUMN agents.system_prompt IS 'Prompt de sistema completo enviado ao Claude a cada invocação';
COMMENT ON COLUMN agents.model         IS 'ID do modelo Claude (ex: claude-haiku-4-5-20251001, claude-sonnet-4-6)';
COMMENT ON COLUMN agents.max_tokens    IS 'Limite de tokens de saída. Padrão 1024.';
COMMENT ON COLUMN agents.client_id     IS 'Referência ao cliente dono deste agente (FK lógica para clients.id)';
COMMENT ON COLUMN agents.tools         IS 'Lista de ferramentas disponíveis ao agente. Array JSON de strings. Ex: ["loja_integrada_query", "brain_query"]';
COMMENT ON COLUMN agents.active        IS 'false = agente desativado, não pode ser invocado via /agent/invoke';
COMMENT ON COLUMN agents.created_at    IS 'Timestamp de criação do registro';
```

### Decisões de schema

| Decisão | Justificativa |
|---------|---------------|
| `model` com DEFAULT `claude-haiku-4-5-20251001` | Modelo mais barato como padrão seguro. Agentes de cliente (Zenya) são volume alto — custo importa. |
| `tools` como `jsonb` array de strings | Flexível e indexável. O handler resolve o nome da tool para a função Python correspondente via registry. Evita acoplamento. |
| `client_id` nullable | Agentes internos (Friday, Orion) não pertencem a cliente específico. |
| `active` boolean | Desativar agente sem deletar registro preserva histórico no `llm_cost_log`. |
| `system_prompt` nullable | Permite registros de agentes internos que definem o prompt no código (ex: Friday). Não é obrigado para agentes já existentes. |
| Sem FK hard para `clients` | `clients.id` é UUID; `agents.client_id` é text para compatibilidade com IDs legados como `"sparkle-internal"`. FK lógica, sem constraint. |

---

## Parte 2 — Spec do Endpoint `POST /agent/invoke`

### Arquivo: `runtime/agents/router.py` (novo)

O endpoint vive em um router próprio — não em `/friday`. Razão: friday é a interface pessoal do Mauro via WhatsApp. `/agent/invoke` é a interface programática para invocação de agentes por outros sistemas (n8n, portal, outros agentes).

### Request

```
POST /agent/invoke
Content-Type: application/json
```

```json
{
  "agent_id": "zenya-ensinaja",
  "message": "Qual o horário de funcionamento da escola?",
  "context": {
    "from_number": "5512999999999",
    "client_id": "ensinaja-uuid"
  }
}
```

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `agent_id` | string | sim | PK da tabela `agents` |
| `message` | string | sim | Mensagem do usuário |
| `context` | object | não | Dados extras passados como contexto (from_number, client_id, etc.) |

### Response — sucesso (200)

```json
{
  "response": "Nosso horário é segunda a sexta das 7h às 18h e sábado das 8h às 12h.",
  "agent_id": "zenya-ensinaja",
  "model": "claude-haiku-4-5-20251001"
}
```

### Response — erro (404)

```json
{
  "detail": "Agent 'zenya-ensinaja' not found or inactive."
}
```

### Response — erro (422) — payload inválido

FastAPI valida automaticamente via Pydantic.

### Response — erro (500)

```json
{
  "detail": "Agent invocation failed: <mensagem de erro>"
}
```

---

## Parte 3 — Spec de Implementação para @dev

### 3.1 — Estrutura de arquivos

```
sparkle-runtime/
  runtime/
    agents/
      __init__.py          ← vazio
      router.py            ← APIRouter com POST /invoke
      handler.py           ← lógica de invocação (fetch + Claude)
  main.py                  ← include_router novo router
```

Não criar pasta `agents/` dentro de `friday/` — são contextos separados.

### 3.2 — Models Pydantic (em `router.py`)

```python
class AgentInvokeRequest(BaseModel):
    agent_id: str
    message: str
    context: dict = {}

class AgentInvokeResponse(BaseModel):
    response: str
    agent_id: str
    model: str
```

### 3.3 — Lógica do handler (`handler.py`)

Passos em ordem:

1. **Buscar agente no Supabase**
   - `SELECT * FROM agents WHERE agent_id = ? AND active = true`
   - Use `supabase.table("agents").select("*").eq("agent_id", agent_id).eq("active", True).maybe_single().execute()`
   - Se `.data` for None → raise HTTPException 404 com mensagem `"Agent '{agent_id}' not found or inactive."`

2. **Extrair campos do registro**
   - `system_prompt = agent_record.get("system_prompt") or ""`
   - `model = agent_record.get("model") or "claude-haiku-4-5-20251001"`
   - `max_tokens = agent_record.get("max_tokens") or 1024`
   - `client_id = agent_record.get("client_id") or context.get("client_id") or settings.sparkle_internal_client_id`

3. **Enriquecer system_prompt com contexto (opcional, mas recomendado)**
   - Se `context` tiver `from_number`, concatenar ao system_prompt:
     `"Número do usuário: {from_number}"`
   - Isso permite ao agente personalizar a resposta por usuário se necessário.

4. **Chamar Claude via `call_claude()`**
   - Usar `runtime.utils.llm.call_claude` — **nunca chamar `anthropic.Client` diretamente**
   - Passar `purpose="agent_invoke"` para rastrear no `llm_cost_log`
   - Passar `agent_id=agent_id` e `client_id=client_id` para custo ser atribuído corretamente

5. **Retornar `AgentInvokeResponse`**

### 3.4 — Integração em `main.py`

Adicionar no bloco de routers (após os routers existentes):

```python
from runtime.agents.router import router as agents_router
app.include_router(agents_router, prefix="/agent", tags=["agents"])
```

O path final do endpoint será: `POST /agent/invoke`

### 3.5 — Exemplo de insert para testar (Supabase Table Editor)

```json
{
  "agent_id": "zenya-ensinaja",
  "name": "Zenya - Ensinaja",
  "system_prompt": "Você é Zenya, assistente virtual da escola Ensinaja em Guaratinguetá/SP. Responda dúvidas sobre matrículas, horários e cursos. Seja cordial e objetivo.",
  "model": "claude-haiku-4-5-20251001",
  "max_tokens": 512,
  "client_id": "ensinaja-uuid",
  "tools": [],
  "active": true
}
```

Após inserção, testar com:
```
POST /agent/invoke
{"agent_id": "zenya-ensinaja", "message": "Qual o horário de funcionamento?", "context": {}}
```

---

## Parte 4 — Decisões Arquiteturais

### Por que router próprio (`/agent`) em vez de `/friday`?

`/friday` é a interface pessoal do Mauro via WhatsApp — tem dispatcher de intent, histórico de conversa, TTS. É stateful e orientada a contexto de usuário único.

`/agent/invoke` é stateless e orientado a multi-tenancy: qualquer sistema (portal, n8n, outra Zenya) pode invocar qualquer agente pelo `agent_id`. Misturar os dois routers criaria acoplamento desnecessário e dificultaria escalar o multi-tenant.

### Por que não criar uma nova abstração de "agente executor"?

O `call_claude()` em `utils/llm.py` já é a abstração certa. Ele garante:
- Log de custo automático no `llm_cost_log`
- Interface única para todos os modelos Claude
- Sem acoplamento direto com `anthropic.Client`

Criar uma camada extra seria over-engineering para o estágio atual.

### Por que `tools` é jsonb array de strings e não objetos de tool?

No estágio atual, as "tools" de um agente são na verdade intents/handlers já existentes no runtime (ex: `loja_integrada_query`). Armazenar strings e resolver para funções no código é mais simples e não requer Anthropic Tool Use ainda.

Quando precisarmos de Anthropic Tool Use real (function calling), a coluna já está lá — só muda o formato do jsonb e a lógica do handler. O schema não precisa mudar.

### Por que `maybe_single()` e não `single()`?

`single()` lança exceção se não encontrar resultado. `maybe_single()` retorna `None` em `.data` sem lançar — deixa o handler Python decidir o erro HTTP correto (404). Padrão mais seguro para endpoints públicos.

---

## Checklist @dev

- [ ] Criar `runtime/agents/__init__.py` (vazio)
- [ ] Criar `runtime/agents/handler.py` com função `invoke_agent(agent_id, message, context) -> dict`
- [ ] Criar `runtime/agents/router.py` com `POST /invoke` usando `AgentInvokeRequest` / `AgentInvokeResponse`
- [ ] Adicionar `include_router` em `main.py`
- [ ] Executar SQL do Parte 1 no Supabase
- [ ] Inserir agente de teste `zenya-ensinaja` na tabela
- [ ] Testar endpoint com agente ativo
- [ ] Testar com `agent_id` inexistente → deve retornar 404
- [ ] Testar com `active = false` → deve retornar 404
- [ ] Verificar `llm_cost_log` após invocação — `purpose` deve ser `"agent_invoke"`
- [ ] Atualizar `RUNTIME_STATE.md` com novo endpoint e schema expandido

---

## Handoff

Após @dev implementar e @qa validar:
- Atualizar `RUNTIME_STATE.md` tabela `agents` com novas colunas
- Atualizar `RUNTIME_STATE.md` seção Endpoints com `POST /agent/invoke`
- Registrar em `memory/work_log.md` como `[FUNCIONAL]`
