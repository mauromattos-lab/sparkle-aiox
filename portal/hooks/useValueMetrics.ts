'use client'

import { useEffect, useState, useCallback } from 'react'

// ── Types ──────────────────────────────────────────────────

export interface ValueMetrics {
  conversations: {
    currentMonth: number
    currentResolved: number
    currentConverted: number
    previousMonth: number
    previousResolved: number
    growthPercent: number | null
  }
  brain: {
    totalChunks: number
    domainsCount: number
    domains: string[]
  }
  economy: {
    hoursSaved: number
    minutesSaved: number
    conversationsHandled: number
  }
  client: {
    hasZenya: boolean
    company: string
  }
  firstConvoDate: string | null
}

export interface ValueNarrativeStrings {
  /** "Zenya resolveu 847 conversas — 23% mais que o mês passado." */
  zenyaHeadline: string
  /** "142 conversas este mês" or similar */
  zenyaDetail: string
  /** Growth badge text: "+23%" or "Primeiro mês" */
  growthBadge: string | null
  /** "Seu Brain tem 1.250 chunks em 4 domínios" */
  brainHeadline: string
  brainDetail: string
  /** "Economia estimada de 12,5 horas este mês" */
  economyHeadline: string
  economyDetail: string
  /** Milestone badges */
  milestones: MilestoneBadge[]
}

export interface MilestoneBadge {
  id: string
  label: string
  icon: 'conversations' | 'brain' | 'economy'
  achieved: boolean
}

export interface UseValueMetricsReturn {
  metrics: ValueMetrics | null
  narrative: ValueNarrativeStrings | null
  isLoading: boolean
  error: string | null
  refresh: () => Promise<void>
}

// ── Milestone definitions ──────────────────────────────────

const MILESTONES = [
  { id: 'conv-100', threshold: 100, field: 'conversations' as const, label: '100 conversas resolvidas', icon: 'conversations' as const },
  { id: 'conv-500', threshold: 500, field: 'conversations' as const, label: '500 conversas resolvidas', icon: 'conversations' as const },
  { id: 'conv-1000', threshold: 1000, field: 'conversations' as const, label: '1.000 conversas resolvidas', icon: 'conversations' as const },
  { id: 'brain-500', threshold: 500, field: 'brain' as const, label: '500 chunks no Brain', icon: 'brain' as const },
  { id: 'brain-1000', threshold: 1000, field: 'brain' as const, label: '1.000 chunks no Brain', icon: 'brain' as const },
  { id: 'hours-50', threshold: 50, field: 'economy' as const, label: '50 horas economizadas', icon: 'economy' as const },
]

// ── Narrative builder ──────────────────────────────────────

function buildNarrative(m: ValueMetrics): ValueNarrativeStrings {
  // Zenya headline
  let zenyaHeadline: string
  if (m.conversations.currentResolved > 0) {
    const growthSuffix = m.conversations.growthPercent !== null && m.conversations.growthPercent > 0
      ? ` — ${m.conversations.growthPercent}% mais que o mês passado`
      : ''
    zenyaHeadline = `Zenya resolveu ${m.conversations.currentResolved.toLocaleString('pt-BR')} conversas${growthSuffix}.`
  } else {
    zenyaHeadline = 'Sua Zenya está pronta para atender.'
  }

  const zenyaDetail = m.conversations.currentMonth > 0
    ? `${m.conversations.currentMonth.toLocaleString('pt-BR')} conversas este mês, ${m.conversations.currentConverted} convertidas`
    : 'Nenhuma conversa registrada este mês ainda.'

  // Growth badge
  let growthBadge: string | null = null
  if (m.conversations.growthPercent !== null) {
    growthBadge = m.conversations.growthPercent >= 0
      ? `+${m.conversations.growthPercent}%`
      : `${m.conversations.growthPercent}%`
  } else if (m.conversations.currentMonth > 0 && m.conversations.previousMonth === 0) {
    growthBadge = 'Primeiro mês'
  }

  // Brain headline
  const brainHeadline = m.brain.totalChunks > 0
    ? `Seu Brain tem ${m.brain.totalChunks.toLocaleString('pt-BR')} chunks em ${m.brain.domainsCount} ${m.brain.domainsCount === 1 ? 'domínio' : 'domínios'}.`
    : 'Seu Brain está sendo preparado.'

  const domainNames: Record<string, string> = {
    website: 'Site',
    instagram: 'Instagram',
    faq: 'FAQ',
    catalog: 'Catálogo',
    manual: 'Manual',
    doc: 'Documento',
    pdf: 'PDF',
  }
  const brainDetail = m.brain.domains.length > 0
    ? `Fontes: ${m.brain.domains.map(d => domainNames[d] || d).join(', ')}`
    : 'Aguardando ingestão de dados.'

  // Economy headline
  const economyHeadline = m.economy.hoursSaved > 0
    ? `Economia estimada de ${m.economy.hoursSaved.toLocaleString('pt-BR')} horas este mês.`
    : 'Em breve você verá a economia gerada.'

  const economyDetail = m.economy.conversationsHandled > 0
    ? `${m.economy.conversationsHandled.toLocaleString('pt-BR')} atendimentos automatizados (~5 min cada)`
    : 'Baseado em tempo médio de atendimento humano.'

  // Milestones
  const milestones: MilestoneBadge[] = MILESTONES
    .map(ms => {
      let value = 0
      if (ms.field === 'conversations') value = m.conversations.currentResolved
      else if (ms.field === 'brain') value = m.brain.totalChunks
      else if (ms.field === 'economy') value = m.economy.hoursSaved
      return {
        id: ms.id,
        label: ms.label,
        icon: ms.icon,
        achieved: value >= ms.threshold,
      }
    })
    .filter(ms => ms.achieved)

  return {
    zenyaHeadline,
    zenyaDetail,
    growthBadge,
    brainHeadline,
    brainDetail,
    economyHeadline,
    economyDetail,
    milestones,
  }
}

// ── Hook ───────────────────────────────────────────────────

export function useValueMetrics(): UseValueMetricsReturn {
  const [metrics, setMetrics] = useState<ValueMetrics | null>(null)
  const [narrative, setNarrative] = useState<ValueNarrativeStrings | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchMetrics = useCallback(async () => {
    try {
      setIsLoading(true)
      setError(null)

      const res = await fetch('/api/metrics/value')
      if (!res.ok) {
        if (res.status === 401) {
          setError('Sessão expirada')
          return
        }
        throw new Error(`HTTP ${res.status}`)
      }

      const data: ValueMetrics = await res.json()
      setMetrics(data)
      setNarrative(buildNarrative(data))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao carregar métricas')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchMetrics()
  }, [fetchMetrics])

  return {
    metrics,
    narrative,
    isLoading,
    error,
    refresh: fetchMetrics,
  }
}
