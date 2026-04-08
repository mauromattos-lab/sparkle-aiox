-- W1-CONTENT-1: Add character_slug column to character_lore
-- Enables slug-based queries (more robust than UUID in multi-env setups)

ALTER TABLE character_lore ADD COLUMN IF NOT EXISTS character_slug TEXT;

-- Backfill from characters table
UPDATE character_lore cl
SET character_slug = c.slug
FROM characters c
WHERE cl.character_id = c.id
  AND cl.character_slug IS NULL;

-- Index for fast slug lookups
CREATE INDEX IF NOT EXISTS idx_character_lore_character_slug ON character_lore (character_slug);
