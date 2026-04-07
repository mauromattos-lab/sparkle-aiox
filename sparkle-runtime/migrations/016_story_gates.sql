CREATE TABLE IF NOT EXISTS story_gates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    story_id        TEXT NOT NULL,
    gate            TEXT NOT NULL,
    agent           TEXT NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('pass', 'fail', 'waived', 'skipped')),
    notes           TEXT,
    completed_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (story_id, gate)
);

CREATE INDEX IF NOT EXISTS idx_story_gates_story ON story_gates (story_id);
CREATE INDEX IF NOT EXISTS idx_story_gates_skipped ON story_gates (status) WHERE status = 'skipped';

COMMENT ON TABLE story_gates IS 'Registro de gates do pipeline AIOS por story. Status skipped dispara alerta via Friday.';
