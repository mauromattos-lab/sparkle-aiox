'use client'

/**
 * SWR hooks for HQ Command Center data.
 * AC4, AC5, AC6: useOverview, useActivity, usePulse
 * Story 3.2: useWorkflowRuns, useAgentWorkItems
 *
 * Common config:
 * - refreshInterval: 30000 (30s polling)
 * - revalidateOnFocus: false (prevents burst on window switch)
 * - dedupingInterval: 10000 (dedup within 10s window)
 */

import useSWR from 'swr'
import { supabase } from '@/lib/supabase'

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

// ── Workflow Runs & Agent Work Items (Story 3.2) ──────────────────────────────

export interface WorkflowRun {
  id: string
  workflow_type: string
  current_step: string
  total_steps: number
  status: 'running' | 'completed' | 'failed' | 'pending'
  context?: Record<string, unknown>
  agent_id?: string
  created_at: string
  updated_at?: string
  completed_at?: string
}

export interface AgentWorkItem {
  id: string
  sprint_item: string
  status: 'todo' | 'in_progress' | 'done' | 'blocked'
  handoff_to?: string
  notes?: string
  verified?: boolean
  verification_source?: string
  created_at: string
  updated_at?: string
}

export interface WorkflowRunsOptions {
  statusFilter?: string
  periodDays?: number
}

/** Workflow runs with optional status/period filters — AC1 */
export function useWorkflowRuns(options?: WorkflowRunsOptions) {
  const { statusFilter, periodDays } = options ?? {}
  const key = `workflow_runs:${statusFilter ?? 'all'}:${periodDays ?? 'all'}`

  return useSWR<WorkflowRun[]>(
    key,
    async () => {
      let query = supabase
        .from('workflow_runs')
        .select('*')
        .order('created_at', { ascending: false })
        .limit(100)

      if (statusFilter && statusFilter !== 'all') {
        query = query.eq('status', statusFilter)
      }
      if (periodDays) {
        const since = new Date(
          Date.now() - periodDays * 24 * 60 * 60 * 1000
        ).toISOString()
        query = query.gte('created_at', since)
      }

      const { data, error } = await query
      if (error) throw error
      return (data as WorkflowRun[]) ?? []
    },
    {
      refreshInterval: 30000,
      revalidateOnFocus: false,
      dedupingInterval: 10000,
    }
  )
}

/** Agent work items (sprint kanban) — AC2 */
export function useAgentWorkItems() {
  return useSWR<AgentWorkItem[]>(
    'agent_work_items',
    async () => {
      const { data, error } = await supabase
        .from('agent_work_items')
        .select('*')
        .order('created_at', { ascending: false })
      if (error) throw error
      return (data as AgentWorkItem[]) ?? []
    },
    {
      refreshInterval: 30000,
      revalidateOnFocus: false,
      dedupingInterval: 10000,
    }
  )
}

// ── Agents types (Story 3.1) ─────────────────────────────────────────────────

export interface AgentRecord {
  agent_id: string
  display_name: string
  agent_type: string
  model?: string
  status: 'working' | 'idle' | 'error'
  capabilities_count?: number
  capabilities?: string[]
  recent_tasks?: Array<{
    type: string
    status: string
    timestamp: string
  }>
  last_task?: {
    type: string
    status: string
    timestamp: string
  }
  // enriched from pulse
  last_action?: string
  last_action_at?: string
}

// ── Hooks (Story 3.1) ────────────────────────────────────────────────────────

/** Agent list with status, capabilities, last_task */
export function useAgents() {
  const { data, error, isLoading } = useSWR<AgentRecord[]>('/api/hq/agents', fetcher, SWR_CONFIG)
  return { agents: data ?? [], error, isLoading }
}

// ── Brain types (Story 3.3) ───────────────────────────────────────────────────

export interface BrainStats {
  pending: number
  approved: number
  review: number
  rejected: number
  total: number
}

export interface BrainNamespaceStat {
  namespace: string
  total: number
  approved: number
  pending: number
  rejected: number
  review: number
}

export interface BrainChunk {
  id: string
  brain_owner: string
  raw_content?: string
  canonical_content?: string
  curation_status: 'pending' | 'approved' | 'rejected' | 'review'
  source_url?: string
  source_type?: string
  source_title?: string
  curation_note?: string
  created_at: string
}

// ── Hooks (Story 3.3) ────────────────────────────────────────────────────────

/**
 * useBrainStats — derives brain KPI data from useOverview() (no extra network call).
 * AC1: extracts brain.pending/approved/review/rejected from overview and sums total.
 */
export function useBrainStats(): { stats: BrainStats; isLoading: boolean } {
  const { data, isLoading } = useOverview()
  const brain = data?.brain
  const pending = brain?.pending ?? 0
  const approved = brain?.approved ?? 0
  const review = brain?.review ?? 0
  const rejected = brain?.rejected ?? 0
  return {
    stats: {
      pending,
      approved,
      review,
      rejected,
      total: pending + approved + review + rejected,
    },
    isLoading,
  }
}

/**
 * useBrainChunks — fetches brain_chunks via Supabase RPC for namespace stats,
 * and raw query for recent ingestions.
 *
 * Strategy used: RPC get_brain_namespace_stats() for grouped stats (server-side GROUP BY),
 * with client-side fallback (fetch 500 + reduce) if RPC fails.
 * Ingestions: direct SELECT last 100 rows within 7 days.
 *
 * AC2: refreshInterval 30s. Graceful empty array on error/missing table.
 */
export function useBrainChunks() {
  const { data: nsData, isLoading: nsLoading } = useSWR<BrainNamespaceStat[]>(
    'brain_namespace_stats',
    async () => {
      // Try RPC first
      const { data: rpcData, error: rpcError } = await supabase.rpc('get_brain_namespace_stats')
      if (!rpcError && rpcData) {
        return (rpcData as BrainNamespaceStat[]).map((row) => ({
          namespace: row.namespace ?? 'unknown',
          total: Number(row.total) || 0,
          approved: Number(row.approved) || 0,
          pending: Number(row.pending) || 0,
          rejected: Number(row.rejected) || 0,
          review: Number(row.review) || 0,
        }))
      }
      // Fallback: fetch 500 and reduce client-side
      const { data: fallbackData, error: fallbackError } = await supabase
        .from('brain_chunks')
        .select('brain_owner, curation_status')
        .limit(500)
      if (fallbackError || !fallbackData) return []
      const acc: Record<string, BrainNamespaceStat> = {}
      for (const row of fallbackData as { brain_owner: string; curation_status: string }[]) {
        const ns = row.brain_owner ?? 'unknown'
        const st = row.curation_status ?? 'pending'
        if (!acc[ns]) acc[ns] = { namespace: ns, total: 0, approved: 0, pending: 0, rejected: 0, review: 0 }
        acc[ns].total++
        if (st === 'approved') acc[ns].approved++
        else if (st === 'pending') acc[ns].pending++
        else if (st === 'rejected') acc[ns].rejected++
        else if (st === 'review') acc[ns].review++
      }
      return Object.values(acc)
    },
    { refreshInterval: 30000, revalidateOnFocus: false, dedupingInterval: 10000 }
  )

  const { data: chunksData, isLoading: chunksLoading } = useSWR<BrainChunk[]>(
    'brain_chunks_recent',
    async () => {
      const since = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString()
      const { data, error } = await supabase
        .from('brain_chunks')
        .select('id, brain_owner, raw_content, canonical_content, curation_status, source_url, source_type, source_title, curation_note, created_at')
        .gte('created_at', since)
        .order('created_at', { ascending: false })
        .limit(20)
      if (error) return []
      return (data ?? []) as BrainChunk[]
    },
    { refreshInterval: 30000, revalidateOnFocus: false, dedupingInterval: 10000 }
  )

  return {
    namespaceStats: (nsData ?? []).sort((a, b) => b.total - a.total),
    chunks: chunksData ?? [],
    isLoading: nsLoading || chunksLoading,
  }
}
