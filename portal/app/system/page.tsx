'use client'

import { useState, useMemo } from 'react'
import { useSystemActivity, RuntimeTask, TaskFilters } from '@/hooks/useSystemActivity'

// ── Agent display config ──────────────────────────────────────

const AGENT_LABELS: Record<string, string> = {
  orion: 'Orion',
  analyst: 'Analyst',
  dev: 'Dev',
  qa: 'QA',
  architect: 'Aria',
  po: 'PO',
  devops: 'Gage',
  friday: 'Friday',
  system: 'System',
  brain: 'Brain',
  scheduler: 'Scheduler',
}

function agentLabel(id: string): string {
  return AGENT_LABELS[id] || id
}

// ── Status helpers ─────────────────────────────────────────────

function statusDotClass(status: string): string {
  switch (status) {
    case 'completed': return 'bg-[#00ff87]'
    case 'failed':    return 'bg-[#ef4444]'
    case 'running':   return 'bg-[#eab308] animate-pulse'
    case 'pending':   return 'bg-zinc-500'
    default:          return 'bg-zinc-600'
  }
}

function statusBadgeClass(status: string): string {
  switch (status) {
    case 'completed': return 'text-[#00ff87] bg-[#00ff87]/10 border-[#00ff87]/20'
    case 'failed':    return 'text-[#ef4444] bg-[#ef4444]/10 border-[#ef4444]/20'
    case 'running':   return 'text-[#eab308] bg-[#eab308]/10 border-[#eab308]/20'
    case 'pending':   return 'text-zinc-400 bg-zinc-400/10 border-zinc-400/20'
    default:          return 'text-zinc-500 bg-zinc-500/10 border-zinc-500/20'
  }
}

// ── Duration formatter ─────────────────────────────────────────

function formatDuration(created: string, completed: string | null): string {
  if (!completed) return '--'
  const ms = new Date(completed).getTime() - new Date(created).getTime()
  if (ms < 0) return '--'
  if (ms < 1000) return `${ms}ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`
  const mins = Math.floor(ms / 60_000)
  const secs = Math.round((ms % 60_000) / 1000)
  return `${mins}m ${secs}s`
}

function formatTime(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function formatDateTime(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleString('pt-BR', {
    day: '2-digit', month: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

function isRecent(iso: string, hoursAgo: number = 1): boolean {
  return Date.now() - new Date(iso).getTime() < hoursAgo * 3600_000
}

// ── Inline SVG icons ───────────────────────────────────────────

function IconActivity() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </svg>
  )
}

function IconAlert() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  )
}

function IconClock() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  )
}

function IconChevron({ open }: { open: boolean }) {
  return (
    <svg
      width="12" height="12" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      className={`transition-transform duration-200 ${open ? 'rotate-90' : ''}`}
    >
      <polyline points="9 18 15 12 9 6" />
    </svg>
  )
}

function IconBack() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="19" y1="12" x2="5" y2="12" />
      <polyline points="12 19 5 12 12 5" />
    </svg>
  )
}

// ── Filter Bar ─────────────────────────────────────────────────

function FilterBar({
  filters,
  setFilters,
  agents,
  taskTypes,
}: {
  filters: TaskFilters
  setFilters: (f: TaskFilters) => void
  agents: string[]
  taskTypes: string[]
}) {
  const selectClass = 'bg-white/[0.03] border border-white/[0.08] rounded px-2 py-1 text-xs font-mono text-white/70 outline-none focus:border-[#0ea5e9]/40 transition-colors appearance-none cursor-pointer'

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-[10px] text-white/30 font-mono uppercase tracking-widest">Filtros</span>

      <select
        className={selectClass}
        value={filters.agent || ''}
        onChange={e => setFilters({ ...filters, agent: e.target.value || null })}
      >
        <option value="">Todos agentes</option>
        {agents.map(a => (
          <option key={a} value={a}>{agentLabel(a)}</option>
        ))}
      </select>

      <select
        className={selectClass}
        value={filters.status || ''}
        onChange={e => setFilters({ ...filters, status: e.target.value || null })}
      >
        <option value="">Todos status</option>
        <option value="completed">Completed</option>
        <option value="failed">Failed</option>
        <option value="running">Running</option>
        <option value="pending">Pending</option>
      </select>

      <select
        className={selectClass}
        value={filters.taskType || ''}
        onChange={e => setFilters({ ...filters, taskType: e.target.value || null })}
      >
        <option value="">Todos tipos</option>
        {taskTypes.map(t => (
          <option key={t} value={t}>{t}</option>
        ))}
      </select>

      {(filters.agent || filters.status || filters.taskType) && (
        <button
          onClick={() => setFilters({ agent: null, status: null, taskType: null })}
          className="text-[10px] text-white/30 hover:text-white/60 font-mono underline transition-colors"
        >
          limpar
        </button>
      )}
    </div>
  )
}

// ── Task Row (expandable) ──────────────────────────────────────

function TaskRow({ task }: { task: RuntimeTask }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="border-b border-white/[0.03] last:border-b-0">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 py-2.5 px-2 hover:bg-white/[0.02] transition-colors text-left"
      >
        {/* Chevron */}
        <span className="text-white/20 flex-shrink-0">
          <IconChevron open={expanded} />
        </span>

        {/* Timestamp */}
        <span className="text-[10px] font-mono text-white/25 flex-shrink-0 w-16">
          {formatTime(task.created_at)}
        </span>

        {/* Agent */}
        <span className="text-[11px] font-mono font-semibold text-white/70 flex-shrink-0 w-20 truncate">
          {agentLabel(task.agent_id)}
        </span>

        {/* Task type */}
        <span className="text-xs font-mono text-white/50 flex-1 truncate">
          {task.task_type}
        </span>

        {/* Status badge */}
        <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded border flex-shrink-0 ${statusBadgeClass(task.status)}`}>
          {task.status}
        </span>

        {/* Duration */}
        <span className="text-[10px] font-mono text-white/20 flex-shrink-0 w-14 text-right">
          {formatDuration(task.created_at, task.completed_at)}
        </span>
      </button>

      {/* Expanded detail */}
      {expanded && (
        <div className="px-8 pb-3 space-y-2">
          {task.payload && Object.keys(task.payload).length > 0 && (
            <div>
              <span className="text-[10px] text-white/30 font-mono uppercase tracking-widest">Payload</span>
              <pre className="mt-1 text-[11px] font-mono text-white/40 bg-white/[0.02] border border-white/[0.04] rounded p-2 overflow-x-auto max-h-40 whitespace-pre-wrap">
                {JSON.stringify(task.payload, null, 2)}
              </pre>
            </div>
          )}
          {task.result && (
            <div>
              <span className="text-[10px] text-white/30 font-mono uppercase tracking-widest">Result</span>
              <pre className={`mt-1 text-[11px] font-mono bg-white/[0.02] border rounded p-2 overflow-x-auto max-h-40 whitespace-pre-wrap ${
                task.status === 'failed' ? 'text-[#ef4444]/70 border-[#ef4444]/10' : 'text-white/40 border-white/[0.04]'
              }`}>
                {typeof task.result === 'string' ? task.result : JSON.stringify(task.result, null, 2)}
              </pre>
            </div>
          )}
          {task.completed_at && (
            <div className="text-[10px] text-white/20 font-mono">
              Concluido em {formatDateTime(task.completed_at)}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Error Log Panel ────────────────────────────────────────────

function ErrorLogPanel({ tasks }: { tasks: RuntimeTask[] }) {
  const [expandedId, setExpandedId] = useState<string | null>(null)

  if (tasks.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-2">
        <span className="text-[#00ff87]/40 font-mono text-xs">Nenhum erro recente</span>
        <span className="text-white/15 font-mono text-[10px]">Tasks com status=failed aparecem aqui</span>
      </div>
    )
  }

  return (
    <div className="space-y-1">
      {tasks.map(task => {
        const recent = isRecent(task.created_at)
        const isOpen = expandedId === task.id

        return (
          <div
            key={task.id}
            className={`rounded-lg border transition-colors ${
              recent
                ? 'border-[#ef4444]/30 bg-[#ef4444]/[0.03]'
                : 'border-white/[0.04] bg-white/[0.01]'
            }`}
          >
            <button
              onClick={() => setExpandedId(isOpen ? null : task.id)}
              className="w-full flex items-center gap-3 px-3 py-2.5 text-left"
            >
              <span className="h-2 w-2 rounded-full bg-[#ef4444] flex-shrink-0" />

              <span className="text-[10px] font-mono text-white/25 flex-shrink-0 w-16">
                {formatTime(task.created_at)}
              </span>

              <span className="text-[11px] font-mono font-semibold text-white/60 flex-shrink-0 w-16">
                {agentLabel(task.agent_id)}
              </span>

              <span className="text-xs font-mono text-[#ef4444]/70 flex-1 truncate">
                {task.task_type}
              </span>

              {recent && (
                <span className="text-[9px] font-mono text-[#ef4444]/60 bg-[#ef4444]/10 px-1.5 py-0.5 rounded flex-shrink-0">
                  RECENTE
                </span>
              )}

              <span className="text-white/15 flex-shrink-0">
                <IconChevron open={isOpen} />
              </span>
            </button>

            {isOpen && task.result && (
              <div className="px-3 pb-3">
                <pre className="text-[11px] font-mono text-[#ef4444]/60 bg-[#ef4444]/[0.03] border border-[#ef4444]/10 rounded p-2 overflow-x-auto max-h-40 whitespace-pre-wrap">
                  {typeof task.result === 'string' ? task.result : JSON.stringify(task.result, null, 2)}
                </pre>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ── System Timeline (24h) ──────────────────────────────────────

function SystemTimeline({ tasks }: { tasks: RuntimeTask[] }) {
  const now = Date.now()
  const h24ago = now - 24 * 3600_000

  // Filter to last 24h
  const recentTasks = useMemo(() => {
    return tasks.filter(t => new Date(t.created_at).getTime() >= h24ago)
  }, [tasks, h24ago])

  // Group by hour (0-23 hours ago)
  const hours = useMemo(() => {
    const buckets: { hour: number; label: string; tasks: RuntimeTask[] }[] = []
    for (let i = 23; i >= 0; i--) {
      const hourStart = now - (i + 1) * 3600_000
      const hourEnd = now - i * 3600_000
      const d = new Date(hourEnd)
      buckets.push({
        hour: i,
        label: d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }),
        tasks: recentTasks.filter(t => {
          const ts = new Date(t.created_at).getTime()
          return ts >= hourStart && ts < hourEnd
        }),
      })
    }
    return buckets
  }, [recentTasks, now])

  const maxCount = Math.max(1, ...hours.map(h => h.tasks.length))

  return (
    <div className="space-y-2">
      {/* Legend */}
      <div className="flex items-center gap-4 text-[10px] font-mono text-white/30">
        <div className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-[#00ff87]" />
          <span>completed</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-[#ef4444]" />
          <span>failed</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-[#eab308]" />
          <span>running</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-zinc-500" />
          <span>pending</span>
        </div>
      </div>

      {/* Timeline bars */}
      <div className="flex items-end gap-[2px] h-32">
        {hours.map(bucket => {
          const barHeight = bucket.tasks.length > 0
            ? Math.max(8, (bucket.tasks.length / maxCount) * 100)
            : 0
          const failedCount = bucket.tasks.filter(t => t.status === 'failed').length
          const completedCount = bucket.tasks.filter(t => t.status === 'completed').length
          const runningCount = bucket.tasks.filter(t => t.status === 'running').length
          const total = bucket.tasks.length

          const failedPct = total > 0 ? (failedCount / total) * 100 : 0
          const runningPct = total > 0 ? (runningCount / total) * 100 : 0

          return (
            <div
              key={bucket.hour}
              className="flex-1 flex flex-col items-center justify-end group relative"
              style={{ height: '100%' }}
            >
              {/* Tooltip */}
              {total > 0 && (
                <div className="absolute bottom-full mb-2 hidden group-hover:block z-10">
                  <div className="bg-zinc-900 border border-white/10 rounded-lg px-2.5 py-1.5 text-[10px] font-mono whitespace-nowrap shadow-xl">
                    <div className="text-white/60 font-semibold mb-0.5">{bucket.label}</div>
                    <div className="text-white/40">{total} task{total !== 1 ? 's' : ''}</div>
                    {completedCount > 0 && <div className="text-[#00ff87]/70">{completedCount} ok</div>}
                    {failedCount > 0 && <div className="text-[#ef4444]/70">{failedCount} failed</div>}
                    {runningCount > 0 && <div className="text-[#eab308]/70">{runningCount} running</div>}
                  </div>
                </div>
              )}

              {/* Bar */}
              {total > 0 ? (
                <div
                  className="w-full rounded-t overflow-hidden transition-all duration-300"
                  style={{ height: `${barHeight}%`, minHeight: '4px' }}
                >
                  {/* Stacked: green base, yellow middle, red top */}
                  <div className="w-full h-full flex flex-col-reverse">
                    <div className="bg-[#00ff87]/60" style={{ flexGrow: completedCount }} />
                    <div className="bg-[#eab308]/60" style={{ flexGrow: runningCount }} />
                    <div className="bg-[#ef4444]/60" style={{ flexGrow: failedCount }} />
                    <div className="bg-zinc-500/60" style={{ flexGrow: total - completedCount - failedCount - runningCount }} />
                  </div>
                </div>
              ) : (
                <div className="w-full h-[2px] bg-white/[0.03] rounded" />
              )}
            </div>
          )
        })}
      </div>

      {/* Hour labels (show every 4th) */}
      <div className="flex gap-[2px]">
        {hours.map((bucket, i) => (
          <div key={bucket.hour} className="flex-1 text-center">
            {i % 4 === 0 ? (
              <span className="text-[8px] font-mono text-white/20">{bucket.label}</span>
            ) : null}
          </div>
        ))}
      </div>

      {/* Summary */}
      <div className="flex items-center gap-4 text-[10px] font-mono text-white/25 pt-1 border-t border-white/[0.03]">
        <span>{recentTasks.length} tasks nas ultimas 24h</span>
        <span>{recentTasks.filter(t => t.status === 'failed').length} falhas</span>
        <span>{recentTasks.filter(t => t.status === 'completed').length} concluidas</span>
      </div>
    </div>
  )
}

// ── Tab type ───────────────────────────────────────────────────

type Tab = 'history' | 'errors' | 'timeline'

// ── Main Page ──────────────────────────────────────────────────

export default function SystemPage() {
  const {
    tasks,
    failedTasks,
    isLoading,
    filters,
    setFilters,
    uniqueAgents,
    uniqueTaskTypes,
  } = useSystemActivity()

  const [activeTab, setActiveTab] = useState<Tab>('history')

  const tabs: { id: Tab; label: string; icon: () => JSX.Element; count?: number }[] = [
    { id: 'history', label: 'Task History', icon: IconActivity, count: tasks.length },
    { id: 'errors', label: 'Error Log', icon: IconAlert, count: failedTasks.length },
    { id: 'timeline', label: 'Timeline 24h', icon: IconClock },
  ]

  return (
    <main
      className="min-h-screen px-4 py-4 flex flex-col gap-3"
      style={{ backgroundColor: '#0a0a0f' }}
    >
      {/* ── Header ──────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <a
            href="/command"
            className="text-white/20 hover:text-white/50 transition-colors"
            title="Voltar ao Command Panel"
          >
            <IconBack />
          </a>
          <h1 className="text-base font-bold text-white tracking-tight font-mono">
            SPARKLE // SYSTEM
          </h1>
          <span className="text-[10px] text-white/20 font-mono uppercase tracking-widest">
            Activity Monitor
          </span>
        </div>

        <div className="flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-[#00ff87] animate-pulse" />
          <span className="text-[10px] text-white/30 font-mono">LIVE</span>
        </div>
      </div>

      {/* ── Tabs ────────────────────────────────────────────── */}
      <div className="flex items-center gap-1 rounded-lg p-1 bg-white/[0.02] border border-white/[0.04] w-fit">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={[
              'flex items-center gap-1.5 px-3 py-1.5 rounded text-[11px] font-mono transition-all',
              activeTab === tab.id
                ? 'bg-white/[0.08] text-white/80'
                : 'text-white/30 hover:text-white/50',
            ].join(' ')}
          >
            <tab.icon />
            <span>{tab.label}</span>
            {tab.count !== undefined && (
              <span className={`text-[9px] px-1 py-0.5 rounded ${
                activeTab === tab.id ? 'bg-white/10 text-white/50' : 'bg-white/[0.03] text-white/20'
              }`}>
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── Content ─────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-h-0">
        {/* Loading state */}
        {isLoading && (
          <div className="flex items-center justify-center py-16">
            <span className="text-xs text-white/20 font-mono animate-pulse">Carregando...</span>
          </div>
        )}

        {!isLoading && activeTab === 'history' && (
          <div className="flex flex-col gap-3 flex-1 min-h-0">
            <FilterBar
              filters={filters}
              setFilters={setFilters}
              agents={uniqueAgents}
              taskTypes={uniqueTaskTypes}
            />

            <div
              className="flex-1 overflow-y-auto rounded-lg border border-white/[0.04] bg-white/[0.01]"
              style={{ scrollbarWidth: 'thin', maxHeight: 'calc(100vh - 220px)' }}
            >
              {tasks.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 gap-2">
                  <span className="text-white/15 font-mono text-xs">Nenhuma task encontrada</span>
                  <span className="text-white/10 font-mono text-[10px]">
                    {filters.agent || filters.status || filters.taskType
                      ? 'Tente ajustar os filtros'
                      : 'Tasks executadas pelo Runtime aparecem aqui'}
                  </span>
                </div>
              ) : (
                tasks.map(task => <TaskRow key={task.id} task={task} />)
              )}
            </div>
          </div>
        )}

        {!isLoading && activeTab === 'errors' && (
          <div
            className="flex-1 overflow-y-auto rounded-lg border border-white/[0.04] bg-white/[0.01] p-3"
            style={{ scrollbarWidth: 'thin', maxHeight: 'calc(100vh - 180px)' }}
          >
            <ErrorLogPanel tasks={failedTasks} />
          </div>
        )}

        {!isLoading && activeTab === 'timeline' && (
          <div className="rounded-lg border border-white/[0.04] bg-white/[0.01] p-4">
            <SystemTimeline tasks={tasks} />
          </div>
        )}
      </div>

      {/* ── Footer ──────────────────────────────────────────── */}
      <div className="flex items-center justify-between text-[10px] text-white/15 font-mono pt-1 border-t border-white/[0.03]">
        <span>SPARKLE AIOX // System Activity Monitor</span>
        <span>
          {tasks.length} tasks carregadas | {failedTasks.length} erros
        </span>
      </div>
    </main>
  )
}
