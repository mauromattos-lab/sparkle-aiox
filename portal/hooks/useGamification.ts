'use client'

import { useEffect, useState, useCallback } from 'react'

// ── Types ──────────────────────────────────────────────────

export interface BrainLevel {
  level: number
  xp: number
  xpInLevel: number
  xpForNext: number
  progress: number
  isMaxLevel: boolean
}

export interface ZenyaLevel {
  level: number
  stars: number
  conversationsHandled: number
  inLevel: number
  forNext: number
  progress: number
  isMaxLevel: boolean
  hasZenya: boolean
  zenyaName: string | null
}

export interface Achievement {
  id: string
  label: string
  description: string
  category: 'brain' | 'zenya' | 'quality' | 'milestone'
  unlocked: boolean
}

export interface TimelineEntry {
  id: string
  type: 'conversa' | 'brain' | 'conquista' | 'nivel'
  label: string
  detail: string
  timestamp: string
}

export interface GamificationStats {
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

export interface GamificationData {
  brain: BrainLevel
  zenya: ZenyaLevel
  achievements: Achievement[]
  timeline: TimelineEntry[]
  stats: GamificationStats
}

export interface UseGamificationReturn {
  data: GamificationData | null
  isLoading: boolean
  error: string | null
  refresh: () => Promise<void>
  /** Computed helpers */
  brainLevel: BrainLevel | null
  zenyaLevel: ZenyaLevel | null
  unlockedAchievements: Achievement[]
  lockedAchievements: Achievement[]
  unlockedCount: number
  totalAchievements: number
}

// ── Hook ───────────────────────────────────────────────────

export function useGamification(): UseGamificationReturn {
  const [data, setData] = useState<GamificationData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchGamification = useCallback(async () => {
    try {
      setIsLoading(true)
      setError(null)

      const res = await fetch('/api/gamification')
      if (!res.ok) {
        if (res.status === 401) {
          setError('Sessao expirada')
          return
        }
        throw new Error(`HTTP ${res.status}`)
      }

      const json: GamificationData = await res.json()
      setData(json)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao carregar gamificacao')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchGamification()
  }, [fetchGamification])

  const unlockedAchievements = data?.achievements.filter((a) => a.unlocked) ?? []
  const lockedAchievements = data?.achievements.filter((a) => !a.unlocked) ?? []

  return {
    data,
    isLoading,
    error,
    refresh: fetchGamification,
    brainLevel: data?.brain ?? null,
    zenyaLevel: data?.zenya ?? null,
    unlockedAchievements,
    lockedAchievements,
    unlockedCount: unlockedAchievements.length,
    totalAchievements: data?.achievements.length ?? 0,
  }
}
