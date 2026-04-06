-- Migration 002: Style Library (CONTENT-0.1)
-- Creates style_library table + ivfflat index for CLIP embeddings
-- Creates zenya-style-library Storage bucket with public read + upload policies

-- ── Extension ──────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS vector;

-- ── Table ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS style_library (
  id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  creator_id       TEXT        NOT NULL DEFAULT 'zenya',
  tier             TEXT        NOT NULL DEFAULT 'C'
                               CHECK (tier IN ('A', 'B', 'C')),
  storage_path     TEXT        NOT NULL,
  public_url       TEXT,
  embedding        vector(512),
  tags             TEXT[],
  style_type       TEXT,
  mauro_score      SMALLINT    NOT NULL DEFAULT 0,
  use_count        INTEGER     NOT NULL DEFAULT 0,
  embedding_status TEXT        NOT NULL DEFAULT 'pending'
                               CHECK (embedding_status IN ('pending', 'done', 'failed')),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Indexes ────────────────────────────────────────────────────────────────
-- ivfflat index for cosine similarity search (pgvector)
CREATE INDEX IF NOT EXISTS idx_style_library_embedding
  ON style_library USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 10);

CREATE INDEX IF NOT EXISTS idx_style_library_creator_tier
  ON style_library (creator_id, tier);

CREATE INDEX IF NOT EXISTS idx_style_library_embedding_status
  ON style_library (embedding_status);

-- ── Trigger: updated_at ────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_style_library_updated_at ON style_library;
CREATE TRIGGER set_style_library_updated_at
  BEFORE UPDATE ON style_library
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

-- ── Storage bucket ─────────────────────────────────────────────────────────
-- Note: bucket creation via SQL requires pg_catalog access.
-- If this fails, bucket was already created via Supabase Dashboard/MCP.
DO $$
BEGIN
  INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
  VALUES (
    'zenya-style-library',
    'zenya-style-library',
    true,
    52428800,  -- 50 MB
    ARRAY['image/jpeg','image/png','image/webp','image/gif','video/mp4']
  )
  ON CONFLICT (id) DO NOTHING;
EXCEPTION WHEN OTHERS THEN
  -- Bucket may not be accessible via SQL in this environment; skip.
  NULL;
END $$;

-- ── Storage policies ───────────────────────────────────────────────────────
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'objects'
      AND schemaname = 'storage'
      AND policyname = 'zenya-style-library public read'
  ) THEN
    CREATE POLICY "zenya-style-library public read"
      ON storage.objects FOR SELECT
      USING (bucket_id = 'zenya-style-library');
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'objects'
      AND schemaname = 'storage'
      AND policyname = 'zenya-style-library anon upload'
  ) THEN
    CREATE POLICY "zenya-style-library anon upload"
      ON storage.objects FOR INSERT
      TO anon
      WITH CHECK (bucket_id = 'zenya-style-library');
  END IF;
END $$;
