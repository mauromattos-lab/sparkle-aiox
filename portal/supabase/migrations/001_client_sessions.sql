-- Migration 001: Tabela de sessões por token (Portal do Cliente)
-- Sparkle AIOX | 2026-03-29
-- Executar via Supabase SQL Editor ou CLI: supabase db push

CREATE TABLE IF NOT EXISTS public.client_sessions (
  id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  client_id   UUID NOT NULL REFERENCES public.clients(id) ON DELETE CASCADE,
  token       TEXT NOT NULL UNIQUE,
  expires_at  TIMESTAMPTZ NOT NULL DEFAULT (now() + INTERVAL '30 minutes'),
  used        BOOLEAN DEFAULT false,
  created_at  TIMESTAMPTZ DEFAULT now(),
  ip_address  TEXT,   -- auditoria opcional
  user_agent  TEXT    -- auditoria opcional
);

-- Índices para performance (validação de token é hot path)
CREATE INDEX IF NOT EXISTS idx_client_sessions_token   ON public.client_sessions(token);
CREATE INDEX IF NOT EXISTS idx_client_sessions_expires ON public.client_sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_client_sessions_client  ON public.client_sessions(client_id);

-- RLS: apenas service_role acessa (API routes do Next.js usam SUPABASE_SERVICE_KEY)
-- anon key NUNCA deve ter acesso a esta tabela
ALTER TABLE public.client_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all_sessions"
  ON public.client_sessions
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- Limpeza de sessões antigas (rodar via pg_cron ou manualmente):
-- DELETE FROM public.client_sessions WHERE expires_at < now() - INTERVAL '1 day';
