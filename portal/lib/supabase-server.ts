// Supabase client com service_role key
// ATENÇÃO: usar APENAS em API routes (server-side). NUNCA importar em componentes 'use client'.
// SUPABASE_SERVICE_KEY NÃO tem prefixo NEXT_PUBLIC_ — nunca exposta ao browser.

import { createClient, SupabaseClient } from '@supabase/supabase-js'

let _client: SupabaseClient | null = null

export function getSupabaseServer(): SupabaseClient {
  if (!_client) {
    _client = createClient(
      process.env.SUPABASE_URL!,
      process.env.SUPABASE_SERVICE_KEY!
    )
  }
  return _client
}

// Alias para compatibilidade — chama lazy init
export const supabaseServer = new Proxy({} as SupabaseClient, {
  get(_target, prop) {
    return (getSupabaseServer() as any)[prop]
  },
})
