-- ============================================================
-- Sparkle Runtime — Migration 005: Agent Taxonomy
-- ============================================================
-- Adds routing_rules, priority columns to agents table.
-- Expands agent_type to support the 5 core taxonomy types:
--   operational, specialist, character, orchestrator, observer
-- Updates existing rows to the new taxonomy.
-- Idempotent: safe to run multiple times.
-- ============================================================

-- 1. Add new columns (IF NOT EXISTS via DO block)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'agents' AND column_name = 'routing_rules'
    ) THEN
        ALTER TABLE agents ADD COLUMN routing_rules jsonb DEFAULT '{}';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'agents' AND column_name = 'priority'
    ) THEN
        ALTER TABLE agents ADD COLUMN priority integer DEFAULT 50;
    END IF;
END $$;

-- 2. Expand agent_type CHECK to include 'operational'
--    Drop and recreate to be safe (idempotent).
ALTER TABLE agents DROP CONSTRAINT IF EXISTS agents_agent_type_check;
ALTER TABLE agents ADD CONSTRAINT agents_agent_type_check
    CHECK (agent_type IN (
        'operational',   -- Day-to-day task execution (friday, brain, zenya)
        'specialist',    -- Domain expertise (analyst, dev, qa, devops, pm, po, trafego)
        'character',     -- IP entities with personality (zenya_*, finch)
        'orchestrator',  -- Coordination and routing (orion, system)
        'observer',      -- Monitoring and quality (observer, health_monitor)
        -- Legacy types kept for backward compatibility:
        'worker', 'interface', 'qa', 'utility'
    ));

-- 3. Index on agent_type for routing queries
CREATE INDEX IF NOT EXISTS idx_agents_agent_type ON agents(agent_type);

-- 4. Index on priority for routing ordering
CREATE INDEX IF NOT EXISTS idx_agents_priority ON agents(priority);

-- 5. Update existing agents to new taxonomy + set routing_rules and priority
-- friday: operational, high priority (handles Mauro's interface)
UPDATE agents SET
    agent_type = 'operational',
    priority = 10,
    routing_rules = '{"intents": ["whatsapp_message", "voice_command", "friday_direct"], "channels": ["whatsapp"]}'::jsonb,
    capabilities = ARRAY['voice_input', 'intent_classify', 'whatsapp_reply', 'audio_transcribe']
WHERE agent_id = 'friday';

-- brain: operational, medium priority
UPDATE agents SET
    agent_type = 'operational',
    priority = 30,
    routing_rules = '{"intents": ["ingest", "search", "embed", "canonicalize"], "channels": ["internal"]}'::jsonb,
    capabilities = ARRAY['ingest', 'embed', 'search', 'canonicalize', 'backfill']
WHERE agent_id = 'brain';

-- zenya: character (IP entity with personality)
UPDATE agents SET
    agent_type = 'character',
    priority = 20,
    routing_rules = '{"intents": ["customer_chat", "customer_support", "order_assist"], "channels": ["whatsapp", "web"]}'::jsonb,
    capabilities = ARRAY['customer_chat', 'kb_lookup', 'order_assist', 'personality_response']
WHERE agent_id = 'zenya';

-- character-runner: operational (generic runner for characters)
UPDATE agents SET
    agent_type = 'operational',
    priority = 25,
    routing_rules = '{"intents": ["character_invoke"], "channels": ["internal"]}'::jsonb,
    capabilities = ARRAY['character_invoke', 'soul_prompt_inject']
WHERE agent_id = 'character-runner';

-- orion: orchestrator, highest priority
UPDATE agents SET
    agent_type = 'orchestrator',
    priority = 1,
    routing_rules = '{"intents": ["orchestrate", "plan", "status", "handoff"], "channels": ["internal", "whatsapp"]}'::jsonb,
    capabilities = ARRAY['orchestrate', 'task_dispatch', 'status_report', 'agent_routing', 'plan_execution']
WHERE agent_id = 'orion';

-- system: orchestrator
UPDATE agents SET
    agent_type = 'orchestrator',
    priority = 5,
    routing_rules = '{"intents": ["handoff", "system_task", "brain_ingest"], "channels": ["internal"]}'::jsonb,
    capabilities = ARRAY['handoff', 'brain_ingest', 'orchestration', 'task_routing']
WHERE agent_id = 'system';

-- qa: specialist
UPDATE agents SET
    agent_type = 'specialist',
    priority = 40,
    routing_rules = '{"intents": ["test", "validate", "qa_gate", "go_live_check"], "channels": ["internal"]}'::jsonb,
    capabilities = ARRAY['scenario_test', 'go_live_gate', 'regression_test', 'edge_case_analysis']
WHERE agent_id = 'qa';

-- analyst: specialist
UPDATE agents SET
    agent_type = 'specialist',
    priority = 45,
    routing_rules = '{"intents": ["research", "analyze", "benchmark", "market_analysis"], "channels": ["internal"]}'::jsonb,
    capabilities = ARRAY['market_research', 'competitive_analysis', 'data_analysis', 'benchmark']
WHERE agent_id = 'analyst';

-- architect: specialist
UPDATE agents SET
    agent_type = 'specialist',
    priority = 40,
    routing_rules = '{"intents": ["architecture", "design_system", "tech_decision", "stack_choice"], "channels": ["internal"]}'::jsonb,
    capabilities = ARRAY['system_design', 'architecture_review', 'tech_decision', 'api_design']
WHERE agent_id = 'architect';

-- dev: specialist
UPDATE agents SET
    agent_type = 'specialist',
    priority = 35,
    routing_rules = '{"intents": ["implement", "code", "deploy", "debug", "fix"], "channels": ["internal"]}'::jsonb,
    capabilities = ARRAY['code_implementation', 'deploy', 'debug', 'infrastructure', 'api_development']
WHERE agent_id = 'dev';

-- pm: specialist
UPDATE agents SET
    agent_type = 'specialist',
    priority = 45,
    routing_rules = '{"intents": ["product_strategy", "requirements", "backlog", "roadmap"], "channels": ["internal"]}'::jsonb,
    capabilities = ARRAY['product_strategy', 'requirements', 'backlog_management', 'roadmap']
WHERE agent_id = 'pm';

-- po: specialist
UPDATE agents SET
    agent_type = 'specialist',
    priority = 45,
    routing_rules = '{"intents": ["acceptance", "story_validation", "priority_decision"], "channels": ["internal"]}'::jsonb,
    capabilities = ARRAY['acceptance_criteria', 'story_validation', 'priority_decision']
WHERE agent_id = 'po';

-- trafego: specialist
UPDATE agents SET
    agent_type = 'specialist',
    priority = 45,
    routing_rules = '{"intents": ["meta_ads", "google_ads", "campaign", "traffic_analysis"], "channels": ["internal"]}'::jsonb,
    capabilities = ARRAY['meta_ads', 'google_ads', 'campaign_management', 'traffic_analysis']
WHERE agent_id = 'trafego';
