-- Migration 012: Brain RPCs for P1-4 and P1-8 fixes
-- P1-4: brain_namespace_stats — server-side aggregation instead of full table scan
-- P1-8: increment_confirmation_count — atomic increment to avoid read-then-write race

-- ── P1-4: Namespace stats aggregation ──────────────────────────────────────

CREATE OR REPLACE FUNCTION brain_namespace_stats()
RETURNS TABLE(namespace text, chunk_count bigint, total_usage bigint, avg_usage numeric)
LANGUAGE sql STABLE
AS $$
  SELECT
    COALESCE(bc.namespace, 'general') AS namespace,
    COUNT(*) AS chunk_count,
    COALESCE(SUM(bc.usage_count), 0) AS total_usage,
    COALESCE(AVG(bc.usage_count), 0) AS avg_usage
  FROM brain_chunks bc
  GROUP BY COALESCE(bc.namespace, 'general')
  ORDER BY chunk_count DESC;
$$;

-- ── P1-8: Atomic confirmation count increment ─────────────────────────────

CREATE OR REPLACE FUNCTION increment_confirmation_count(p_table text, p_id uuid)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  EXECUTE format(
    'UPDATE %I SET confirmation_count = confirmation_count + 1, updated_at = now() WHERE id = $1',
    p_table
  )
  USING p_id;
END;
$$;
