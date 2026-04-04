-- B3-05: Brain Advanced — Namespaces, TTL/Archival, Usage Metrics
-- Adds namespace grouping, expiration/archival, and usage tracking to brain_chunks.

-- 1. Add new columns to brain_chunks (idempotent via IF NOT EXISTS workaround)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'brain_chunks' AND column_name = 'namespace'
    ) THEN
        ALTER TABLE brain_chunks ADD COLUMN namespace text DEFAULT 'general';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'brain_chunks' AND column_name = 'expires_at'
    ) THEN
        ALTER TABLE brain_chunks ADD COLUMN expires_at timestamptz;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'brain_chunks' AND column_name = 'usage_count'
    ) THEN
        ALTER TABLE brain_chunks ADD COLUMN usage_count integer DEFAULT 0;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'brain_chunks' AND column_name = 'last_used_at'
    ) THEN
        ALTER TABLE brain_chunks ADD COLUMN last_used_at timestamptz;
    END IF;
END $$;

-- 2. Indexes for new columns
CREATE INDEX IF NOT EXISTS idx_brain_chunks_namespace
    ON brain_chunks (namespace);

CREATE INDEX IF NOT EXISTS idx_brain_chunks_expires_at
    ON brain_chunks (expires_at)
    WHERE expires_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_brain_chunks_usage_count
    ON brain_chunks (usage_count DESC);

CREATE INDEX IF NOT EXISTS idx_brain_chunks_last_used_at
    ON brain_chunks (last_used_at DESC NULLS LAST);

-- 3. Archive table (mirrors brain_chunks structure + archived_at)
CREATE TABLE IF NOT EXISTS brain_chunks_archive (
    id                  uuid PRIMARY KEY,
    raw_content         text,
    source_type         text,
    source_title        text,
    pipeline_type       text,
    brain_owner         text,
    client_id           text,
    embedding           vector(1536),
    chunk_metadata      jsonb,
    curation_status     text,
    confirmation_count  integer DEFAULT 0,
    namespace           text DEFAULT 'general',
    expires_at          timestamptz,
    usage_count         integer DEFAULT 0,
    last_used_at        timestamptz,
    created_at          timestamptz,
    archived_at         timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_brain_chunks_archive_namespace
    ON brain_chunks_archive (namespace);

CREATE INDEX IF NOT EXISTS idx_brain_chunks_archive_archived_at
    ON brain_chunks_archive (archived_at DESC);

CREATE INDEX IF NOT EXISTS idx_brain_chunks_archive_brain_owner
    ON brain_chunks_archive (brain_owner);
