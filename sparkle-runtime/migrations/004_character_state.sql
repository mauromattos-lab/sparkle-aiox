-- 004_character_state.sql — Canonical character state (B1-02)
-- Source of truth for mood, energy, arc, and personality of each character IP.

CREATE TABLE IF NOT EXISTS character_state (
    id              uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
    character_slug  text        NOT NULL UNIQUE,
    mood            text        NOT NULL DEFAULT 'neutral',
    energy          numeric(3,2) NOT NULL DEFAULT 0.75,
    last_event      text,
    last_event_at   timestamptz,
    arc_position    jsonb       DEFAULT '{}',
    personality_traits jsonb    DEFAULT '{}',
    session_context jsonb       DEFAULT '{}',
    updated_at      timestamptz DEFAULT now(),
    created_at      timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_character_state_slug
    ON character_state(character_slug);
