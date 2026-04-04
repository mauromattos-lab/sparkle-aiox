-- B2-06: Observer Quality — response quality evaluation log
-- Tracks per-response Haiku evaluations for all agents.

CREATE TABLE IF NOT EXISTS response_quality_log (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_slug    text NOT NULL,
    user_message_preview text,          -- first 200 chars
    response_preview     text,          -- first 200 chars
    score         float NOT NULL,       -- 0-1 average across criteria
    scores_detail jsonb,                -- {"relevance":0.9,"completeness":0.8,...}
    issues        jsonb DEFAULT '[]',   -- ["issue1","issue2"]
    suggestion    text,                 -- actionable improvement hint
    evaluated_at  timestamptz NOT NULL DEFAULT now()
);

-- Fast lookups: agent performance over time, filtering by score range
CREATE INDEX IF NOT EXISTS idx_quality_log_agent_evaluated
    ON response_quality_log (agent_slug, evaluated_at DESC);

CREATE INDEX IF NOT EXISTS idx_quality_log_score
    ON response_quality_log (score);
