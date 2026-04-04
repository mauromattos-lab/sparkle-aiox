-- B4-05: Member State Engine — Community gamification layer
-- Tables: member_state (XP/level/engagement per client community)
--         member_events (event log with XP attribution)

-- ── member_state ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS member_state (
    id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    client_id       text NOT NULL,
    member_id       text NOT NULL,
    display_name    text,
    level           int NOT NULL DEFAULT 1,
    xp              int NOT NULL DEFAULT 0,
    status          text NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'inactive', 'churned')),
    joined_at       timestamptz NOT NULL DEFAULT now(),
    last_active_at  timestamptz,
    engagement_score numeric(3,2) NOT NULL DEFAULT 0.00
                    CHECK (engagement_score >= 0 AND engagement_score <= 1),
    metadata        jsonb DEFAULT '{}'::jsonb,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),

    UNIQUE (client_id, member_id)
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_member_state_client_id ON member_state (client_id);
CREATE INDEX IF NOT EXISTS idx_member_state_member_id ON member_state (member_id);
CREATE INDEX IF NOT EXISTS idx_member_state_status ON member_state (status);
CREATE INDEX IF NOT EXISTS idx_member_state_level ON member_state (level);
CREATE INDEX IF NOT EXISTS idx_member_state_last_active ON member_state (last_active_at);
CREATE INDEX IF NOT EXISTS idx_member_state_client_xp ON member_state (client_id, xp DESC);

-- ── member_events ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS member_events (
    id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    member_id       uuid NOT NULL REFERENCES member_state(id) ON DELETE CASCADE,
    event_type      text NOT NULL,
    event_data      jsonb DEFAULT '{}'::jsonb,
    xp_earned       int NOT NULL DEFAULT 0,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_member_events_member_id ON member_events (member_id);
CREATE INDEX IF NOT EXISTS idx_member_events_type ON member_events (event_type);
CREATE INDEX IF NOT EXISTS idx_member_events_created ON member_events (created_at);

-- ── RLS (optional, enable if needed) ────────────────────────────────────
-- ALTER TABLE member_state ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE member_events ENABLE ROW LEVEL SECURITY;
