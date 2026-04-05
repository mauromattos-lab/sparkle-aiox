-- Migration 013: cron_executions
-- Tabela de log de execução de crons para auditabilidade operacional (SUB-8)
-- Cada disparo do APScheduler gera uma linha com status, duração e erro (se houver)

CREATE TABLE IF NOT EXISTS cron_executions (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    cron_name     TEXT        NOT NULL,
    task_type     TEXT,
    started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at   TIMESTAMPTZ,
    duration_ms   INTEGER,
    status        TEXT        NOT NULL DEFAULT 'running'
                  CHECK (status IN ('running', 'success', 'error')),
    error         TEXT,
    rows_affected INTEGER,
    task_id       UUID,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cron_executions_cron_name  ON cron_executions (cron_name);
CREATE INDEX IF NOT EXISTS idx_cron_executions_started_at ON cron_executions (started_at DESC);
CREATE INDEX IF NOT EXISTS idx_cron_executions_status     ON cron_executions (status);
