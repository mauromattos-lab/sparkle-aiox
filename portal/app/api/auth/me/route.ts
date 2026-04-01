// GET /api/auth/me
// Retorna dados do cliente logado com base no cookie de sessão.
// Usado pelo dashboard para carregar os dados sem sessionStorage.

export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import { cookies } from 'next/headers'
import { supabaseServer } from '@/lib/supabase-server'

export async function GET(_req: NextRequest) {
  const cookieStore = cookies()
  const token = cookieStore.get('sparkle_session')?.value

  if (!token) {
    return NextResponse.json({ error: 'Não autenticado' }, { status: 401 })
  }

  // Verificar sessão válida no banco
  const { data: session, error: sessionError } = await supabaseServer
    .from('client_sessions')
    .select('client_id, expires_at')
    .eq('token', token)
    .eq('used', false)
    .gt('expires_at', new Date().toISOString())
    .single()

  if (sessionError || !session) {
    return NextResponse.json({ error: 'Sessão inválida ou expirada' }, { status: 401 })
  }

  // Buscar dados do cliente (campos mínimos necessários para o dashboard)
  const { data: client, error: clientError } = await supabaseServer
    .from('clients')
    .select('id, name, company, plan, mrr, due_day, has_zenya, has_trafego, status')
    .eq('id', session.client_id)
    .single()

  if (clientError || !client) {
    return NextResponse.json({ error: 'Cliente não encontrado' }, { status: 404 })
  }

  return NextResponse.json({ client, expiresAt: session.expires_at })
}
