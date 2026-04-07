-- Migration 015 — Content Pieces Resilience (CONTENT-2.2)
-- Adds retry_count, failed_permanent, error_reason columns to content_pieces
-- and a partial index for efficient stuck-piece detection.

ALTER TABLE content_pieces
    ADD COLUMN IF NOT EXISTS retry_count      INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS failed_permanent BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS error_reason     TEXT;

CREATE INDEX IF NOT EXISTS idx_content_pieces_stuck
    ON content_pieces (status, updated_at)
    WHERE failed_permanent = FALSE;

COMMENT ON COLUMN content_pieces.retry_count IS
    'Número de tentativas de retry automático por timeout. Max 3.';
COMMENT ON COLUMN content_pieces.failed_permanent IS
    'TRUE quando retry_count >= 3. Piece não será reprocessada automaticamente.';
COMMENT ON COLUMN content_pieces.error_reason IS
    'Causa técnica da falha (timeout_auto_retry, max_retries_exceeded, etc.)';
