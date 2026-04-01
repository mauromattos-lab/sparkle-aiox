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

  const clientId = session.client_id
  const mesInicio = new Date()
  mesInicio.setDate(1)
  mesInicio.setHours(0, 0, 0, 0)

  const hojeInicio = new Date()
  hojeInicio.setHours(0, 0, 0, 0)

  const [{ data: mes }, { data: hoje }] = await Promise.all([
    supabaseServer
      .from('zenya_conversations')
      .select('outcome, sentiment, escalated_to_human')
      .eq('client_id', clientId)
      .gte('started_at', mesInicio.toISOString()),
    supabaseServer
      .from('zenya_conversations')
      .select('id')
      .eq('client_id', clientId)
      .gte('started_at', hojeInicio.toISOString()),
  ])

  const total_mes = mes?.length ?? 0
  const hoje_total = hoje?.length ?? 0
  const resolvidos = mes?.filter(c => c.outcome === 'atendido' || c.outcome === 'convertido').length ?? 0
  const conversoes = mes?.filter(c => c.outcome === 'convertido').length ?? 0
  const escalados = mes?.filter(c => c.escalated_to_human).length ?? 0
  const taxa_resolucao = total_mes > 0 ? Math.round((resolvidos / total_mes) * 100) : 0
  const positivos = mes?.filter(c => c.sentiment === 'positivo').length ?? 0
  const satisfacao = total_mes > 0 ? Math.round((positivos / total_mes) * 100) : 0

  return NextResponse.json({
    total_mes,
    hoje: hoje_total,
    taxa_resolucao,
    conversoes,
    escalados,
    satisfacao,
  })
}
