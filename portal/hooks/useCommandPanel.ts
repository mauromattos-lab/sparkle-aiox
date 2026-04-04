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
  type: 'task' | 'workflow' | 'brain' | 'command' | 'content' | 'error' | 'friday'
  status: string
}

export interface SystemStats {
  chunks_total: number
  insights_total: number
  content_total: number
  workflows_active: number
  uptime: string | null
}

export interface BrainSearchResult {
  id?: string
  title?: string
  content: string
  domain?: string
  confidence?: number
  source?: string
  type?: 'synthesis' | 'insight' | 'chunk'
  similarity?: number
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
  const [stats, setStats] = useState<SystemStats | null>(null)
  const [toasts, setToasts] = useState<{ id: string; message: string; type: 'brain' | 'content' | 'error' }[]>([])
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

  // Add toast notification (auto-dismiss after 4s)
  const addToast = useCallback((message: string, type: 'brain' | 'content' | 'error') => {
    const id = `toast-${Date.now()}`
    setToasts(prev => [...prev, { id, message, type }])
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 4000)
  }, [])

  const dismissToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  // Fetch aggregated stats from multiple endpoints
  const fetchStats = useCallback(async () => {
    try {
      const [brainResp, contentResp, healthResp] = await Promise.allSettled([
        fetch(`${RUNTIME_URL}/brain/activity`),
        fetch(`${RUNTIME_URL}/content/list?limit=1`),
        fetch(`${RUNTIME_URL}/health`),
      ])

      const newStats: SystemStats = {
        chunks_total: 0,
        insights_total: 0,
        content_total: 0,
        workflows_active: 0,
        uptime: null,
      }

      if (brainResp.status === 'fulfilled' && brainResp.value.ok) {
        const brain = await brainResp.value.json()
        if (brain.stats) {
          newStats.chunks_total = brain.stats.chunks_total || 0
          newStats.insights_total = brain.stats.insights_total || 0
        }
      }

      if (contentResp.status === 'fulfilled' && contentResp.value.ok) {
        const content = await contentResp.value.json()
        newStats.content_total = content.total || content.items?.length || 0
      }

      if (healthResp.status === 'fulfilled' && healthResp.value.ok) {
        const health = await healthResp.value.json()
        newStats.uptime = health.uptime || null
      }

      setStats(newStats)
    } catch {
      // stats are non-critical, fail silently
    }
  }, [])

  // Fetch pulse data from Runtime
  const fetchPulse = useCallback(async () => {
    try {
      const resp = await fetch(`${RUNTIME_URL}/system/pulse`)
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const data: PulseData = await resp.json()
      setPulse(data)
      setStats(prev => prev ? { ...prev, workflows_active: data.workflows.active_count } : prev)
      setError(null)
      return data
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao conectar ao Runtime')
      return null
    } finally {
      setIsLoading(false)
    }
  }, [])

  // Brain search
  const searchBrain = useCallback(async (query: string, limit = 10): Promise<BrainSearchResult[]> => {
    try {
      const resp = await fetch(`${RUNTIME_URL}/brain/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, limit }),
      })
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const data = await resp.json()
      return data.results || data.items || []
    } catch (err) {
      throw new Error(err instanceof Error ? err.message : 'Erro ao buscar no Brain')
    }
  }, [])

  // Send command
  const sendCommand = useCallback(async (text: string): Promise<string> => {
    const trimmed = text.trim()
    const lower = trimmed.toLowerCase()

    // ── /brain <query> — Brain semantic search ──────────────
    if (lower.startsWith('/brain ')) {
      const query = trimmed.slice(7).trim()
      if (!query) return 'Uso: /brain <texto de busca>'
      try {
        const results = await searchBrain(query)
        addFeedEvent({
          id: `cmd-${Date.now()}`,
          timestamp: new Date().toISOString(),
          agent: 'brain',
          description: `Busca: "${query}" -- ${results.length} resultados`,
          type: 'brain',
          status: 'completed',
        })
        if (results.length === 0) return `Brain: nenhum resultado para "${query}"`
        return results
          .slice(0, 5)
          .map((r, i) => `[${i + 1}] ${r.title || r.domain || '---'}: ${(r.content || '').slice(0, 120)}...`)
          .join('\n')
      } catch (err) {
        return `Erro Brain: ${err instanceof Error ? err.message : 'unknown'}`
      }
    }

    // ── /task <description> — Create task in Runtime ────────
    if (lower.startsWith('/task ')) {
      const description = trimmed.slice(6).trim()
      if (!description) return 'Uso: /task <descricao da tarefa>'
      try {
        const resp = await fetch(`${RUNTIME_URL}/tasks/create`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            task_type: 'manual',
            payload: { description, source: 'command_panel' },
          }),
        })
        const data = await resp.json()
        if (!resp.ok) return `Erro: ${data.detail || 'falha ao criar task'}`
        addFeedEvent({
          id: `cmd-${Date.now()}`,
          timestamp: new Date().toISOString(),
          agent: 'system',
          description: `Task criada: ${description}`,
          type: 'task',
          status: 'pending',
        })
        return `Task criada (${data.task_id || data.id || 'ok'}): ${description}`
      } catch (err) {
        return `Erro: ${err instanceof Error ? err.message : 'unknown'}`
      }
    }

    // ── /status — System status (health + capabilities) ─────
    if (lower === '/status' || lower.startsWith('/status')) {
      try {
        const [healthResp, capsResp] = await Promise.allSettled([
          fetch(`${RUNTIME_URL}/health`),
          fetch(`${RUNTIME_URL}/system/capabilities`),
        ])

        const parts: string[] = []

        if (healthResp.status === 'fulfilled' && healthResp.value.ok) {
          const h = await healthResp.value.json()
          parts.push(`Runtime: ${h.status || 'ok'} | Uptime: ${h.uptime || '---'}`)
        } else {
          parts.push('Runtime: OFFLINE')
        }

        if (capsResp.status === 'fulfilled' && capsResp.value.ok) {
          const c = await capsResp.value.json()
          const handlers = c.handlers || c.capabilities || []
          const handlerList = Array.isArray(handlers) ? handlers : Object.keys(handlers)
          parts.push(`Handlers: ${handlerList.length} (${handlerList.slice(0, 8).join(', ')}${handlerList.length > 8 ? '...' : ''})`)
        }

        addFeedEvent({
          id: `cmd-${Date.now()}`,
          timestamp: new Date().toISOString(),
          agent: 'system',
          description: 'Status check executado',
          type: 'command',
          status: 'completed',
        })

        return parts.join('\n')
      } catch (err) {
        return `Erro: ${err instanceof Error ? err.message : 'unknown'}`
      }
    }

    // ── Workflow patterns ────────────────────────────────────
    const workflowPatterns: Record<string, string> = {
      'onborda': 'onboarding',
      'onboard': 'onboarding',
      'landing': 'landing-page',
      'conteudo': 'content-generation',
      'conteúdo': 'content-generation',
    }

    let matched = false

    for (const [pattern, slug] of Object.entries(workflowPatterns)) {
      if (lower.startsWith(pattern)) {
        matched = true
        const name = trimmed.slice(pattern.length).trim() || trimmed
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
  }, [addFeedEvent, searchBrain])

  // Setup Supabase Realtime + initial fetch
  useEffect(() => {
    let channels: RealtimeChannel[] = []
    let pollInterval: ReturnType<typeof setInterval> | null = null

    // Initial load
    fetchPulse()
    fetchStats()

    // Poll pulse every 30s, stats every 60s
    pollInterval = setInterval(fetchPulse, 30_000)
    const statsInterval = setInterval(fetchStats, 60_000)

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

          const eventType: FeedEvent['type'] = status === 'failed' ? 'error' : 'task'

          addFeedEvent({
            id: `task-${row.id || Date.now()}`,
            timestamp: (row.created_at as string) || new Date().toISOString(),
            agent: agentId,
            description,
            type: eventType,
            status,
          })

          if (status === 'failed') {
            addToast(`Error: ${agentId} failed ${taskType}`, 'error')
          }

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

          addToast(`Brain ingest: "${title}" (${chunks} chunks)`, 'brain')
          fetchPulse()
          fetchStats()
        }
      )
      .subscribe()
    channels.push(brainChannel)

    // Channel: generated_content
    const contentChannel = supabase
      .channel('cmd_content_live')
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'generated_content' },
        (payload) => {
          const row = payload.new as Record<string, unknown> | undefined
          if (!row) return

          const topic = (row.topic as string) || 'conteudo'
          const persona = (row.persona as string) || ''
          const format = (row.format as string) || ''

          addFeedEvent({
            id: `content-${row.id || Date.now()}`,
            timestamp: (row.created_at as string) || new Date().toISOString(),
            agent: persona || 'content',
            description: `Gerou ${format}: "${topic}"`,
            type: 'content',
            status: 'completed',
          })

          addToast(`Content: ${format} "${topic}"`, 'content')
          fetchStats()
        }
      )
      .subscribe()
    channels.push(contentChannel)

    return () => {
      channels.forEach(ch => ch.unsubscribe())
      if (pollInterval) clearInterval(pollInterval)
      clearInterval(statsInterval)
    }
  }, [fetchPulse, fetchStats, addFeedEvent, addToast])

  return { pulse, feed, isConnected, isLoading, error, sendCommand, searchBrain, stats, toasts, dismissToast }
}
