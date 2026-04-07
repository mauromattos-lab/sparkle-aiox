-- W0-BRAIN-1: Soft-delete para brain_chunks
-- Campo deleted_at para política de retenção de chunks rejeitados (30 dias)
ALTER TABLE brain_chunks ADD COLUMN IF NOT EXISTS deleted_at timestamptz DEFAULT NULL;

-- Index para filtrar chunks não-deletados (hot path de retrieval)
CREATE INDEX IF NOT EXISTS idx_brain_chunks_deleted_at
    ON brain_chunks (deleted_at)
    WHERE deleted_at IS NULL;

COMMENT ON COLUMN brain_chunks.deleted_at IS
    'Soft-delete: chunks rejeitados há >30 dias recebem deleted_at. Excluídos de todas as queries de retrieval.';
