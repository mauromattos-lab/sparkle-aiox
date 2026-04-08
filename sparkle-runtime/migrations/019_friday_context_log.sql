-- Migration 019 — W1-FRIDAY-1: Tabela friday_context_log
-- Registra cada consulta ao Brain feita pela Friday durante respostas de chat.
-- Permite auditoria, diagnóstico e métricas de uso do contexto mauro-personal.

CREATE TABLE IF NOT EXISTS friday_context_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interaction_id UUID,
    brain_namespace TEXT NOT NULL DEFAULT 'mauro-personal',
    chunks_retrieved INTEGER NOT NULL DEFAULT 0,
    used_in_response BOOLEAN NOT NULL DEFAULT true,
    fallback_used BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índice para consultas por interação e período
CREATE INDEX IF NOT EXISTS idx_friday_context_log_interaction ON friday_context_log (interaction_id);
CREATE INDEX IF NOT EXISTS idx_friday_context_log_created ON friday_context_log (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_friday_context_log_namespace ON friday_context_log (brain_namespace);
