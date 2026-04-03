import { useEffect, useState, useCallback, useRef } from 'react'
import { supabase } from '@/lib/supabase'
import { RealtimeChannel } from '@supabase/supabase-js'

// ── Types ──────────────────────────────────────────────────

export interface AgentPulse {
  id: string
  status: 'working' | 'idle'
  last_action: {
    task_type: string
    status: string
    at: string
  } | null
}

export interface FeedEvent {
  id: string
  timestamp: string
  agent: string
  description: string
  type: 'task' | 'workflow' | 'brain' | 'command'
  status: string
}

export interface PulseData {
  agents: AgentPulse[]
  brain: {
    chunks_today: number
    chunks_total: number
    last_ingestions: {
      id: string
      title: string
      source_type: string
      chunks_generated: number
      status: string
      created_at: string
    }[]
  }
  workflows: {
    active: {
      id: string
      name: string
      template_slug: string
      status: string
      current_step: number
      created_at: string
    }[]
    active_count: number
    completed_today: number
  }
  clients: {
    active: number
    mrr_total: number
  }
  timestamp: string
}

// ── Runtime API URL ─────────────────────────────────────────

const RUNTIME_URL = process.env.NEXT_PUBLIC_RUNTIME_URL || 'https://runtime.sparkleai.tech'

// ── Hook ────────────────────────────────────────────────────

export function useCommandPanel() {
  const [pulse, setPulse] = useState<PulseData | null>(null)
  const [feed, setFeed] = useState<FeedEvent[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const feedRef = useRef<FeedEvent[]>([])

  // Keep ref in sync
  useEffect(() => {
    feedRef.current = feed
  }, [feed])

  // Add event to feed (newest first, max 100)
  const addFeedEvent = useCallback((event: FeedEvent) => {
    setFeed(prev => {
      const next = [event, ...prev].slice(0, 100)
      return next
    })
  }, [])

  // Fetch pulse data from Runtime
  const fetchPulse = useCallback(async () => {
    try {
      const resp = await fetch(`${RUNTIME_URL}/system/pulse`)
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const data: PulseData = await resp.json()
      setPulse(data)
      setError(null)
      return data
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao conectar ao Runtime')
      return null
    } finally {
      setIsLoading(false)
    }
  }, [])

  // Send command
  const sendCommand = useCallback(async (text: string): Promise<string> => {
    // Check for known workflow patterns
    const workflowPatterns: Record<string, string> = {
      'onborda': 'onboarding',
      'onboard': 'onboarding',
      'landing': 'landing-page',
      'conteudo': 'content-generation',
      'conteúdo': 'content-generation',
    }

    const lower = text.toLowerCase().trim()
    let matched = false

    for (const [pattern, slug] of Object.entries(workflowPatterns)) {
      if (lower.startsWith(pattern)) {
        matched = true
        const name = text.slice(pattern.length).trim() || text
        try {
          const resp = await fetch(`${RUNTIME_URL}/workflow/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              template_slug: slug,
              name: name,
              context: { source: 'command_panel', raw_input: text },
            }),
          })
          const data = await resp.json()
          if (!resp.ok) {
            return `Erro: ${data.detail || 'falha ao iniciar workflow'}`
          }
          addFeedEvent({
            id: `cmd-${Date.now()}`,
            timestamp: new Date().toISOString(),
            agent: 'system',
            description: `Workflow "${slug}" iniciado: ${name}`,
            type: 'command',
            status: 'running',
          })
          return `Workflow "${slug}" iniciado (${data.instance_id})`
        } catch (err) {
          return `Erro de conexao: ${err instanceof Error ? err.message : 'unknown'}`
        }
      }
    }

    // Default: send as Friday message
    if (!matched) {
      try {
        const resp = await fetch(`${RUNTIME_URL}/friday/message`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text, source: 'command_panel' }),
        })
        const data = await resp.json()
        addFeedEvent({
          id: `cmd-${Date.now()}`,
          timestamp: new Date().toISOString(),
          agent: 'friday',
          description: data.response || data.message || text,
          type: 'command',
          status: 'completed',
        })
        return data.response || data.message || 'Comando enviado'
      } catch (err) {
        return `Erro: ${err instanceof Error ? err.message : 'unknown'}`
      }
    }

    return 'Comando nao reconhecido'
  }, [addFeedEvent])

  // Setup Supabase Realtime + initial fetch
  useEffect(() => {
    let channels: RealtimeChannel[] = []
    let pollInterval: ReturnType<typeof setInterval> | null = null

    // Initial load
    fetchPulse()

    // Poll pulse every 30s
    pollInterval = setInterval(fetchPulse, 30_000)

    // Channel: runtime_tasks (agent activity)
    const tasksChannel = supabase
      .channel('cmd_tasks_live')
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'runtime_tasks' },
        (payload) => {
          const row = payload.new as Record<string, unknown> | undefined
          if (!row) return

          const status = row.status as string
          const agentId = (row.agent_id as string) || 'system'
          const taskType = (row.task_type as string) || ''

          let description = ''
          if (payload.eventType === 'INSERT') {
            description = `${agentId} iniciou ${taskType}`
          } else if (status === 'completed') {
            description = `${agentId} concluiu ${taskType}`
          } else if (status === 'failed') {
            description = `${agentId} falhou em ${taskType}`
          } else {
            description = `${agentId}: ${taskType} → ${status}`
          }

          addFeedEvent({
            id: `task-${row.id || Date.now()}`,
            timestamp: (row.created_at as string) || new Date().toISOString(),
            agent: agentId,
            description,
            type: 'task',
            status,
          })

          // Refresh pulse on task changes
          fetchPulse()
        }
      )
      .subscribe((status) => {
        if (status === 'SUBSCRIBED') setIsConnected(true)
        if (status === 'CLOSED' || status === 'CHANNEL_ERROR') setIsConnected(false)
      })
    channels.push(tasksChannel)

    // Channel: workflow_instances
    const workflowChannel = supabase
      .channel('cmd_workflow_live')
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'workflow_instances' },
        (payload) => {
          const row = payload.new as Record<string, unknown> | undefined
          if (!row) return

          const name = (row.name as string) || (row.template_slug as string) || 'workflow'
          const status = (row.status as string) || ''

          addFeedEvent({
            id: `wf-${row.id || Date.now()}`,
            timestamp: (row.updated_at as string) || new Date().toISOString(),
            agent: 'workflow',
            description: `${name}: ${status}`,
            type: 'workflow',
            status,
          })

          fetchPulse()
        }
      )
      .subscribe()
    channels.push(workflowChannel)

    // Channel: brain_raw_ingestions
    const brainChannel = supabase
      .channel('cmd_brain_live')
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'brain_raw_ingestions' },
        (payload) => {
          const row = payload.new as Record<string, unknown> | undefined
          if (!row) return

          const title = (row.title as string) || 'conteudo'
          const chunks = (row.chunks_generated as number) || 0

          addFeedEvent({
            id: `brain-${row.id || Date.now()}`,
            timestamp: (row.created_at as string) || new Date().toISOString(),
            agent: 'brain',
            description: `Ingeriu "${title}" (${chunks} chunks)`,
            type: 'brain',
            status: 'completed',
          })

          fetchPulse()
        }
      )
      .subscribe()
    channels.push(brainChannel)

    return () => {
      channels.forEach(ch => ch.unsubscribe())
      if (pollInterval) clearInterval(pollInterval)
    }
  }, [fetchPulse, addFeedEvent])

  return { pulse, feed, isConnected, isLoading, error, sendCommand }
}
