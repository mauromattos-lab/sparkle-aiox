# SYS Design Spec — Sistema Vivo: Brain + Contexto + Handoffs

**Autor:** Aria (@architect) | **Data:** 2026-04-02
**Status:** SPEC APROVADA PARA IMPLEMENTACAO
**Destinatario:** @dev

---

## Visao Geral da Arquitetura

Tres subsistemas interconectados transformam o Runtime de "corpo que executa" em "organismo que pensa e aprende":

```
                    +-------------------+
                    |   FONTES EXTERNAS |
                    | YouTube, PDF, URL |
                    | audio, conversa   |
                    +--------+----------+
                             |
                    +--------v----------+
                    |  SYS-1: PIPELINE  |
                    |  MEGA BRAIN       |
                    |  6 fases Finch    |
                    +--------+----------+
                             |
              +--------------+--------------+
              |                             |
     +--------v----------+       +----------v--------+
     |  SYS-2: CONTEXTO  |       |  SYS-3: HANDOFFS  |
     |  PERSISTENTE       |       |  AUTOMATICOS       |
     |  (injeta em cada   |       |  (workflows reais  |
     |   agente ativado)  |       |   com steps)       |
     +--------+----------+       +----------+--------+
              |                             |
              +-------------+---------------+
                            |
                   +--------v----------+
                   |  RUNTIME (corpo)  |
                   |  FastAPI + ARQ    |
                   |  Supabase + Redis |
                   +-------------------+
```

**Conexoes criticas:**

1. SYS-1 alimenta SYS-2 — o Brain produz chunks, DNA, narrativas que compoem o contexto
2. SYS-2 alimenta SYS-3 — cada agente dentro de um workflow recebe contexto completo automaticamente
3. SYS-3 alimenta SYS-1 — outputs de workflows sao auto-ingeridos no Brain (brain_worthy ja funciona)

---

## SYS-1: Pipeline de Ingestao Mega Brain no Runtime

### O que ja existe (base funcional)

| Componente | Status | Onde |
|-----------|--------|------|
| `brain_ingest` handler | Funcional | handlers/brain_ingest.py |
| `brain_ingest_url` endpoint | Funcional | brain/ingest_url.py |
| Canonicalizacao de entidades | Funcional | brain_ingest.py + tabela brain_entities |
| Embedding via OpenAI | Funcional | text-embedding-3-small |
| `extract_dna` handler | Funcional | handlers/extract_dna.py (6 camadas) |
| `narrative_synthesis` handler | Funcional | handlers/narrative_synthesis.py |
| `match_brain_chunks` RPC | Funcional | pgvector no Supabase |
| Chunking basico | Funcional | ingest_url.py (_chunk_text) |
| Brain Gate no worker | Funcional | worker.py (injeta contexto em todo task) |

### O que falta: pipeline unificada de 6 fases

O que existe sao handlers isolados. O que falta eh um **pipeline orchestrator** que encadeia as 6 fases do Finch automaticamente ao receber qualquer conteudo.

### Design: handler `brain_ingest_pipeline`

Novo handler que orquestra as 6 fases em sequencia. Nao substitui os handlers existentes — os reutiliza.

```
POST /brain/ingest-pipeline
{
  "source_type": "youtube" | "pdf_text" | "url" | "transcript" | "conversation" | "document",
  "source_ref": "https://youtube.com/...",      // URL ou referencia
  "raw_content": "...",                          // OU conteudo direto (transcript, texto)
  "title": "Live Finch 27/02",
  "persona": "mauro",                           // namespace: mauro | especialista | cliente
  "client_id": null,                            // null = sparkle-internal
  "target_entity": "Thiago Finch",              // opcional: entidade principal
  "run_dna": true,                              // se deve rodar extract_dna ao final
  "run_narrative": true                          // se deve rodar narrative_synthesis
}
```

**Pseudocodigo do handler:**

```python
async def handle_brain_ingest_pipeline(task: dict) -> dict:
    payload = task["payload"]
    task_id = task["id"]
    client_id = task.get("client_id")

    # FASE 1: Raw Storage — obter conteudo bruto
    if payload.get("source_ref"):
        # Delega para logica existente de ingest_url
        raw_text, title = await _extract_from_source(
            source_type=payload["source_type"],
            source_ref=payload["source_ref"],
        )
    else:
        raw_text = payload["raw_content"]
        title = payload.get("title", "direct_input")

    if not raw_text or len(raw_text) < 50:
        return {"error": "Conteudo muito curto para ingestao"}

    # Salva raw completo em brain_raw_ingestions (nova tabela)
    raw_id = await _save_raw(raw_text, title, payload, task_id)

    # FASE 2: Chunking Semantico
    chunks = _semantic_chunk(raw_text, chunk_size=1500, overlap=200)

    # FASE 3: Canonicalizacao + FASE 4: Embedding
    chunk_ids = []
    for i, chunk_text in enumerate(chunks):
        # Canonicaliza entidades (reutiliza logica existente)
        canonical, entity_tags = await canonicalize_entities(chunk_text, client_id)

        # Gera embedding
        embedding = await _get_embedding(canonical or chunk_text)

        # Insere em brain_chunks
        row = {
            "raw_content": chunk_text,
            "canonical_content": canonical if canonical != chunk_text else None,
            "source_type": payload["source_type"],
            "source_title": f"{title} (chunk {i+1}/{len(chunks)})" if len(chunks) > 1 else title,
            "pipeline_type": payload.get("persona", "mauro"),
            "chunk_metadata": {
                "source_ref": payload.get("source_ref"),
                "source_agent": "brain_pipeline",
                "chunk_index": i,
                "total_chunks": len(chunks),
                "entity_tags": entity_tags,
                "raw_ingestion_id": str(raw_id),
            },
        }
        if client_id:
            row["client_id"] = client_id
        if embedding:
            row["embedding"] = embedding

        result = await insert_chunk(row)
        if result:
            chunk_ids.append(result)

    # FASE 5: Insight Extraction + DNA (condicional)
    dna_stats = None
    if payload.get("run_dna", True) and chunk_ids:
        # Cria sub-task extract_dna com os chunk_ids inseridos
        dna_stats = await _run_extract_dna(chunk_ids, task_id, client_id)

    # FASE 6: Narrative Synthesis (condicional)
    narrative_stats = None
    if payload.get("run_narrative", True):
        narrative_stats = await _run_narrative_synthesis(
            target_entity=payload.get("target_entity"),
            task_id=task_id,
            client_id=client_id,
        )

    return {
        "message": f"Pipeline completa: {len(chunk_ids)} chunks ingeridos",
        "raw_ingestion_id": str(raw_id),
        "chunks_inserted": len(chunk_ids),
        "chunk_ids": chunk_ids,
        "dna": dna_stats,
        "narrative": narrative_stats,
        "brain_worthy": True,  # auto-ingere o resultado no Brain
    }
```

### Schema Supabase: nova tabela `brain_raw_ingestions`

Armazena o conteudo bruto completo antes de chunking — preserva rastreabilidade total.

```sql
CREATE TABLE IF NOT EXISTS brain_raw_ingestions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type TEXT NOT NULL,          -- youtube, pdf_text, url, transcript, conversation, document
    source_ref TEXT,                    -- URL ou referencia externa
    title TEXT NOT NULL,
    raw_content TEXT NOT NULL,          -- conteudo bruto completo (sem limite)
    pipeline_type TEXT DEFAULT 'mauro', -- mauro | especialista | cliente
    client_id UUID REFERENCES clients(id),  -- NULL = sparkle-internal
    metadata JSONB DEFAULT '{}',       -- source_agent, extra context
    task_id UUID,                       -- task que disparou a ingestao
    chunks_generated INT DEFAULT 0,
    status TEXT DEFAULT 'completed',    -- completed | failed | processing
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_brain_raw_source_type ON brain_raw_ingestions(source_type);
CREATE INDEX idx_brain_raw_client_id ON brain_raw_ingestions(client_id);
```

### Coluna nova em `brain_chunks`

```sql
ALTER TABLE brain_chunks
    ADD COLUMN IF NOT EXISTS raw_ingestion_id UUID REFERENCES brain_raw_ingestions(id);
```

Vincula cada chunk ao raw de origem — cadeia de custodia completa.

### Endpoint REST

```
POST /brain/ingest-pipeline    -- dispara pipeline completa
GET  /brain/ingestions          -- lista ingestoes (com stats)
GET  /brain/ingestions/:id      -- detalhe de uma ingestao (chunks, DNA gerado)
```

### Cron opcional: auto-ingestao de conversas acumuladas

Adicionar ao scheduler um job semanal que:
1. Busca conversations do Mauro com Friday das ultimas 7 dias
2. Agrupa por tema (via classificacao rapida Haiku)
3. Dispara `brain_ingest_pipeline` para cada grupo

```python
# scheduler.py — adicionar:
async def _run_weekly_brain_digest() -> None:
    await _run_and_execute("brain_weekly_digest", priority=3)
```

---

## SYS-2: Agent Context Persistente

### Problema

Hoje, `activate_agent` monta o system prompt assim:

```python
_ANALYST_SYSTEM = (
    "Voce e o @analyst da Sparkle AIOX..."
    "Ferramentas disponiveis: brain_query, supabase_read..."
)
```

Esse contexto eh **hardcoded no codigo**. O agente nao sabe:
- Quais outros agentes existem e o que cada um faz
- Quais processos deve seguir (os 6 processos do sparkle-os-processes.md)
- Qual eh o estado atual do sistema (sprints, items, bloqueios)
- Quais clientes existem e qual o contexto de cada um
- Qual DNA foi extraido e como usar
- Quais MCPs e tools estao disponiveis alem do hardcoded

### Design: Context Assembly Service

Um modulo `runtime/context/assembler.py` que monta o contexto completo sob demanda. Chamado por `activate_agent` antes de executar qualquer subagente.

**Arquitetura em camadas (do mais estavel ao mais volatil):**

```
CAMADA 1: SISTEMA (quase nunca muda)
  - Quem somos (Sparkle AIOX, AI-native)
  - Agentes disponiveis e o que cada um faz
  - Ferramentas disponiveis (MCPs, tools)
  - Regras inviolaveis (7 regras + anti-patterns)
  - Modelo de roteamento de IA (Opus/Sonnet/Haiku/Groq)

CAMADA 2: PROCESSOS (muda a cada sprint)
  - Os 6 processos operacionais
  - Formato de handoff obrigatorio
  - Gates de qualidade
  - Bootstrap do agente especifico

CAMADA 3: ESTADO (muda a cada hora)
  - Sprint items e status atual
  - Clientes ativos e MRR
  - Tasks em execucao e bloqueios
  - Datetime atual (Brasilia)

CAMADA 4: CONHECIMENTO (muda a cada ingestao)
  - DNA do agente (agent_dna filtrado por agent_id)
  - Narrativas de entidades relevantes (brain_entities)
  - Chunks relevantes para o request (Brain Gate ja faz isso)
```

### Schema Supabase: tabela `agent_context_blocks`

Armazena os blocos de contexto em vez de manter em codigo Python.

```sql
CREATE TABLE IF NOT EXISTS agent_context_blocks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    block_key TEXT UNIQUE NOT NULL,     -- ex: "system.identity", "process.onboarding", "agent.analyst.bootstrap"
    layer TEXT NOT NULL,                -- system | process | state | knowledge
    agent_id TEXT,                      -- NULL = global (todos agentes), "analyst" = so analyst
    content TEXT NOT NULL,              -- o texto do bloco
    priority INT DEFAULT 5,            -- ordem dentro da camada (1=primeiro)
    active BOOLEAN DEFAULT TRUE,
    version INT DEFAULT 1,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_context_blocks_layer ON agent_context_blocks(layer, active);
CREATE INDEX idx_context_blocks_agent ON agent_context_blocks(agent_id, active);
```

### Pseudocodigo do Context Assembler

```python
# runtime/context/assembler.py

MAX_CONTEXT_TOKENS = 12000  # limite para nao estourar janela

async def assemble_context(agent_id: str, request: str = "") -> str:
    """
    Monta o system prompt completo para um agente.
    Combina blocos estaticos (Supabase) + dados dinamicos (queries ao vivo).
    """
    blocks = []

    # CAMADA 1: SISTEMA — blocos estaticos do banco
    system_blocks = await _get_blocks(layer="system", agent_id=agent_id)
    blocks.extend(system_blocks)

    # CAMADA 2: PROCESSOS — blocos estaticos filtrados por agente
    process_blocks = await _get_blocks(layer="process", agent_id=agent_id)
    blocks.extend(process_blocks)

    # CAMADA 3: ESTADO — montado dinamicamente
    state = await _build_state_context()
    blocks.append(state)

    # CAMADA 4: CONHECIMENTO — DNA do agente + narrativas relevantes
    knowledge = await _build_knowledge_context(agent_id, request)
    blocks.append(knowledge)

    # Monta texto final com headers de secao
    sections = []
    for block in blocks:
        sections.append(f"## {block['title']}\n{block['content']}")

    full_context = "\n\n---\n\n".join(sections)

    # Trunca se necessario (preserva camadas 1 e 2 integrais)
    return _truncate_if_needed(full_context, MAX_CONTEXT_TOKENS)


async def _get_blocks(layer: str, agent_id: str) -> list[dict]:
    """Busca blocos do banco: globais + especificos do agente."""
    result = await asyncio.to_thread(
        lambda: supabase.table("agent_context_blocks")
        .select("block_key,content,priority")
        .eq("layer", layer)
        .eq("active", True)
        .or_(f"agent_id.is.null,agent_id.eq.{agent_id}")
        .order("priority")
        .execute()
    )
    return [
        {"title": r["block_key"], "content": r["content"]}
        for r in (result.data or [])
    ]


async def _build_state_context() -> dict:
    """Monta contexto de estado atual do sistema — queries ao vivo."""
    # Clientes ativos
    clients = await asyncio.to_thread(
        lambda: supabase.table("clients")
        .select("name,type,mrr,status")
        .eq("status", "active")
        .execute()
    )
    clients_text = "\n".join(
        f"- {c['name']} ({c['type']}): R${c.get('mrr', 0)}/mes — {c['status']}"
        for c in (clients.data or [])
    )

    # Sprint items ativos
    items = await asyncio.to_thread(
        lambda: supabase.table("agent_work_items")
        .select("sprint_item,status,agent_id,notes")
        .neq("status", "done")
        .order("created_at", desc=True)
        .limit(15)
        .execute()
    )
    items_text = "\n".join(
        f"- {i['sprint_item']}: {i['status']} ({i.get('agent_id', '?')})"
        for i in (items.data or [])
    )

    now_brasilia = datetime.now(ZoneInfo("America/Sao_Paulo"))
    state_text = (
        f"Data/hora: {now_brasilia.strftime('%d/%m/%Y %H:%M')} (Brasilia)\n\n"
        f"Clientes ativos:\n{clients_text or 'Nenhum cliente ativo no banco'}\n\n"
        f"Items de sprint em andamento:\n{items_text or 'Nenhum item ativo'}"
    )
    return {"title": "Estado Atual do Sistema", "content": state_text}


async def _build_knowledge_context(agent_id: str, request: str) -> dict:
    """Busca DNA do agente + narrativas relevantes."""
    # DNA do agente
    dna = await asyncio.to_thread(
        lambda: supabase.table("agent_dna")
        .select("layer,content")
        .eq("agent_id", agent_id)
        .eq("active", True)
        .limit(20)
        .execute()
    )
    dna_text = ""
    if dna.data:
        by_layer = {}
        for d in dna.data:
            by_layer.setdefault(d["layer"], []).append(d["content"])
        for layer, items in by_layer.items():
            dna_text += f"\n### {layer.title()}\n"
            for item in items:
                dna_text += f"- {item}\n"

    # Narrativas de entidades (top 3 mais recentes)
    narratives = await asyncio.to_thread(
        lambda: supabase.table("brain_entities")
        .select("canonical_name,narrative")
        .not_.is_("narrative", "null")
        .order("updated_at", desc=True)
        .limit(3)
        .execute()
    )
    narratives_text = "\n\n".join(
        f"**{n['canonical_name']}:** {n['narrative'][:500]}"
        for n in (narratives.data or [])
        if n.get("narrative")
    )

    content = ""
    if dna_text:
        content += f"DNA do Agente:\n{dna_text}\n\n"
    if narratives_text:
        content += f"Entidades Conhecidas:\n{narratives_text}"

    return {"title": "Conhecimento (Brain)", "content": content or "Sem DNA ou narrativas carregados."}
```

### Integracao com `activate_agent`

Modificar `_run_subagent` em `activate_agent.py`:

```python
# ANTES (hardcoded):
system = agent_config["system_prompt"]

# DEPOIS (dinamico):
from runtime.context.assembler import assemble_context
base_system = agent_config.get("system_prompt_base", "")  # instrucoes minimas do agente
dynamic_context = await assemble_context(agent_key, user_prompt)
system = f"{base_system}\n\n{dynamic_context}"
```

### Seed inicial dos blocos de contexto

Ao implementar, @dev deve criar um script/migration que popula `agent_context_blocks` com o conteudo de:
- `AGENT_CONTEXT.md` → blocos de camada "system"
- `sparkle-os-processes.md` → blocos de camada "process"
- Bootstrap files por agente → blocos de camada "process" com agent_id

Formato: um bloco por secao logica (nao o arquivo inteiro num bloco so).

### Endpoint para gerenciar contexto

```
GET    /context/blocks                    -- lista todos os blocos ativos
GET    /context/blocks?agent=analyst      -- blocos de um agente
POST   /context/blocks                    -- cria novo bloco
PUT    /context/blocks/:id                -- atualiza bloco
DELETE /context/blocks/:id                -- desativa bloco (soft delete)
GET    /context/preview?agent=analyst     -- preview do contexto montado
```

O endpoint `GET /context/preview` eh essencial: permite que Mauro ou qualquer agente veja exatamente o que outro agente receberia como contexto, sem precisar ativar o agente.

---

## SYS-3: Handoff Automatico entre Agentes

### O que ja existe

O worker ja tem:
- **Handoff engine**: se handler retorna `{"handoff_to": "task_type", "handoff_payload": {...}}`, cria task automaticamente (worker.py linhas 183-194)
- **Workflow context**: `_steps` array em JSONB para encadeamento (CORE-1)
- **Gate enforcement**: tasks podem ter `required_gates` e `gates_cleared` (worker.py linhas 142-153)

### O que falta: templates de workflow

Templates sao definicoes declarativas de workflows completos, armazenadas no Supabase. O Runtime le o template e cria as tasks encadeadas automaticamente.

### Schema Supabase: tabelas de workflow

```sql
-- Templates de workflow (definicao estatica)
CREATE TABLE IF NOT EXISTS workflow_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT UNIQUE NOT NULL,          -- "onboarding_zenya", "landing_page", "content_production"
    name TEXT NOT NULL,
    description TEXT,
    steps JSONB NOT NULL,               -- array de steps (ver abaixo)
    default_priority INT DEFAULT 7,
    active BOOLEAN DEFAULT TRUE,
    version INT DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Instancias de workflow em execucao
CREATE TABLE IF NOT EXISTS workflow_instances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID REFERENCES workflow_templates(id),
    template_slug TEXT NOT NULL,
    name TEXT NOT NULL,                 -- "Onboarding Confeitaria Maria"
    client_id UUID REFERENCES clients(id),
    current_step INT DEFAULT 0,
    status TEXT DEFAULT 'running',      -- running | paused | completed | failed | cancelled
    context JSONB DEFAULT '{}',         -- dados acumulados entre steps
    started_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_workflow_instances_status ON workflow_instances(status);
CREATE INDEX idx_workflow_instances_client ON workflow_instances(client_id);
```

### Formato do campo `steps` em workflow_templates

```json
[
    {
        "step": 0,
        "name": "scrape_site",
        "task_type": "brain_ingest_pipeline",
        "agent_id": "analyst",
        "description": "Scrapeia site do cliente e ingere no Brain",
        "payload_template": {
            "source_type": "url",
            "source_ref": "{{context.site_url}}",
            "title": "Site {{context.business_name}}",
            "persona": "cliente",
            "client_id": "{{context.client_id}}"
        },
        "required_gates": [],
        "on_success": {"next_step": 1},
        "on_failure": {"next_step": 1, "continue": true},
        "timeout_s": 120
    },
    {
        "step": 1,
        "name": "generate_kb",
        "task_type": "onboard_client",
        "agent_id": "dev",
        "...": "..."
    }
]
```

**Regras do template:**
- `{{context.field}}` eh substituido por valores do `context` JSONB da instancia
- `required_gates` pode conter `["qa", "po"]` — step so executa apos aprovacao
- `on_success.next_step` pode ser numero (sequencial) ou lista (paralelo)
- `on_failure.continue: true` significa que falha nao bloqueia o workflow
- Cada step que completa atualiza `workflow_instances.context` com seu resultado

### Handler: `workflow_orchestrator`

Novo handler que gerencia a execucao de workflows.

```python
async def handle_workflow_step(task: dict) -> dict:
    """
    Executa um step de workflow.
    Chamado automaticamente pelo handoff engine.
    """
    payload = task["payload"]
    instance_id = payload["workflow_instance_id"]
    step_index = payload["step_index"]

    # 1. Carrega instancia e template
    instance = await _get_instance(instance_id)
    template = await _get_template(instance["template_id"])
    steps = template["steps"]

    if step_index >= len(steps):
        # Workflow concluido
        await _complete_instance(instance_id)
        return {"message": f"Workflow '{instance['name']}' concluido!", "workflow_completed": True}

    step = steps[step_index]
    context = instance.get("context", {})

    # 2. Resolve payload template com variaveis do context
    resolved_payload = _resolve_template(step["payload_template"], context)

    # 3. Cria e executa a task real
    result = await _execute_step_task(
        task_type=step["task_type"],
        payload=resolved_payload,
        agent_id=step.get("agent_id", "system"),
        client_id=instance.get("client_id"),
        required_gates=step.get("required_gates", []),
    )

    # 4. Atualiza context da instancia com resultado
    context[f"step_{step_index}_result"] = result
    await _update_instance(instance_id, {
        "current_step": step_index + 1,
        "context": context,
    })

    # 5. Determina proximo step
    outcome = step.get("on_success", {}) if result.get("status") != "failed" else step.get("on_failure", {})
    next_step = outcome.get("next_step", step_index + 1)

    if isinstance(next_step, list):
        # Steps paralelos — cria tasks para cada um
        for ns in next_step:
            return {
                "handoff_to": "workflow_step",
                "handoff_payload": {"workflow_instance_id": instance_id, "step_index": ns},
            }
    else:
        return {
            "handoff_to": "workflow_step",
            "handoff_payload": {"workflow_instance_id": instance_id, "step_index": next_step},
        }
```

### Endpoint para disparar workflows

```
POST /workflow/start
{
    "template_slug": "onboarding_zenya",
    "name": "Onboarding Confeitaria Maria",
    "client_id": "uuid-do-cliente",
    "context": {
        "business_name": "Confeitaria Maria",
        "site_url": "mariaconfeitaria.com.br",
        "phone": "5511999999999",
        "business_type": "confeitaria"
    }
}

GET  /workflow/instances                    -- lista instancias ativas
GET  /workflow/instances/:id                -- detalhes de uma instancia
POST /workflow/instances/:id/pause          -- pausa workflow
POST /workflow/instances/:id/resume         -- retoma workflow
POST /workflow/instances/:id/cancel         -- cancela workflow
```

### Template 1: Onboarding Zenya

```json
{
    "slug": "onboarding_zenya",
    "name": "Onboarding Novo Cliente Zenya",
    "description": "Pipeline completa: scrape -> KB -> config -> clone -> QA -> go-live",
    "steps": [
        {
            "step": 0,
            "name": "scrape_e_pesquisa",
            "task_type": "brain_ingest_pipeline",
            "agent_id": "analyst",
            "description": "Scrape site + Instagram do cliente. Ingere no Brain com persona=cliente",
            "payload_template": {
                "source_type": "url",
                "source_ref": "{{site_url}}",
                "title": "Site {{business_name}}",
                "persona": "cliente",
                "client_id": "{{client_id}}",
                "run_dna": false,
                "run_narrative": false
            },
            "required_gates": [],
            "on_success": {"next_step": 1}
        },
        {
            "step": 1,
            "name": "gerar_kb_e_prompt",
            "task_type": "onboard_client",
            "agent_id": "dev",
            "description": "Gera KB (20-30 itens) + system prompt + cria registro em clients",
            "payload_template": {
                "business_name": "{{business_name}}",
                "business_type": "{{business_type}}",
                "site_url": "{{site_url}}",
                "phone": "{{phone}}",
                "client_id": "{{client_id}}"
            },
            "required_gates": [],
            "on_success": {"next_step": 2}
        },
        {
            "step": 2,
            "name": "review_po",
            "task_type": "activate_agent",
            "agent_id": "po",
            "description": "PO revisa system prompt: tom de voz, alinhamento SOUL.md, copy",
            "payload_template": {
                "agent": "@po",
                "request": "Revise o system prompt do cliente {{business_name}} (client_id={{client_id}}). Verifique tom de voz, alinhamento com Zenya SOUL.md, copy das respostas padrao. Consulte o Brain para contexto do cliente."
            },
            "required_gates": [],
            "on_success": {"next_step": 3}
        },
        {
            "step": 3,
            "name": "qa_test",
            "task_type": "activate_agent",
            "agent_id": "qa",
            "description": "QA executa 20+ conversas de teste por categoria",
            "payload_template": {
                "agent": "@qa",
                "request": "Execute o plano de testes para o cliente {{business_name}} (client_id={{client_id}}). Teste: identidade, escalamento humano, edge cases, tom de voz. Reporte pass/fail por categoria."
            },
            "required_gates": ["qa"],
            "on_success": {"next_step": 4},
            "on_failure": {"next_step": 1, "continue": false}
        },
        {
            "step": 4,
            "name": "go_live",
            "task_type": "activate_agent",
            "agent_id": "devops",
            "description": "DevOps ativa workflows, configura Z-API, go-live",
            "payload_template": {
                "agent": "@devops",
                "request": "Ative os workflows do cliente {{business_name}} (client_id={{client_id}}). Configure Z-API, ative Chatwoot inbox, confirme go-live."
            },
            "required_gates": ["sm"],
            "on_success": {"next_step": 5}
        },
        {
            "step": 5,
            "name": "notifica_mauro",
            "task_type": "chat",
            "agent_id": "friday",
            "description": "Friday notifica Mauro que onboarding esta completo",
            "payload_template": {
                "original_text": "Onboarding do cliente {{business_name}} concluido. Zenya ativa e respondendo. Workflows ativados, QA aprovado, go-live confirmado."
            },
            "required_gates": [],
            "on_success": {}
        }
    ]
}
```

### Template 2: Landing Page por Nicho

```json
{
    "slug": "landing_page_nicho",
    "name": "Landing Page por Nicho",
    "description": "Pesquisa -> Copy -> UX -> Dev -> QA -> Deploy",
    "steps": [
        {
            "step": 0,
            "name": "pesquisa_nicho",
            "task_type": "activate_agent",
            "agent_id": "analyst",
            "description": "Pesquisa dores, desejos e linguagem do nicho",
            "payload_template": {
                "agent": "@analyst",
                "request": "Pesquise o nicho '{{niche}}' para landing page Zenya. Entregue: dores reais do publico, termos do setor, 3 benchmarks visuais de referencia, diferenciais que convertem."
            },
            "required_gates": [],
            "on_success": {"next_step": 1}
        },
        {
            "step": 1,
            "name": "copy_completa",
            "task_type": "activate_agent",
            "agent_id": "po",
            "description": "PO cria copy completa: H1, subtitulo, beneficios, CTAs, pricing",
            "payload_template": {
                "agent": "@po",
                "request": "Com base na pesquisa do nicho '{{niche}}' (step anterior), crie copy completa para landing page: H1, subtitulo, 3 beneficios com icone, depoimento modelo, CTAs (primario e secundario), pricing copy. Consulte o Brain para contexto do step anterior."
            },
            "required_gates": [],
            "on_success": {"next_step": 2}
        },
        {
            "step": 2,
            "name": "implementacao",
            "task_type": "activate_agent",
            "agent_id": "dev",
            "description": "Dev implementa HTML com data-nicho, UTM, fbq, WA links",
            "payload_template": {
                "agent": "@dev",
                "request": "Implemente a landing page do nicho '{{niche}}' usando o template base em landing/index.html. Copy e brief visual dos steps anteriores. Garanta: data-nicho, UTM params, fbq events, WA links corretos."
            },
            "required_gates": [],
            "on_success": {"next_step": 3}
        },
        {
            "step": 3,
            "name": "qa_validacao",
            "task_type": "activate_agent",
            "agent_id": "qa",
            "description": "QA valida links, UTM, fbq, deploy, responsividade",
            "payload_template": {
                "agent": "@qa",
                "request": "Valide a landing page do nicho '{{niche}}'. Checklist: links WA funcionam, UTM params presentes, fbq events disparam, responsiva em mobile, assets existem, copy aplicada corretamente."
            },
            "required_gates": ["qa"],
            "on_success": {"next_step": 4}
        },
        {
            "step": 4,
            "name": "deploy",
            "task_type": "activate_agent",
            "agent_id": "devops",
            "description": "Push + deploy via GitHub Actions",
            "payload_template": {
                "agent": "@devops",
                "request": "Faca deploy da landing page do nicho '{{niche}}'. Push para GitHub, confirme deploy via GitHub Actions, valide URL em producao."
            },
            "required_gates": ["sm"],
            "on_success": {}
        }
    ]
}
```

### Template 3: Producao de Conteudo

```json
{
    "slug": "content_production",
    "name": "Producao de Conteudo Semanal",
    "description": "Briefing -> Roteiro -> Criacao -> Revisao -> Publicacao",
    "steps": [
        {
            "step": 0,
            "name": "briefing",
            "task_type": "activate_agent",
            "agent_id": "analyst",
            "description": "Pesquisa tendencias e define temas da semana",
            "payload_template": {
                "agent": "@analyst",
                "request": "Pesquise tendencias atuais no nicho '{{niche}}' para a persona '{{persona}}'. Sugira 3 temas de conteudo para Instagram com: titulo, angulo, formato (post/carousel/reels), gancho, CTA. Use EXA para dados frescos."
            },
            "required_gates": [],
            "on_success": {"next_step": 1}
        },
        {
            "step": 1,
            "name": "roteiro_e_criacao",
            "task_type": "generate_content",
            "agent_id": "dev",
            "description": "Gera conteudo completo (texto + visual prompt)",
            "payload_template": {
                "topic": "{{step_0_result.topics[0]}}",
                "format": "{{format}}",
                "persona": "{{persona}}",
                "source_type": "workflow",
                "source_ref": "content_production"
            },
            "required_gates": [],
            "on_success": {"next_step": 2}
        },
        {
            "step": 2,
            "name": "revisao_po",
            "task_type": "activate_agent",
            "agent_id": "po",
            "description": "PO revisa copy, tom de voz, CTA, hashtags",
            "payload_template": {
                "agent": "@po",
                "request": "Revise o conteudo gerado no step anterior para a persona '{{persona}}'. Valide: tom de voz, CTA claro, hashtags relevantes, sem erros gramaticais, alinhamento com SOUL.md da persona."
            },
            "required_gates": ["po"],
            "on_success": {"next_step": 3}
        },
        {
            "step": 3,
            "name": "publicacao",
            "task_type": "activate_agent",
            "agent_id": "dev",
            "description": "Agenda publicacao via Instagram Graph API",
            "payload_template": {
                "agent": "@dev",
                "request": "Agende a publicacao do conteudo aprovado para o perfil Instagram da persona '{{persona}}'. Horario ideal para o nicho. Confirme agendamento."
            },
            "required_gates": [],
            "on_success": {}
        }
    ]
}
```

---

## Checklist de Implementacao para @dev

Tarefas ordenadas por dependencia. Cada tarefa pode ser um PR atomico.

### Fase 1: Fundacao (sem dependencias entre si)

- [ ] **SYS-1.1** Criar tabela `brain_raw_ingestions` via migration Supabase
- [ ] **SYS-1.2** Adicionar coluna `raw_ingestion_id` em `brain_chunks`
- [ ] **SYS-2.1** Criar tabela `agent_context_blocks` via migration Supabase
- [ ] **SYS-3.1** Criar tabelas `workflow_templates` e `workflow_instances` via migration Supabase

### Fase 2: Handlers (depende da Fase 1)

- [ ] **SYS-1.3** Implementar handler `brain_ingest_pipeline` em `runtime/tasks/handlers/brain_ingest_pipeline.py`
  - Reutiliza: `canonicalize_entities`, `_get_embedding`, `_chunk_text`
  - Chama: `handle_extract_dna`, `handle_narrative_synthesis` internamente
  - Registrar em `registry.py`
- [ ] **SYS-1.4** Criar endpoint `POST /brain/ingest-pipeline` no router (pode ir no `brain/ingest_url.py` existente ou novo arquivo `brain/pipeline_router.py`)
- [ ] **SYS-1.5** Criar endpoints `GET /brain/ingestions` e `GET /brain/ingestions/:id`

### Fase 3: Context Assembler (depende da Fase 1)

- [ ] **SYS-2.2** Criar modulo `runtime/context/assembler.py` com funcao `assemble_context()`
- [ ] **SYS-2.3** Criar script de seed para popular `agent_context_blocks` com conteudo de:
  - `AGENT_CONTEXT.md` → camada system (5-7 blocos)
  - `sparkle-os-processes.md` → camada process (6 blocos, um por processo)
  - Bootstraps por agente → camada process com agent_id
- [ ] **SYS-2.4** Criar endpoints REST para `agent_context_blocks` (CRUD + preview)
  - Pode ser `runtime/context/router.py`
  - Registrar em `main.py`
- [ ] **SYS-2.5** Integrar `assemble_context()` no `activate_agent.py`
  - Substituir system prompt hardcoded pela chamada ao assembler
  - Manter o system prompt base no `_AVAILABLE_AGENTS` como fallback

### Fase 4: Workflow Engine (depende da Fase 2 e 3)

- [ ] **SYS-3.2** Implementar handler `workflow_step` em `runtime/tasks/handlers/workflow_step.py`
  - Template resolution: substituir `{{variable}}` por valores do context
  - Step execution: criar task real e aguardar resultado
  - Next step determination: sequencial ou paralelo
  - Registrar em `registry.py`
- [ ] **SYS-3.3** Criar endpoint `POST /workflow/start` e demais endpoints do workflow router
  - Pode ser `runtime/workflow/router.py`
  - Registrar em `main.py`
- [ ] **SYS-3.4** Popular os 3 templates de workflow via migration ou seed script:
  - `onboarding_zenya`
  - `landing_page_nicho`
  - `content_production`

### Fase 5: Integracao e Cron (depende de tudo anterior)

- [ ] **SYS-1.6** Adicionar cron `brain_weekly_digest` no scheduler (domingo 23h Brasilia)
  - Busca conversas da semana, agrupa, dispara `brain_ingest_pipeline`
- [ ] **SYS-2.6** Expandir `_AVAILABLE_AGENTS` em `activate_agent.py` para incluir mais agentes:
  - @dev, @qa, @architect, @po, @sm (com system_prompt_base minimo, contexto vem do assembler)
- [ ] **SYS-3.5** Integrar Friday: quando Mauro diz "onborda X", Friday dispara `POST /workflow/start` com template `onboarding_zenya` em vez de chamar `onboard_client` diretamente

### Fase 6: Validacao

- [ ] **QA-1** Testar pipeline de ingestao end-to-end: URL YouTube → chunks → DNA → narrativa
- [ ] **QA-2** Testar context assembler: ativar @analyst e verificar que recebe contexto completo
- [ ] **QA-3** Testar workflow onboarding: disparar via API e verificar que steps executam em sequencia
- [ ] **QA-4** Verificar que Brain Gate continua funcionando (nao quebrou com mudancas)
- [ ] **QA-5** Verificar custos: monitorar `llm_cost_log` durante testes

---

## Decisoes de Design e Justificativas

| Decisao | Justificativa |
|---------|--------------|
| Pipeline handler em vez de microservicos | Runtime-first: tudo roda no mesmo processo FastAPI. Sem infra nova. |
| `brain_raw_ingestions` como tabela separada | Rastreabilidade (crenca Finch #1): cada chunk sabe de onde veio. Texto bruto preservado. |
| Context blocks no banco, nao em codigo | Editavel sem deploy. Mauro ou qualquer agente pode atualizar contexto via API. |
| Workflow templates declarativos em JSONB | Novos workflows sem codigo. Basta inserir template no banco e o engine executa. |
| Context assembler com 4 camadas | Prioridade clara: sistema > processos > estado > conhecimento. Trunca conhecimento primeiro se estourar janela. |
| Reuso de handlers existentes | Zero reescrita. `brain_ingest_pipeline` orquestra os que ja existem (canonicalize, extract_dna, narrative). |
| Gates nos steps de workflow | Processos Sparkle OS exigem QA/SM/PO gates. Workflow engine respeita isso nativamente. |

---

## Riscos e Mitigacoes

| Risco | Mitigacao |
|-------|----------|
| Contexto muito grande estoura janela do modelo | MAX_CONTEXT_TOKENS = 12000. Camada 4 (conhecimento) eh truncada primeiro. |
| Pipeline longa demora muito (timeout ARQ) | `job_timeout` ja eh 600s. Pipeline pode rodar async — cada fase eh uma sub-task. |
| Workflow instance fica presa se step falha | `on_failure.continue: true` permite pular. Timeout por step. Status "failed" visivel em `/workflow/instances`. |
| Custo de tokens com context assembly para todo agente | Blocos sao texto estatico (sem LLM). So DNA/narrativa vem do banco. Custo = 0 para assembly. |
| Templates de workflow podem ficar desatualizados | Versionados (`version` INT). Blocos podem ser editados via API sem deploy. |

---

---

## SYS-6: Painel de Comando — Interface do Mauro com o Sistema

> Lei 15: "Se parece com Notion ou Trello, esta errado. Se parece com Overwatch ou Final Fantasy, esta no caminho certo."

### Stack existente

| Componente | Status | Onde |
|-----------|--------|------|
| Portal Next.js | FUNCIONAL | `portal/` → portal.sparkleai.tech |
| Mission Control basico | FUNCIONAL | `portal/app/mission-control/page.tsx` |
| Supabase Realtime | FUNCIONAL | WebSocket ativo para `agent_work_items` |
| Traefik | FUNCIONAL | Config em `/traefik/dynamic/portal.yml` no Coolify |

### Visao: nao eh dashboard, eh cockpit

O Mauro nao administra — ele **pilota**. A interface deve dar a sensacao de comando, nao de gerenciamento. Tres areas:

```
+----------------------------------------------+
|              COMMAND BAR (topo)               |
|  Voz / texto → Friday interpreta e aciona    |
+------+-------------------+-------------------+
|      |                   |                    |
| TEAM |   LIVE FEED       |   BRAIN PULSE     |
|      |                   |                    |
| Ver  | Workflows ao      | O que o Brain     |
| cada | vivo: step atual, | aprendeu hoje,    |
| agente| quem esta         | chunks novos,     |
| suas | trabalhando,      | narrativas        |
| skills| handoffs          | crescendo         |
| e    | acontecendo       |                    |
| status|                  |                    |
|      |                   |                    |
+------+-------------------+-------------------+
```

### Endpoints que o painel consome

**Ja existem:**
- `GET /health` — status do Runtime
- `GET /system/state` — sprint items e status
- `GET /brain/search` — busca no Brain
- Supabase Realtime → `agent_work_items` (WebSocket)

**Criados por SYS-1/2/3 (novos):**
- `GET /brain/ingestions` — lista de ingestoes recentes (Brain Pulse)
- `GET /brain/ingestions/:id` — detalhe de ingestao
- `GET /context/preview?agent=X` — preview do contexto de cada agente (Team view)
- `GET /context/blocks` — blocos de contexto editaveis
- `GET /workflow/instances` — workflows ativos ao vivo (Live Feed)
- `GET /workflow/instances/:id` — detalhe com step atual
- `POST /workflow/start` — Mauro aciona workflow pelo painel

**Novos necessarios para SYS-6:**
- `GET /system/pulse` — endpoint consolidado:
  - Agentes: quais existem, qual esta ativo agora, ultimo trabalho
  - Brain: chunks hoje, ingestoes recentes, narrativas atualizadas
  - Workflows: instancias ativas com step atual
  - Crons: proximas execucoes agendadas
  - Clientes: status de cada Zenya (ativa, mensagens ultimas 24h)

### Supabase Realtime para dados ao vivo

Alem do WebSocket de `agent_work_items` ja ativo, adicionar listeners para:

```typescript
// Live Feed — workflows em tempo real
supabase
  .channel('workflow_live')
  .on('postgres_changes', {
    event: '*',
    schema: 'public',
    table: 'workflow_instances'
  }, handleWorkflowChange)

// Brain Pulse — ingestoes em tempo real
supabase
  .channel('brain_live')
  .on('postgres_changes', {
    event: 'INSERT',
    schema: 'public',
    table: 'brain_raw_ingestions'
  }, handleNewIngestion)

// Tasks — agentes trabalhando
supabase
  .channel('tasks_live')
  .on('postgres_changes', {
    event: '*',
    schema: 'public',
    table: 'runtime_tasks',
    filter: 'status=eq.running'
  }, handleTaskChange)
```

### MVP do painel (primeira versao)

Prioridade: mostrar que o sistema VIVE, nao mostrar tudo.

**MVP inclui:**
1. **Team** — cards dos agentes com: nome, icone, status (idle/working/blocked), ultima acao
2. **Live Feed** — stream de eventos: "analyst comecou pesquisa nicho clinica", "QA aprovou landing page", "Brain ingeriu 23 chunks de youtube.com/..."
3. **Command Bar** — input de texto que dispara workflows: "onborda clinica X" → cria instancia

**MVP NAO inclui (v2+):**
- Voz (precisa de Whisper + TTS no frontend)
- Tela de selecao Overwatch completa
- Edicao visual de workflows
- Metricas e graficos

### Direcao visual

- Fundo escuro (como terminal, nao como SaaS)
- Cores de status: verde=ativo, azul=trabalhando, amarelo=esperando, vermelho=erro
- Tipografia monospace para dados, sans-serif para labels
- Animacoes sutis: pulse quando agente esta trabalhando, fade-in quando evento novo chega
- Sem bordas grossas, sem shadows pesados — estilo HUD, nao material design
- Referencia visual: Huly.io + Linear + interfaces de sci-fi

### Checklist SYS-6 (adicionar ao final da Fase 5)

- [ ] **SYS-6.1** Criar endpoint `GET /system/pulse` no Runtime
- [ ] **SYS-6.2** Criar pagina `/command` no Portal (substitui ou evolui mission-control)
- [ ] **SYS-6.3** Implementar Team Panel: cards de agentes com status ao vivo
- [ ] **SYS-6.4** Implementar Live Feed: stream de eventos via Supabase Realtime
- [ ] **SYS-6.5** Implementar Command Bar: input de texto → `POST /workflow/start`
- [ ] **SYS-6.6** Adicionar Realtime listeners para workflow_instances + brain_raw_ingestions + runtime_tasks

---

*SYS-6 adicionado por Orion — 2026-04-02*
*Spec completa: SYS-1 (Brain Pipeline) + SYS-2 (Context Persistente) + SYS-3 (Handoffs) + SYS-6 (Painel de Comando)*
*Pronta para implementacao por @dev — seguir checklist da Fase 1 em diante.*
