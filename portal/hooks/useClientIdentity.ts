'use client'

import { useEffect, useState, useCallback } from 'react'

// ── Types ──────────────────────────────────────────────────

export interface ClientIdentity {
  client: {
    id: string
    name: string
    company: string
    plan: string
    mrr: number
    hasZenya: boolean
    hasTrafego: boolean
    niche: string
    instagram: string | null
    website: string | null
  }
  dna: Record<string, string>
  brandColor: string | null
  zenya: {
    name: string
    slug: string
    avatar_url: string | null
    tagline: string | null
  } | null
  stats: {
    brainChunks: number
    conversationsToday: number
    resolvedToday: number
    conversationsMonth: number
  }
  expiresAt: string
}

export interface UseClientIdentityReturn {
  identity: ClientIdentity | null
  isLoading: boolean
  error: string | null
  /** Shortcut getters */
  clientName: string | null
  businessName: string | null
  plan: string | null
  zenyaName: string | null
  brandColor: string | null
  greeting: string
  refresh: () => Promise<void>
}

// ── Plan display labels ────────────────────────────────────

export const PLAN_LABELS: Record<string, string> = {
  zenya_basico: 'Zenya',
  zenya_premium: 'Zenya Premium',
  trafego: 'Trafego Pago',
  full: 'Full Service',
}

export function planLabel(plan: string | null): string {
  if (!plan) return 'Cliente'
  return PLAN_LABELS[plan] || plan
}

// ── Time-aware greeting ────────────────────────────────────

function getGreeting(): string {
  const hour = new Date().getHours()
  if (hour < 12) return 'Bom dia'
  if (hour < 18) return 'Boa tarde'
  return 'Boa noite'
}

// ── Hook ───────────────────────────────────────────────────

export function useClientIdentity(): UseClientIdentityReturn {
  const [identity, setIdentity] = useState<ClientIdentity | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchIdentity = useCallback(async () => {
    try {
      setIsLoading(true)
      setError(null)

      const res = await fetch('/api/client/identity')
      if (!res.ok) {
        if (res.status === 401) {
          setError('Sessão expirada')
          return
        }
        throw new Error(`HTTP ${res.status}`)
      }

      const data: ClientIdentity = await res.json()
      setIdentity(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao carregar dados')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchIdentity()
  }, [fetchIdentity])

  return {
    identity,
    isLoading,
    error,
    clientName: identity?.client.name ?? null,
    businessName: identity?.client.company ?? null,
    plan: identity?.client.plan ?? null,
    zenyaName: identity?.zenya?.name ?? null,
    brandColor: identity?.brandColor ?? null,
    greeting: `${getGreeting()}, ${identity?.client.company || identity?.client.name || ''}`,
    refresh: fetchIdentity,
  }
}
