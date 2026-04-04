import { useEffect, useState, useCallback, useRef } from 'react'
import { supabase } from '@/lib/supabase'
import { RealtimeChannel } from '@supabase/supabase-js'

// ── Types ──────────────────────────────────────────────────

export interface RuntimeTask {
  id: string
  agent_id: string
  task_type: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  payload: Record<string, unknown> | null
  result: Record<string, unknown> | string | null
  created_at: string
  completed_at: string | null
}

export interface TaskFilters {
  agent: string | null
  status: string | null
  taskType: string | null
}

// ── Hook ────────────────────────────────────────────────────

export function useSystemActivity() {
  const [tasks, setTasks] = useState<RuntimeTask[]>([])
  const [failedTasks, setFailedTasks] = useState<RuntimeTask[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [filters, setFilters] = useState<TaskFilters>({ agent: null, status: null, taskType: null })
  const channelRef = useRef<RealtimeChannel | null>(null)

  // Fetch task history
  const fetchTasks = useCallback(async () => {
    try {
      let query = supabase
        .from('runtime_tasks')
        .select('id, agent_id, task_type, status, payload, result, created_at, completed_at')
        .order('created_at', { ascending: false })
        .limit(50)

      if (filters.agent) {
        query = query.eq('agent_id', filters.agent)
      }
      if (filters.status) {
        query = query.eq('status', filters.status)
      }
      if (filters.taskType) {
        query = query.eq('task_type', filters.taskType)
      }

      const { data, error } = await query

      if (error) {
        console.error('Error fetching tasks:', error)
        return
      }

      setTasks((data as RuntimeTask[]) || [])
    } catch (err) {
      console.error('Error fetching tasks:', err)
    } finally {
      setIsLoading(false)
    }
  }, [filters])

  // Fetch failed tasks
  const fetchFailedTasks = useCallback(async () => {
    try {
      const { data, error } = await supabase
        .from('runtime_tasks')
        .select('id, agent_id, task_type, status, payload, result, created_at, completed_at')
        .eq('status', 'failed')
        .order('created_at', { ascending: false })
        .limit(20)

      if (error) {
        console.error('Error fetching failed tasks:', error)
        return
      }

      setFailedTasks((data as RuntimeTask[]) || [])
    } catch (err) {
      console.error('Error fetching failed tasks:', err)
    }
  }, [])

  // Get unique agents and task types for filter dropdowns
  const uniqueAgents = Array.from(new Set(tasks.map(t => t.agent_id))).sort()
  const uniqueTaskTypes = Array.from(new Set(tasks.map(t => t.task_type))).sort()

  // Setup realtime + initial fetch
  useEffect(() => {
    fetchTasks()
    fetchFailedTasks()

    // Subscribe to realtime changes on runtime_tasks
    const channel = supabase
      .channel('system_activity_live')
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'runtime_tasks' },
        () => {
          // Refetch on any change
          fetchTasks()
          fetchFailedTasks()
        }
      )
      .subscribe()

    channelRef.current = channel

    return () => {
      if (channelRef.current) {
        channelRef.current.unsubscribe()
      }
    }
  }, [fetchTasks, fetchFailedTasks])

  // Refetch when filters change
  useEffect(() => {
    fetchTasks()
  }, [fetchTasks])

  return {
    tasks,
    failedTasks,
    isLoading,
    filters,
    setFilters,
    uniqueAgents,
    uniqueTaskTypes,
    refetch: fetchTasks,
  }
}
