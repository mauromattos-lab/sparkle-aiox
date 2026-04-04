-- B2-05: Hierarchical 3-Level Handoff System — observability log
-- Tracks every handoff between agents across all three levels:
--   local  = within same workflow/task context
--   layer  = cross-workflow/domain handoff
--   global = escalation to orchestrator (Orion/system)

CREATE TABLE IF NOT EXISTS handoff_log (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_agent    text NOT NULL,
    target_agent    text NOT NULL,
    handoff_level   text NOT NULL CHECK (handoff_level IN ('local', 'layer', 'global')),
    intent          text,
    status          text NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'accepted', 'completed', 'failed', 'escalated')),
    payload_summary text,                       -- short description of what was handed off
    task_id         uuid,                       -- runtime_tasks.id that was created (layer/global)
    parent_task_id  uuid,                       -- originating task, if any
    error           text,                       -- failure reason if status=failed
    created_at      timestamptz NOT NULL DEFAULT now(),
    completed_at    timestamptz
);

-- Fast lookups by agent and level
CREATE INDEX IF NOT EXISTS idx_handoff_log_source
    ON handoff_log (source_agent, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_handoff_log_target
    ON handoff_log (target_agent, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_handoff_log_level
    ON handoff_log (handoff_level, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_handoff_log_status
    ON handoff_log (status);
