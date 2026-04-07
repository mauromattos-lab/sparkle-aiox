-- Migration: 003_content_pieces
-- Story: CONTENT-1.1 — Migration + Modelo de Dados (content_pieces, calendar)
-- Applied: 2026-04-07
-- Description: Creates content_pieces and content_calendar tables for the Zenya content pipeline

CREATE TABLE IF NOT EXISTS content_pieces (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  creator_id      TEXT NOT NULL DEFAULT 'zenya',
  platform        TEXT NOT NULL DEFAULT 'instagram_reels',
  style           TEXT NOT NULL DEFAULT 'influencer_natural',
  status          TEXT NOT NULL DEFAULT 'briefed'
                  CHECK (status IN (
                    'briefed','image_generating','image_done',
                    'video_generating','video_done','voice_generating',
                    'assembly_pending','assembly_done','pending_approval',
                    'approved','scheduled','published','rejected',
                    'image_failed','video_failed','assembly_failed','publish_failed'
                  )),
  theme           TEXT,
  mood            TEXT,
  brief_notes     TEXT,
  image_prompt    TEXT,
  image_url       TEXT,
  video_prompt    TEXT,
  video_url       TEXT,
  voice_script    TEXT,
  audio_url       TEXT,
  caption         TEXT,
  final_url       TEXT,
  approved_by     TEXT,
  approved_at     TIMESTAMPTZ,
  rejection_reason TEXT,
  mauro_edits     JSONB,
  scheduled_at    TIMESTAMPTZ,
  published_at    TIMESTAMPTZ,
  published_url   TEXT,
  style_ref_ids   UUID[],
  brain_chunk_id  UUID,
  pipeline_log    JSONB DEFAULT '[]',
  error_log       JSONB DEFAULT '[]',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_content_pieces_status ON content_pieces(status);
CREATE INDEX IF NOT EXISTS idx_content_pieces_creator ON content_pieces(creator_id);
CREATE INDEX IF NOT EXISTS idx_content_pieces_scheduled ON content_pieces(scheduled_at) WHERE scheduled_at IS NOT NULL;

CREATE TABLE IF NOT EXISTS content_calendar (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  target_date      DATE NOT NULL,
  creator_id       TEXT NOT NULL DEFAULT 'zenya',
  platform         TEXT NOT NULL DEFAULT 'instagram_reels',
  theme            TEXT,
  style            TEXT,
  content_piece_id UUID REFERENCES content_pieces(id),
  status           TEXT DEFAULT 'planned'
                   CHECK (status IN ('planned','in_production','done')),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_content_calendar_date ON content_calendar(target_date);
CREATE INDEX IF NOT EXISTS idx_content_calendar_creator ON content_calendar(creator_id);
