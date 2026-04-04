// GET /api/client/identity
// Returns enriched client identity: base info + DNA + Zenya character + quick stats
// Used by useClientIdentity hook for personalization across the portal

export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import { cookies } from 'next/headers'
import { supabaseServer } from '@/lib/supabase-server'

export async function GET(_req: NextRequest) {
  const token = cookies().get('sparkle_session')?.value
  if (!token) return NextResponse.json({ error: 'Não autenticado' }, { status: 401 })

  // Validate session
  const { data: session } = await supabaseServer
    .from('client_sessions')
    .select('client_id, expires_at')
    .eq('token', token)
    .eq('used', false)
    .gt('expires_at', new Date().toISOString())
    .single()

  if (!session) return NextResponse.json({ error: 'Sessão inválida' }, { status: 401 })

  const clientId = session.client_id

  // Fetch client, DNA, and stats in parallel
  const [
    { data: client },
    { data: dnaEntries },
    { count: brainChunks },
    { data: conversationsToday },
    { data: conversationsMonth },
  ] = await Promise.all([
    // Base client data
    supabaseServer
      .from('clients')
      .select('id, name, company, plan, mrr, due_day, has_zenya, has_trafego, niche, status, instagram, website')
      .eq('id', clientId)
      .single(),

    // Client DNA entries (tom, persona, diferenciais, etc.)
    supabaseServer
      .from('client_dna')
      .select('dna_type, title, content, key, confidence')
      .eq('client_id', clientId)
      .order('confidence', { ascending: false }),

    // Brain chunks count for this client
    supabaseServer
      .from('brain_chunks')
      .select('id', { count: 'exact', head: true })
      .eq('client_id', clientId),

    // Conversations today
    supabaseServer
      .from('zenya_conversations')
      .select('id, outcome')
      .eq('client_id', clientId)
      .gte('started_at', new Date(new Date().setHours(0, 0, 0, 0)).toISOString()),

    // Conversations this month
    supabaseServer
      .from('zenya_conversations')
      .select('id, outcome')
      .eq('client_id', clientId)
      .gte('started_at', new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString()),
  ])

  if (!client) return NextResponse.json({ error: 'Cliente não encontrado' }, { status: 404 })

  // Extract relevant DNA fields into a structured object
  const dna: Record<string, string> = {}
  if (dnaEntries) {
    for (const entry of dnaEntries) {
      const key = entry.key || entry.dna_type
      if (key && !dna[key]) {
        dna[key] = entry.content
      }
    }
  }

  // Build brand colors from DNA or use defaults based on niche
  const brandColor = dna['cor_primaria'] || dna['brand_color'] || null

  // Zenya info (global character, active for all clients with has_zenya)
  let zenya = null
  if (client.has_zenya) {
    const { data: zenyaChar } = await supabaseServer
      .from('characters')
      .select('name, slug, avatar_url, tagline')
      .eq('slug', 'zenya')
      .eq('active', true)
      .single()

    if (zenyaChar) {
      zenya = zenyaChar
    }
  }

  // Quick stats
  const todayTotal = conversationsToday?.length ?? 0
  const todayResolved = conversationsToday?.filter(
    (c: { outcome: string }) => c.outcome === 'atendido' || c.outcome === 'convertido'
  ).length ?? 0
  const monthTotal = conversationsMonth?.length ?? 0

  return NextResponse.json({
    client: {
      id: client.id,
      name: client.name,
      company: client.company,
      plan: client.plan,
      mrr: client.mrr,
      hasZenya: client.has_zenya,
      hasTrafego: client.has_trafego,
      niche: client.niche,
      instagram: client.instagram,
      website: client.website,
    },
    dna,
    brandColor,
    zenya,
    stats: {
      brainChunks: brainChunks ?? 0,
      conversationsToday: todayTotal,
      resolvedToday: todayResolved,
      conversationsMonth: monthTotal,
    },
    expiresAt: session.expires_at,
  })
}
