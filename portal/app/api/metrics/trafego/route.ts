export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import { cookies } from 'next/headers'
import { supabaseServer } from '@/lib/supabase-server'

export async function GET(_req: NextRequest) {
  const token = cookies().get('sparkle_session')?.value
  if (!token) return NextResponse.json({ error: 'Não autenticado' }, { status: 401 })

  const { data: session } = await supabaseServer
    .from('client_sessions')
    .select('client_id, expires_at')
    .eq('token', token)
    .eq('used', false)
    .gt('expires_at', new Date().toISOString())
    .single()

  if (!session) return NextResponse.json({ error: 'Sessão inválida' }, { status: 401 })

  const sete_dias = new Date()
  sete_dias.setDate(sete_dias.getDate() - 7)

  const { data } = await supabaseServer
    .from('meta_insights')
    .select('impressions, clicks, spend, leads, messages, ctr')
    .eq('client_id', session.client_id)
    .gte('date', sete_dias.toISOString().split('T')[0])

  const rows = data ?? []
  const investimento = rows.reduce((s, r) => s + Number(r.spend ?? 0), 0)
  const leads = rows.reduce((s, r) => s + Number(r.leads ?? 0), 0)
  const impressoes = rows.reduce((s, r) => s + Number(r.impressions ?? 0), 0)
  const cliques = rows.reduce((s, r) => s + Number(r.clicks ?? 0), 0)
  const ctr_medio = impressoes > 0 ? (cliques / impressoes) * 100 : 0

  return NextResponse.json({
    investimento_7d: investimento,
    leads_7d: leads,
    impressoes_7d: impressoes,
    ctr_medio: Math.round(ctr_medio * 100) / 100,
    cliques_7d: cliques,
  })
}
