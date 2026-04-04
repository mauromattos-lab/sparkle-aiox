// GET /api/gamification
// Gamification metrics: Brain XP, Zenya Level, Achievements, Timeline
// Queries Supabase for brain_chunks, conversations, quality scores

export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import { cookies } from 'next/headers'
import { supabaseServer } from '@/lib/supabase-server'

// ── Level thresholds ──────────────────────────────────────────

const BRAIN_XP_PER_CHUNK = 10
const BRAIN_LEVELS = [
  { level: 1, xpRequired: 0 },
  { level: 2, xpRequired: 100 },
  { level: 3, xpRequired: 300 },
  { level: 4, xpRequired: 600 },
  { level: 5, xpRequired: 1000 },
  { level: 6, xpRequired: 2000 },
  { level: 7, xpRequired: 3500 },
  { level: 8, xpRequired: 5000 },
  { level: 9, xpRequired: 8000 },
  { level: 10, xpRequired: 12000 },
]

const ZENYA_LEVELS = [
  { level: 1, conversationsRequired: 0, stars: 1 },
  { level: 2, conversationsRequired: 25, stars: 1 },
  { level: 3, conversationsRequired: 75, stars: 2 },
  { level: 4, conversationsRequired: 150, stars: 2 },
  { level: 5, conversationsRequired: 300, stars: 3 },
  { level: 6, conversationsRequired: 500, stars: 3 },
  { level: 7, conversationsRequired: 1000, stars: 4 },
  { level: 8, conversationsRequired: 2000, stars: 4 },
  { level: 9, conversationsRequired: 3500, stars: 5 },
  { level: 10, conversationsRequired: 5000, stars: 5 },
]

// ── Achievement definitions ───────────────────────────────────

interface AchievementDef {
  id: string
  label: string
  description: string
  category: 'brain' | 'zenya' | 'quality' | 'milestone'
  check: (ctx: MetricsContext) => boolean
}

interface MetricsContext {
  brainChunks: number
  brainDomains: number
  totalConversations: number
  resolvedConversations: number
  convertedConversations: number
  currentMonthConversations: number
  currentMonthResolved: number
  hoursSaved: number
  avgSentiment: number | null
  daysActive: number
}

const ACHIEVEMENTS: AchievementDef[] = [
  {
    id: 'primeiro-faq',
    label: 'Primeiro FAQ',
    description: 'Adicionou o primeiro conteudo ao Brain',
    category: 'brain',
    check: (ctx) => ctx.brainChunks >= 1,
  },
  {
    id: 'brain-100',
    label: 'Brain Ativo',
    description: '100 chunks no Brain',
    category: 'brain',
    check: (ctx) => ctx.brainChunks >= 100,
  },
  {
    id: 'brain-500',
    label: 'Brain Expert',
    description: '500 chunks de conhecimento',
    category: 'brain',
    check: (ctx) => ctx.brainChunks >= 500,
  },
  {
    id: 'brain-master',
    label: 'Brain Master',
    description: '1.000+ chunks — base de conhecimento robusta',
    category: 'brain',
    check: (ctx) => ctx.brainChunks >= 1000,
  },
  {
    id: 'multi-dominio',
    label: 'Multi-Dominio',
    description: 'Brain com 3+ fontes de dados diferentes',
    category: 'brain',
    check: (ctx) => ctx.brainDomains >= 3,
  },
  {
    id: 'primeira-conversa',
    label: 'Primeira Conversa',
    description: 'Zenya atendeu o primeiro cliente',
    category: 'zenya',
    check: (ctx) => ctx.totalConversations >= 1,
  },
  {
    id: '100-conversas',
    label: '100 Conversas',
    description: 'Zenya resolveu 100 conversas',
    category: 'zenya',
    check: (ctx) => ctx.resolvedConversations >= 100,
  },
  {
    id: '500-conversas',
    label: '500 Conversas',
    description: 'Zenya ja resolveu 500 conversas',
    category: 'zenya',
    check: (ctx) => ctx.resolvedConversations >= 500,
  },
  {
    id: '1000-conversas',
    label: '1.000 Conversas',
    description: 'Marco de 1.000 conversas resolvidas',
    category: 'zenya',
    check: (ctx) => ctx.resolvedConversations >= 1000,
  },
  {
    id: 'conversor',
    label: 'Conversor',
    description: '10+ conversas convertidas em vendas',
    category: 'zenya',
    check: (ctx) => ctx.convertedConversations >= 10,
  },
  {
    id: 'economizador',
    label: 'Economizador',
    description: '50+ horas economizadas com automacao',
    category: 'milestone',
    check: (ctx) => ctx.hoursSaved >= 50,
  },
  {
    id: 'veterano',
    label: 'Veterano',
    description: '30+ dias usando a plataforma',
    category: 'milestone',
    check: (ctx) => ctx.daysActive >= 30,
  },
]

// ── Helpers ───────────────────────────────────────────────────

function computeBrainLevel(chunks: number) {
  const xp = chunks * BRAIN_XP_PER_CHUNK
  let current = BRAIN_LEVELS[0]
  let next = BRAIN_LEVELS[1]

  for (let i = BRAIN_LEVELS.length - 1; i >= 0; i--) {
    if (xp >= BRAIN_LEVELS[i].xpRequired) {
      current = BRAIN_LEVELS[i]
      next = BRAIN_LEVELS[i + 1] ?? BRAIN_LEVELS[i]
      break
    }
  }

  const xpInLevel = xp - current.xpRequired
  const xpForNext = next.xpRequired - current.xpRequired
  const progress = xpForNext > 0 ? Math.min(xpInLevel / xpForNext, 1) : 1

  return {
    level: current.level,
    xp,
    xpInLevel,
    xpForNext,
    progress,
    isMaxLevel: current.level === 10,
  }
}

function computeZenyaLevel(totalResolved: number) {
  let current = ZENYA_LEVELS[0]
  let next = ZENYA_LEVELS[1]

  for (let i = ZENYA_LEVELS.length - 1; i >= 0; i--) {
    if (totalResolved >= ZENYA_LEVELS[i].conversationsRequired) {
      current = ZENYA_LEVELS[i]
      next = ZENYA_LEVELS[i + 1] ?? ZENYA_LEVELS[i]
      break
    }
  }

  const inLevel = totalResolved - current.conversationsRequired
  const forNext = next.conversationsRequired - current.conversationsRequired
  const progress = forNext > 0 ? Math.min(inLevel / forNext, 1) : 1

  return {
    level: current.level,
    stars: current.stars,
    conversationsHandled: totalResolved,
    inLevel,
    forNext,
    progress,
    isMaxLevel: current.level === 10,
  }
}

// ── Route Handler ─────────────────────────────────────────────

export async function GET(_req: NextRequest) {
  const token = cookies().get('sparkle_session')?.value
  if (!token) return NextResponse.json({ error: 'Nao autenticado' }, { status: 401 })

  const { data: session } = await supabaseServer
    .from('client_sessions')
    .select('client_id, expires_at')
    .eq('token', token)
    .eq('used', false)
    .gt('expires_at', new Date().toISOString())
    .single()

  if (!session) return NextResponse.json({ error: 'Sessao invalida' }, { status: 401 })

  const clientId = session.client_id
  const now = new Date()
  const currentMonthStart = new Date(now.getFullYear(), now.getMonth(), 1)

  const [
    { count: brainChunksTotal },
    { data: brainDomains },
    { data: allConversations },
    { data: currentMonthConvos },
    { data: clientData },
  ] = await Promise.all([
    // Total brain chunks
    supabaseServer
      .from('brain_chunks')
      .select('id', { count: 'exact', head: true })
      .eq('client_id', clientId),

    // Brain domains
    supabaseServer
      .from('brain_chunks')
      .select('source_type')
      .eq('client_id', clientId),

    // All conversations (for total counts)
    supabaseServer
      .from('zenya_conversations')
      .select('id, outcome, sentiment, started_at')
      .eq('client_id', clientId)
      .order('started_at', { ascending: false }),

    // Current month conversations
    supabaseServer
      .from('zenya_conversations')
      .select('id, outcome, sentiment, started_at')
      .eq('client_id', clientId)
      .gte('started_at', currentMonthStart.toISOString()),

    // Client info
    supabaseServer
      .from('clients')
      .select('has_zenya, company, created_at')
      .eq('id', clientId)
      .single(),
  ])

  const chunks = brainChunksTotal ?? 0
  const uniqueDomains = new Set(
    (brainDomains ?? []).map((d: { source_type: string }) => d.source_type).filter(Boolean)
  )

  const totalConversations = allConversations?.length ?? 0
  const resolvedConversations = allConversations?.filter(
    (c: { outcome: string }) => c.outcome === 'atendido' || c.outcome === 'convertido'
  ).length ?? 0
  const convertedConversations = allConversations?.filter(
    (c: { outcome: string }) => c.outcome === 'convertido'
  ).length ?? 0

  const currentMonthTotal = currentMonthConvos?.length ?? 0
  const currentMonthResolved = currentMonthConvos?.filter(
    (c: { outcome: string }) => c.outcome === 'atendido' || c.outcome === 'convertido'
  ).length ?? 0

  // Average sentiment (1-5 scale from conversations that have it)
  const sentimentValues = (allConversations ?? [])
    .map((c: { sentiment: number | null }) => c.sentiment)
    .filter((s: number | null): s is number => s !== null && s > 0)
  const avgSentiment = sentimentValues.length > 0
    ? parseFloat((sentimentValues.reduce((a: number, b: number) => a + b, 0) / sentimentValues.length).toFixed(1))
    : null

  // Days active since client creation
  const createdAt = clientData?.created_at ? new Date(clientData.created_at) : now
  const daysActive = Math.floor((now.getTime() - createdAt.getTime()) / (1000 * 60 * 60 * 24))

  const hoursSaved = parseFloat((resolvedConversations * 5 / 60).toFixed(1))

  // Compute levels
  const brainLevel = computeBrainLevel(chunks)
  const zenyaLevel = computeZenyaLevel(resolvedConversations)

  // Compute achievements
  const ctx: MetricsContext = {
    brainChunks: chunks,
    brainDomains: uniqueDomains.size,
    totalConversations,
    resolvedConversations,
    convertedConversations,
    currentMonthConversations: currentMonthTotal,
    currentMonthResolved,
    hoursSaved,
    avgSentiment,
    daysActive,
  }

  const achievements = ACHIEVEMENTS.map((a) => ({
    id: a.id,
    label: a.label,
    description: a.description,
    category: a.category,
    unlocked: a.check(ctx),
  }))

  // Build timeline from recent notable events (last 10 conversations + brain growth)
  const timeline: Array<{
    id: string
    type: 'conversa' | 'brain' | 'conquista' | 'nivel'
    label: string
    detail: string
    timestamp: string
  }> = []

  // Recent conversations as timeline entries (last 5)
  const recentConvos = (allConversations ?? []).slice(0, 5)
  for (const c of recentConvos) {
    const conv = c as { id: string; outcome: string; started_at: string }
    const outcomeLabel = conv.outcome === 'convertido'
      ? 'Conversa convertida'
      : conv.outcome === 'atendido'
        ? 'Conversa resolvida'
        : 'Conversa registrada'
    timeline.push({
      id: `conv-${conv.id}`,
      type: 'conversa',
      label: outcomeLabel,
      detail: `Atendimento Zenya`,
      timestamp: conv.started_at,
    })
  }

  // Achievement unlocks as timeline milestones
  const unlockedAchievements = achievements.filter((a) => a.unlocked)
  for (const a of unlockedAchievements) {
    timeline.push({
      id: `ach-${a.id}`,
      type: 'conquista',
      label: a.label,
      detail: a.description,
      timestamp: now.toISOString(), // approximation
    })
  }

  // Sort timeline by timestamp descending, take 10
  timeline.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
  const timelineTrimmed = timeline.slice(0, 10)

  return NextResponse.json({
    brain: brainLevel,
    zenya: {
      ...zenyaLevel,
      hasZenya: clientData?.has_zenya ?? false,
      zenyaName: null, // Could be fetched from zenya_agents table
    },
    achievements,
    timeline: timelineTrimmed,
    stats: {
      brainChunks: chunks,
      brainDomains: uniqueDomains.size,
      totalConversations,
      resolvedConversations,
      convertedConversations,
      currentMonthConversations: currentMonthTotal,
      currentMonthResolved,
      hoursSaved,
      avgSentiment,
      daysActive,
    },
  })
}
