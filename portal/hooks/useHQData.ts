'use client'

/**
 * SWR hooks for HQ Command Center data.
 * AC4, AC5, AC6: useOverview, useActivity, usePulse
 *
 * Common config:
 * - refreshInterval: 30000 (30s polling)
 * - revalidateOnFocus: false (prevents burst on window switch)
 * - dedupingInterval: 10000 (dedup within 10s window)
 */

import useSWR from 'swr'

// ── Types ────────────────────────────────────────────────────────────────────

export interface OverviewData {
  mrr?: number
  client_count?: number
  tasks_24h?: {
    total: number
    done: number
    failed: number
  }
  brain?: {
    pending: number
    approved: number
    review: number
    rejected: number
  }
  [key: string]: unknown
}

export interface ActivityEvent {
  id?: string
  event_type: string
  description: string
  timestamp: string
  agent?: string
  entity_id?: string
  entity_type?: string
  payload?: Record<string, unknown>
}

export interface ActivityData {
  events?: ActivityEvent[]
  [key: string]: unknown
}

export interface PulseData {
  agents?: {
    total: number
    active: number
    idle: number
    error: number
  }
  brain?: {
    status: string
  }
  workflows?: {
    running: number
  }
  clients?: {
    total: number
    healthy: number
    warning: number
    critical: number
  }
  pipeline?: {
    total: number
    [key: string]: unknown
  }
  checks?: {
    supabase?: boolean
    zapi_connected?: boolean
    zapi_configured?: boolean
    groq?: boolean
    anthropic?: boolean
    openai?: boolean
  }
  [key: string]: unknown
}

// ── Shared fetcher ────────────────────────────────────────────────────────────

const fetcher = (url: string) =>
  fetch(url).then((r) => {
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
    return r.json()
  })

const SWR_CONFIG = {
  refreshInterval: 30000,
  revalidateOnFocus: false,
  dedupingInterval: 10000,
} as const

// ── Hooks ─────────────────────────────────────────────────────────────────────

/** Overview KPIs: MRR, client_count, tasks_24h, brain stats */
export function useOverview() {
  return useSWR<OverviewData>('/api/hq/overview', fetcher, SWR_CONFIG)
}

/** Activity feed: last 50 runtime events */
export function useActivity() {
  return useSWR<ActivityData>('/api/hq/activity', fetcher, SWR_CONFIG)
}

/** System pulse: agents, brain, workflows, clients health */
export function usePulse() {
  return useSWR<PulseData>('/api/hq/pulse', fetcher, SWR_CONFIG)
}

// ── Clients & Pipeline types (Story 1.4) ─────────────────────────────────────

export interface ClientRecord {
  id: string
  name: string
  health_status: 'green' | 'yellow' | 'red'
  mrr?: number
  plan?: string
  last_interaction?: string
  notes?: string
  empresa?: string
  service_type?: string
  onboarding_status?: string
  zenya_active?: boolean
  health_reason?: string
  [key: string]: unknown
}

export interface ClientsData {
  clients?: ClientRecord[]
  [key: string]: unknown
}

export interface PipelineLead {
  id: string
  name: string
  stage?: string
  follow_up_date?: string
  notes?: string
  phone?: string
  source?: string
  empresa?: string
  bant_score?: string | number
  last_contact?: string
  created_at?: string
  updated_at?: string
  [key: string]: unknown
}

export interface PipelineData {
  leads?: PipelineLead[]
  [key: string]: unknown
}

// ── Hooks (Story 1.4) ───────────────────────────────────────────────────────

/** Client list with health status */
export function useClients() {
  return useSWR<ClientsData>('/api/hq/clients', fetcher, SWR_CONFIG)
}

/** Sales pipeline / leads */
export function usePipeline() {
  return useSWR<PipelineData>('/api/hq/pipeline', fetcher, SWR_CONFIG)
}
