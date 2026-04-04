// GET /api/metrics/value
// Aggregated value metrics for the Value Narrative component.
// Returns: conversations (current + previous month), brain chunks by domain, timestamps.

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

  // Date ranges
  const now = new Date()
  const currentMonthStart = new Date(now.getFullYear(), now.getMonth(), 1)
  const previousMonthStart = new Date(now.getFullYear(), now.getMonth() - 1, 1)
  const previousMonthEnd = new Date(now.getFullYear(), now.getMonth(), 0, 23, 59, 59)

  const [
    { data: currentMonthConvos },
    { data: previousMonthConvos },
    { count: brainChunksTotal },
    { data: brainDomains },
    { data: clientData },
  ] = await Promise.all([
    // Current month conversations
    supabaseServer
      .from('zenya_conversations')
      .select('id, outcome, sentiment, started_at')
      .eq('client_id', clientId)
      .gte('started_at', currentMonthStart.toISOString()),

    // Previous month conversations
    supabaseServer
      .from('zenya_conversations')
      .select('id, outcome')
      .eq('client_id', clientId)
      .gte('started_at', previousMonthStart.toISOString())
      .lte('started_at', previousMonthEnd.toISOString()),

    // Total brain chunks
    supabaseServer
      .from('brain_chunks')
      .select('id', { count: 'exact', head: true })
      .eq('client_id', clientId),

    // Brain domains (distinct source types)
    supabaseServer
      .from('brain_chunks')
      .select('source_type')
      .eq('client_id', clientId),

    // Client info for Zenya name
    supabaseServer
      .from('clients')
      .select('has_zenya, company')
      .eq('id', clientId)
      .single(),
  ])

  // Conversations metrics
  const currentTotal = currentMonthConvos?.length ?? 0
  const currentResolved = currentMonthConvos?.filter(
    (c: { outcome: string }) => c.outcome === 'atendido' || c.outcome === 'convertido'
  ).length ?? 0
  const currentConverted = currentMonthConvos?.filter(
    (c: { outcome: string }) => c.outcome === 'convertido'
  ).length ?? 0
  const previousTotal = previousMonthConvos?.length ?? 0
  const previousResolved = previousMonthConvos?.filter(
    (c: { outcome: string }) => c.outcome === 'atendido' || c.outcome === 'convertido'
  ).length ?? 0

  // Growth percentage (resolved conversations)
  let growthPercent: number | null = null
  if (previousResolved > 0) {
    growthPercent = Math.round(((currentResolved - previousResolved) / previousResolved) * 100)
  }

  // Brain domains count (unique source_type values)
  const uniqueDomains = new Set(
    (brainDomains ?? []).map((d: { source_type: string }) => d.source_type).filter(Boolean)
  )

  // Estimated hours saved: each conversation ~ 5 min average handling time
  const minutesSaved = currentResolved * 5
  const hoursSaved = parseFloat((minutesSaved / 60).toFixed(1))

  // First conversation date for "time working" narrative
  const firstConvoDate = currentMonthConvos?.[currentMonthConvos.length - 1]?.started_at ?? null

  return NextResponse.json({
    conversations: {
      currentMonth: currentTotal,
      currentResolved,
      currentConverted,
      previousMonth: previousTotal,
      previousResolved,
      growthPercent,
    },
    brain: {
      totalChunks: brainChunksTotal ?? 0,
      domainsCount: uniqueDomains.size,
      domains: Array.from(uniqueDomains),
    },
    economy: {
      hoursSaved,
      minutesSaved,
      conversationsHandled: currentResolved,
    },
    client: {
      hasZenya: clientData?.has_zenya ?? false,
      company: clientData?.company ?? '',
    },
    firstConvoDate,
  })
}
