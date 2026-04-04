-- B2-04: Evolve client_dna schema for granular DNA extraction
-- Add missing columns, update types, add check constraint for dna_type categories

-- Add 'key' column for granular item identification within a dna_type
ALTER TABLE client_dna ADD COLUMN IF NOT EXISTS key text;

-- Add 'extracted_at' to track when extraction happened (distinct from created_at)
ALTER TABLE client_dna ADD COLUMN IF NOT EXISTS extracted_at timestamptz DEFAULT now();

-- Change source_chunk_ids from text[] to uuid[] (if currently text[])
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'client_dna'
      AND column_name = 'source_chunk_ids'
      AND udt_name = '_text'
  ) THEN
    ALTER TABLE client_dna ADD COLUMN source_chunk_ids_new uuid[] DEFAULT '{}';
    BEGIN
      UPDATE client_dna SET source_chunk_ids_new = source_chunk_ids::uuid[]
      WHERE source_chunk_ids IS NOT NULL AND array_length(source_chunk_ids, 1) > 0;
    EXCEPTION WHEN OTHERS THEN
      NULL;
    END;
    ALTER TABLE client_dna DROP COLUMN source_chunk_ids;
    ALTER TABLE client_dna RENAME COLUMN source_chunk_ids_new TO source_chunk_ids;
  END IF;
END $$;

-- Add check constraint for the 8 dna_type categories
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'client_dna_type_check'
  ) THEN
    ALTER TABLE client_dna DROP CONSTRAINT client_dna_type_check;
  END IF;
END $$;

ALTER TABLE client_dna ADD CONSTRAINT client_dna_type_check
  CHECK (dna_type IN (
    'tom', 'persona', 'regras', 'diferenciais', 'publico_alvo',
    'produtos', 'objecoes', 'faq',
    -- Backward compat with old 6-layer types
    'identidade', 'tom_voz', 'regras_negocio', 'anti_patterns'
  ));

-- Composite index on (client_id, dna_type, key) for fast lookups
CREATE INDEX IF NOT EXISTS idx_client_dna_client_type_key
  ON client_dna (client_id, dna_type, key);
