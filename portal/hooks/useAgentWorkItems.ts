import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import { RealtimeChannel } from '@supabase/supabase-js'

export type AgentStatus = 'idle' | 'active' | 'blocked' | 'done' | 'error'

export interface AgentWorkItem {
  id: string
  output_type: string | null
  artifact_id: string | null
  status: string | null
  assigned_to: string | null
  created_by: string | null
  created_at: string | null
  completed_at: string | null
  notes: string | null
}

export interface AgentView {
  agentId: string          // ex: '@dev', '@qa'
  status: AgentStatus
  currentItem: AgentWorkItem | null
  itemsLast24h: AgentWorkItem[]
  timeInCurrentStatus: number  // segundos desde ultima mudanca de status
}

// Mapeamento de status do banco para status do AgentCard
const STATUS_MAP: Record<string, AgentStatus> = {
  'pendente':       'idle',
  'em_execucao':    'active',
  'aguardando_qa':  'blocked',
  'aprovado_qa':    'done',
  'funcional':      'done',
  'erro':           'error',
  'blocked':        'blocked',
}

function mapStatus(rawStatus: string | null): AgentStatus {
  if (!rawStatus) return 'idle'
  return STATUS_MAP[rawStatus.toLowerCase()] ?? 'idle'
}

function buildAgentViews(items: AgentWorkItem[]): AgentView[] {
  const now = Date.now()
  const byAgent = new Map<string, AgentWorkItem[]>()

  for (const item of items) {
    const agent = item.assigned_to ?? 'unknown'
    if (!byAgent.has(agent)) byAgent.set(agent, [])
    byAgent.get(agent)!.push(item)
  }

  return Array.from(byAgent.entries()).map(([agentId, agentItems]) => {
    // Item mais recente como "current"
    const sorted = [...agentItems].sort(
      (a, b) => new Date(b.created_at ?? 0).getTime() - new Date(a.created_at ?? 0).getTime()
    )
    const current = sorted[0] ?? null
    const status = mapStatus(current?.status)
    const createdAt = current?.created_at ? new Date(current.created_at).getTime() : now
    const timeInStatus = Math.floor((now - createdAt) / 1000)

    return {
      agentId,
      status,
      currentItem: current,
      itemsLast24h: agentItems,
      timeInCurrentStatus: timeInStatus,
    }
  })
}

// Prioridade para sorting: error > active > blocked > idle > done
const STATUS_PRIORITY: Record<AgentStatus, number> = {
  error: 0, active: 1, blocked: 2, idle: 3, done: 4,
}

export function useAgentWorkItems() {
  const [agents, setAgents] = useState<AgentView[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let channel: RealtimeChannel | null = null
    let fallbackInterval: ReturnType<typeof setInterval> | null = null

    const loadData = async () => {
      try {
        const cutoff = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString()
        const { data, error: fetchError } = await supabase
          .from('agent_work_items')
          .select('*')
          .gte('created_at', cutoff)
          .order('created_at', { ascending: false })

        if (fetchError) throw fetchError
        const views = buildAgentViews(data ?? [])
        const sorted = views.sort(
          (a, b) => STATUS_PRIORITY[a.status] - STATUS_PRIORITY[b.status]
        )
        setAgents(sorted)
        setIsLoading(false)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Erro ao carregar dados')
        setIsLoading(false)
      }
    }

    // Carga inicial
    loadData()

    // Supabase Realtime subscription
    channel = supabase
      .channel('agent_work_items_realtime')
      .on(
        'postgres_changes',
        {
          event: '*',          // INSERT + UPDATE + DELETE
          schema: 'public',
          table: 'agent_work_items',
        },
        (_payload) => {
          // Recarrega lista completa ao receber qualquer evento
          loadData()
        }
      )
      .subscribe((status) => {
        if (status === 'SUBSCRIBED') {
          setIsConnected(true)
          // Cancela fallback polling se WebSocket conectou
          if (fallbackInterval) {
            clearInterval(fallbackInterval)
            fallbackInterval = null
          }
        } else if (status === 'CLOSED' || status === 'CHANNEL_ERROR') {
          setIsConnected(false)
          // Fallback: polling a cada 30s se WebSocket falhar
          if (!fallbackInterval) {
            fallbackInterval = setInterval(loadData, 30_000)
          }
        }
      })

    return () => {
      channel?.unsubscribe()
      if (fallbackInterval) clearInterval(fallbackInterval)
    }
  }, [])

  return { agents, isConnected, isLoading, error }
}
