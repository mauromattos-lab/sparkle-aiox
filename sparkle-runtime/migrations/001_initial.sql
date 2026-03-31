-- ============================================================
-- Sparkle Runtime — Migration 001: Initial Schema
-- ============================================================
-- Every table has client_id. No exceptions.
-- "sparkle-internal" is Mauro's own client_id for Friday/internal tasks.
-- ============================================================

-- Enable pgvector if not already enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- AGENTS
-- Defines every autonomous agent in the system.
-- agent_id is a short slug (e.g. "friday", "zenya", "qa").
-- ============================================================
CREATE TABLE IF NOT EXISTS agents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id        TEXT NOT NULL UNIQUE,
    agent_type      TEXT NOT NULL CHECK (agent_type IN ('interface', 'worker', 'qa', 'orchestrator')),
    display_name    TEXT NOT NULL,
    capabilities    TEXT[] NOT NULL DEFAULT '{}',
    status          TEXT NOT NULL DEFAULT 'idle'
                        CHECK (status IN ('idle', 'running', 'paused', 'error')),
    escalation_threshold TEXT NOT NULL DEFAULT 'always_escalate',
    last_heartbeat  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- RUNTIME_TASKS
-- The central API bus of the system. Every inter-agent
-- communication goes through here.
-- ============================================================
CREATE TABLE IF NOT EXISTS runtime_tasks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_task_id  UUID REFERENCES runtime_tasks(id) ON DELETE SET NULL,
    agent_id        TEXT REFERENCES agents(agent_id) ON DELETE SET NULL,
    client_id       TEXT NOT NULL DEFAULT 'sparkle-internal',
    task_type       TEXT NOT NULL,
    payload         JSONB NOT NULL DEFAULT '{}',
    status          TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'running', 'done', 'failed', 'cancelled')),
    priority        INTEGER NOT NULL DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),
    result          JSONB,
    error           TEXT,
    retry_count     INTEGER NOT NULL DEFAULT 0,
    max_retries     INTEGER NOT NULL DEFAULT 3,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_runtime_tasks_status ON runtime_tasks(status);
CREATE INDEX IF NOT EXISTS idx_runtime_tasks_client ON runtime_tasks(client_id);
CREATE INDEX IF NOT EXISTS idx_runtime_tasks_type ON runtime_tasks(task_type);
CREATE INDEX IF NOT EXISTS idx_runtime_tasks_priority ON runtime_tasks(priority DESC, created_at ASC);

-- ============================================================
-- LLM_COST_LOG
-- Every Claude API call is logged here via the llm.py wrapper.
-- No direct API calls allowed outside the wrapper.
-- ============================================================
CREATE TABLE IF NOT EXISTS llm_cost_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       TEXT NOT NULL,
    task_id         UUID REFERENCES runtime_tasks(id) ON DELETE SET NULL,
    agent_id        TEXT,
    model           TEXT NOT NULL,
    input_tokens    INTEGER NOT NULL DEFAULT 0,
    output_tokens   INTEGER NOT NULL DEFAULT 0,
    cost_usd        NUMERIC(10, 6) NOT NULL DEFAULT 0,
    purpose         TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_llm_cost_client ON llm_cost_log(client_id);
CREATE INDEX IF NOT EXISTS idx_llm_cost_task ON llm_cost_log(task_id);

-- ============================================================
-- BRAIN_RAW_CHUNKS
-- Phase 1 of the Sparkle Brain pipeline: raw storage of
-- ingested content. Fully isolated by client_id.
-- ============================================================
CREATE TABLE IF NOT EXISTS brain_raw_chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       TEXT NOT NULL,
    source_type     TEXT NOT NULL CHECK (source_type IN ('whatsapp', 'youtube', 'pdf', 'text', 'url', 'internal')),
    source_ref      TEXT,
    content         TEXT NOT NULL,
    chunk_index     INTEGER NOT NULL DEFAULT 0,
    chunk_total     INTEGER,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_brain_raw_client ON brain_raw_chunks(client_id);

-- ============================================================
-- BRAIN_CHUNKS
-- Phase 2+: processed chunks with embeddings.
-- Busca vetorial sempre filtrada por client_id.
-- ============================================================
CREATE TABLE IF NOT EXISTS brain_chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       TEXT NOT NULL,
    raw_chunk_id    UUID REFERENCES brain_raw_chunks(id) ON DELETE CASCADE,
    content         TEXT NOT NULL,
    canonical_content TEXT,
    embedding       vector(1536),
    entity_tags     TEXT[] NOT NULL DEFAULT '{}',
    topics          TEXT[] NOT NULL DEFAULT '{}',
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_brain_chunks_client ON brain_chunks(client_id);
-- pgvector IVFFlat index (create after data is inserted, not now)
-- CREATE INDEX ON brain_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ============================================================
-- BRAIN_ENTITIES
-- Canonical entities per client (whitelist for canonicalization).
-- ============================================================
CREATE TABLE IF NOT EXISTS brain_entities (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       TEXT NOT NULL,
    canonical_name  TEXT NOT NULL,
    aliases         TEXT[] NOT NULL DEFAULT '{}',
    entity_type     TEXT NOT NULL DEFAULT 'general',
    narrative       TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(client_id, canonical_name)
);

CREATE INDEX IF NOT EXISTS idx_brain_entities_client ON brain_entities(client_id);

-- ============================================================
-- SEED: Core agents
-- ============================================================
INSERT INTO agents (agent_id, agent_type, display_name, capabilities, escalation_threshold)
VALUES
    ('friday',  'interface',    'Friday',       ARRAY['voice_input', 'intent_classify', 'whatsapp_reply'], 'never_escalate'),
    ('zenya',   'worker',       'Zenya',        ARRAY['customer_chat', 'kb_lookup', 'order_assist'],       'escalate_on_unknown'),
    ('qa',      'qa',           'QA Agent',     ARRAY['scenario_test', 'go_live_gate'],                    'escalate_on_fail'),
    ('orion',   'orchestrator', 'Orion',        ARRAY['orchestrate', 'task_dispatch', 'status_report'],    'never_escalate'),
    ('brain',   'worker',       'Brain',        ARRAY['ingest', 'embed', 'search', 'canonicalize'],        'escalate_on_error')
ON CONFLICT (agent_id) DO NOTHING;

-- ============================================================
-- RLS: Enable row-level security on all tables
-- ============================================================
ALTER TABLE agents          ENABLE ROW LEVEL SECURITY;
ALTER TABLE runtime_tasks   ENABLE ROW LEVEL SECURITY;
ALTER TABLE llm_cost_log    ENABLE ROW LEVEL SECURITY;
ALTER TABLE brain_raw_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE brain_chunks    ENABLE ROW LEVEL SECURITY;
ALTER TABLE brain_entities  ENABLE ROW LEVEL SECURITY;

-- Service role bypasses RLS (used by the Runtime server)
-- Anon/authenticated roles have no access by default (secure by default)

CREATE INDEX IF NOT EXISTS idx_brain_chunks_raw_chunk_id ON brain_chunks(raw_chunk_id);
