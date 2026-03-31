-- Migration 002: RPC get_orion_session_context
-- Orion chama no início de toda sessão para obter estado real do sistema
-- sem depender da janela de contexto da conversa.
-- Aplicada em: 2026-03-31

CREATE OR REPLACE FUNCTION get_orion_session_context()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_tasks_summary jsonb;
  v_agents jsonb;
  v_cost_7d numeric;
  v_recent_tasks jsonb;
  v_pending_tasks jsonb;
BEGIN

  SELECT jsonb_object_agg(status, cnt)
  INTO v_tasks_summary
  FROM (
    SELECT status, COUNT(*) AS cnt
    FROM runtime_tasks
    WHERE created_at >= NOW() - INTERVAL '7 days'
    GROUP BY status
  ) s;

  SELECT jsonb_agg(jsonb_build_object(
    'agent_id', agent_id,
    'agent_type', agent_type,
    'display_name', display_name,
    'status', status,
    'last_heartbeat', last_heartbeat
  ) ORDER BY agent_id)
  INTO v_agents
  FROM agents;

  SELECT COALESCE(SUM(cost_usd), 0)
  INTO v_cost_7d
  FROM llm_cost_log
  WHERE created_at >= NOW() - INTERVAL '7 days';

  SELECT jsonb_agg(jsonb_build_object(
    'id', id,
    'task_type', task_type,
    'status', status,
    'agent_id', agent_id,
    'client_id', client_id,
    'created_at', created_at,
    'completed_at', completed_at,
    'error', error
  ) ORDER BY created_at DESC)
  INTO v_recent_tasks
  FROM (
    SELECT id, task_type, status, agent_id, client_id, created_at, completed_at, error
    FROM runtime_tasks
    ORDER BY created_at DESC
    LIMIT 10
  ) r;

  SELECT jsonb_agg(jsonb_build_object(
    'id', id,
    'task_type', task_type,
    'status', status,
    'agent_id', agent_id,
    'client_id', client_id,
    'created_at', created_at,
    'priority', priority
  ) ORDER BY priority DESC, created_at ASC)
  INTO v_pending_tasks
  FROM runtime_tasks
  WHERE status IN ('pending', 'running');

  RETURN jsonb_build_object(
    'generated_at', NOW(),
    'tasks_by_status_7d', COALESCE(v_tasks_summary, '{}'::jsonb),
    'agents', COALESCE(v_agents, '[]'::jsonb),
    'cost_usd_7d', v_cost_7d,
    'recent_tasks', COALESCE(v_recent_tasks, '[]'::jsonb),
    'pending_tasks', COALESCE(v_pending_tasks, '[]'::jsonb)
  );
END;
$$;

GRANT EXECUTE ON FUNCTION get_orion_session_context() TO anon, authenticated;
