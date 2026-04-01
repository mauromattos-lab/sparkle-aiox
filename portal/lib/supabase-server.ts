// Supabase client com service_role key
// ATENÇÃO: usar APENAS em API routes (server-side). NUNCA importar em componentes 'use client'.
// SUPABASE_SERVICE_KEY NÃO tem prefixo NEXT_PUBLIC_ — nunca exposta ao browser.

import { createClient } from '@supabase/supabase-js'

export const supabaseServer = createClient(
  process.env.SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_KEY! // server-side only — não é NEXT_PUBLIC_
)
