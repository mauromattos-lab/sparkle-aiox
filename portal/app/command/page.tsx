'use client'

import { useState, useRef, useEffect, KeyboardEvent } from 'react'
import { useCommandPanel, AgentPulse, FeedEvent, SystemStats } from '@/hooks/useCommandPanel'
import { useClientIdentity } from '@/hooks/useClientIdentity'
import BrainActivity from '@/components/BrainActivity'
import ContentManager from '@/components/ContentManager'
import ClientHeader from '@/components/ClientHeader'
import WelcomeSection from '@/components/WelcomeSection'

// ── Agent display config ──────────────────────────────────────

const AGENT_LABELS: Record<string, { name: string; role: string }> = {
  orion:     { name: 'Orion',     role: 'Orchestrator' },
  analyst:   { name: 'Analyst',   role: 'Research' },
  dev:       { name: 'Dev',       role: 'Engineering' },
  qa:        { name: 'QA',        role: 'Validation' },
  architect: { name: 'Aria',      role: 'Architecture' },
  po:        { name: 'PO',        role: 'Product' },
  devops:    { name: 'Gage',      role: 'DevOps' },
}

// ── Status badge colors ────────────────────────────────────────

function statusColor(status: string): string {
  switch (status) {
    case 'running':
    case 'working':
      return 'bg-[#0ea5e9]'
    case 'completed':
    case 'done':
    case 'funcional':
      return 'bg-[#00ff87]'
    case 'pending':
    case 'idle':
      return 'bg-zinc-500'
    case 'failed':
    case 'error':
    case 'erro':
      return 'bg-[#ef4444]'
    case 'paused':
    case 'blocked':
    case 'aguardando_qa':
      return 'bg-[#eab308]'
    default:
      return 'bg-zinc-600'
  }
}

function feedTypeColor(type: string): string {
  switch (type) {
    case 'task':     return 'text-white/60'
    case 'brain':    return 'text-[#3b82f6]'
    case 'content':  return 'text-[#22c55e]'
    case 'error':    return 'text-[#ef4444]'
    case 'friday':   return 'text-purple-400'
    case 'workflow': return 'text-[#eab308]'
    case 'command':  return 'text-purple-400'
    default:         return 'text-white/40'
  }
}

function feedTypeBg(type: string): string {
  switch (type) {
    case 'brain':    return 'border-l-[#3b82f6]/30'
    case 'content':  return 'border-l-[#22c55e]/30'
    case 'error':    return 'border-l-[#ef4444]/30'
    case 'friday':   return 'border-l-purple-400/30'
    case 'workflow': return 'border-l-[#eab308]/30'
    default:         return 'border-l-transparent'
  }
}

// ── Toast color mapping ────────────────────────────────────────

function toastColor(type: 'brain' | 'content' | 'error'): string {
  switch (type) {
    case 'brain':   return 'border-[#3b82f6]/40 bg-[#3b82f6]/10 text-[#3b82f6]'
    case 'content': return 'border-[#22c55e]/40 bg-[#22c55e]/10 text-[#22c55e]'
    case 'error':   return 'border-[#ef4444]/40 bg-[#ef4444]/10 text-[#ef4444]'
  }
}

// ── Stats Bar ──────────────────────────────────────────────────

function StatsBar({ stats, pulse }: { stats: SystemStats | null; pulse: { workflows: { active_count: number } } | null }) {
  if (!stats) return null

  const items = [
    { label: 'Brain', value: `${stats.chunks_total} chunks, ${stats.insights_total} insights`, color: 'text-[#3b82f6]' },
    { label: 'Content', value: `${stats.content_total} items`, color: 'text-[#22c55e]' },
    { label: 'Workflows', value: `${pulse?.workflows.active_count ?? stats.workflows_active} ativos`, color: 'text-[#eab308]' },
    ...(stats.uptime ? [{ label: 'Uptime', value: stats.uptime, color: 'text-white/50' }] : []),
  ]

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg px-4 py-2 bg-white/5 backdrop-blur-md border border-white/10">
      {items.map((item, i) => (
        <div key={item.label} className="flex items-center gap-2">
          {i > 0 && <span className="hidden sm:inline text-white/10">|</span>}
          <span className="text-[10px] font-mono text-white/30 uppercase tracking-wider">{item.label}</span>
          <span className={`text-xs font-mono font-medium ${item.color}`}>{item.value}</span>
        </div>
      ))}
    </div>
  )
}

// ── Toast Container ────────────────────────────────────────────

function ToastContainer({ toasts, onDismiss }: { toasts: { id: string; message: string; type: 'brain' | 'content' | 'error' }[]; onDismiss: (id: string) => void }) {
  if (toasts.length === 0) return null

  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
      {toasts.map(toast => (
        <div
          key={toast.id}
          className={`flex items-center gap-2 rounded-lg border px-3 py-2 font-mono text-xs backdrop-blur-md animate-slide-in ${toastColor(toast.type)}`}
          onClick={() => onDismiss(toast.id)}
          style={{ cursor: 'pointer' }}
        >
          <span className="flex-1">{toast.message}</span>
          <span className="text-white/20 hover:text-white/40 text-[10px]">x</span>
        </div>
      ))}
    </div>
  )
}

// ── Inline SVG icons (no emoji) ────────────────────────────────

function IconTerminal() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="4 17 10 11 4 5" />
      <line x1="12" y1="19" x2="20" y2="19" />
    </svg>
  )
}

function IconPulse() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </svg>
  )
}

function IconBrain() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <path d="M12 2a7 7 0 0 0 0 20" />
      <path d="M12 2a7 7 0 0 1 0 20" />
      <path d="M2 12h20" />
    </svg>
  )
}

function IconSend() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  )
}

// ── AgentCard (Team Panel) ─────────────────────────────────────

function AgentTile({ agent }: { agent: AgentPulse }) {
  const label = AGENT_LABELS[agent.id] || { name: agent.id, role: '' }
  const isWorking = agent.status === 'working'

  return (
    <div
      className={[
        'rounded-lg p-3 transition-all duration-300 border',
        isWorking
          ? 'border-[#0ea5e9]/40 bg-[#0ea5e9]/5'
          : 'border-white/5 bg-white/[0.02]',
      ].join(' ')}
    >
      {/* Top row: name + status dot */}
      <div className="flex items-center justify-between mb-1">
        <span className="font-mono text-xs font-semibold text-white/90">
          {label.name}
        </span>
        <span
          className={[
            'h-2 w-2 rounded-full',
            isWorking ? 'bg-[#0ea5e9] animate-pulse' : 'bg-zinc-600',
          ].join(' ')}
        />
      </div>

      {/* Role */}
      <p className="text-[10px] text-white/30 uppercase tracking-widest mb-2">
        {label.role}
      </p>

      {/* Last action */}
      {agent.last_action ? (
        <div className="flex items-center gap-1">
          <span className={`h-1.5 w-1.5 rounded-full flex-shrink-0 ${statusColor(agent.last_action.status)}`} />
          <span className="text-[10px] text-white/40 truncate font-mono">
            {agent.last_action.task_type}
          </span>
        </div>
      ) : (
        <p className="text-[10px] text-white/20 italic">standby</p>
      )}
    </div>
  )
}

// ── FeedItem ────────────────────────────────────────────────────

function FeedItem({ event }: { event: FeedEvent }) {
  const time = new Date(event.timestamp)
  const hh = String(time.getHours()).padStart(2, '0')
  const mm = String(time.getMinutes()).padStart(2, '0')
  const ss = String(time.getSeconds()).padStart(2, '0')

  return (
    <div className={`flex gap-3 py-2 border-b border-white/[0.03] last:border-b-0 border-l-2 pl-2 ${feedTypeBg(event.type)}`}>
      {/* Timestamp */}
      <span className="text-[10px] font-mono text-white/25 flex-shrink-0 pt-0.5 w-14 text-right">
        {hh}:{mm}:{ss}
      </span>

      {/* Agent tag */}
      <span className={`text-[10px] font-mono font-semibold flex-shrink-0 pt-0.5 w-16 ${feedTypeColor(event.type)}`}>
        {event.agent}
      </span>

      {/* Description */}
      <span className="text-xs text-white/60 flex-1">
        {event.description}
      </span>

      {/* Status badge */}
      <span className={`h-1.5 w-1.5 rounded-full flex-shrink-0 mt-1.5 ${statusColor(event.status)}`} />
    </div>
  )
}

// ── Command Bar ─────────────────────────────────────────────────

function CommandBar({ onSend }: { onSend: (text: string) => Promise<string> }) {
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [lastResponse, setLastResponse] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleSend = async () => {
    const text = input.trim()
    if (!text || sending) return
    setSending(true)
    setInput('')
    setLastResponse(null)
    try {
      const resp = await onSend(text)
      setLastResponse(resp)
    } catch {
      setLastResponse('Erro ao enviar comando')
    } finally {
      setSending(false)
      inputRef.current?.focus()
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="w-full">
      <div className="flex items-center gap-2 bg-white/[0.03] border border-white/[0.06] rounded-lg px-3 py-2 focus-within:border-[#0ea5e9]/40 transition-colors">
        <span className="text-[#00ff87]/60">
          <IconTerminal />
        </span>
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="onborda cliente X | landing nicho Y | qualquer comando para Friday..."
          className="flex-1 bg-transparent text-sm font-mono text-white/80 placeholder:text-white/20 outline-none"
          disabled={sending}
        />
        <button
          onClick={handleSend}
          disabled={sending || !input.trim()}
          className="text-white/30 hover:text-[#00ff87] transition-colors disabled:opacity-30"
        >
          {sending ? (
            <span className="h-4 w-4 block rounded-full border-2 border-white/20 border-t-[#0ea5e9] animate-spin" />
          ) : (
            <IconSend />
          )}
        </button>
      </div>
      {lastResponse && (
        <div className="mt-1 px-3 py-1.5 text-xs font-mono text-white/40 bg-white/[0.02] rounded border border-white/[0.04]">
          {lastResponse}
        </div>
      )}
    </div>
  )
}

// ── Main Page ────────────────────────────────────────────────────

export default function CommandPage() {
  const { pulse, feed, isConnected, isLoading, error, sendCommand, stats, toasts, dismissToast } = useCommandPanel()
  const clientIdentity = useClientIdentity()
  const feedContainerRef = useRef<HTMLDivElement>(null)
  const [rightPanel, setRightPanel] = useState<'brain' | 'content'>('brain')

  // Auto-scroll feed to top (newest first, so no scroll needed)

  return (
    <main
      className="min-h-screen px-4 py-4 flex flex-col gap-3"
      style={{ backgroundColor: '#0a0a0f' }}
    >
      {/* ── Toast Notifications ───────────────────────────── */}
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />

      {/* ── Client Header ─────────────────────────────────── */}
      <ClientHeader
        identity={clientIdentity}
        rightContent={
          <div className="flex items-center gap-3">
            {/* System Activity link */}
            <a
              href="/system"
              className="text-[10px] font-mono text-white/25 hover:text-white/50 transition-colors uppercase tracking-widest"
              title="System Activity Monitor"
            >
              System
            </a>

            {/* Realtime indicator */}
            <div className="flex items-center gap-1.5">
              <span
                className={[
                  'h-1.5 w-1.5 rounded-full transition-colors duration-500',
                  isConnected ? 'bg-[#00ff87] animate-pulse' : 'bg-zinc-600',
                ].join(' ')}
              />
              <span className="text-[10px] text-white/30 font-mono">
                {isConnected ? 'LIVE' : 'POLL'}
              </span>
            </div>
          </div>
        }
      />

      {/* ── Welcome Section ────────────────────────────────── */}
      <WelcomeSection identity={clientIdentity} />

      {/* ── Stats Bar ──────────────────────────────────────── */}
      <StatsBar stats={stats} pulse={pulse} />

      {/* ── Command Bar (full width top) ────────────────────── */}
      <CommandBar onSend={sendCommand} />

      {/* ── Error banner ────────────────────────────────────── */}
      {error && (
        <div className="rounded border border-[#ef4444]/30 bg-[#ef4444]/5 px-3 py-2 text-xs text-[#ef4444]/80 font-mono">
          {error}
        </div>
      )}

      {/* ── Main grid: Team Panel + Live Feed ───────────────── */}
      <div className="flex-1 flex flex-col md:flex-row gap-3 min-h-0 md:h-[calc(100vh-200px)]">

        {/* Team Panel (left) */}
        <div className="w-full md:w-[250px] flex-shrink-0 flex flex-col gap-2 overflow-y-auto pr-1 max-h-[300px] md:max-h-none" style={{ scrollbarWidth: 'thin' }}>
          <div className="flex items-center gap-1.5 mb-1">
            <IconPulse />
            <h2 className="text-[10px] text-white/30 font-mono uppercase tracking-widest">
              Team
            </h2>
          </div>

          {isLoading && (
            <div className="text-xs text-white/20 font-mono animate-pulse py-8 text-center">
              Carregando...
            </div>
          )}

          {pulse?.agents.map(agent => (
            <AgentTile key={agent.id} agent={agent} />
          ))}

          {/* Workflow summary */}
          {pulse && (
            <div className="mt-3 pt-3 border-t border-white/[0.04]">
              <p className="text-[10px] text-white/25 font-mono uppercase tracking-widest mb-2">
                Workflows
              </p>
              <div className="flex items-center justify-between text-xs font-mono">
                <span className="text-white/40">Ativos</span>
                <span className="text-[#0ea5e9]">{pulse.workflows.active_count}</span>
              </div>
              <div className="flex items-center justify-between text-xs font-mono mt-1">
                <span className="text-white/40">Hoje</span>
                <span className="text-[#00ff87]/60">{pulse.workflows.completed_today}</span>
              </div>
            </div>
          )}

          {/* Client summary */}
          {pulse && (
            <div className="mt-3 pt-3 border-t border-white/[0.04]">
              <p className="text-[10px] text-white/25 font-mono uppercase tracking-widest mb-2">
                Clientes
              </p>
              <div className="flex items-center justify-between text-xs font-mono">
                <span className="text-white/40">Ativos</span>
                <span className="text-white/70">{pulse.clients.active}</span>
              </div>
              <div className="flex items-center justify-between text-xs font-mono mt-1">
                <span className="text-white/40">MRR</span>
                <span className="text-[#00ff87]/70">
                  R$ {pulse.clients.mrr_total.toLocaleString('pt-BR')}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Live Feed (center) */}
        <div className="flex-1 flex flex-col min-w-0">
          <div className="flex items-center gap-1.5 mb-2">
            <span className="h-1.5 w-1.5 rounded-full bg-[#00ff87] animate-pulse" />
            <h2 className="text-[10px] text-white/30 font-mono uppercase tracking-widest">
              Live Feed
            </h2>
            <span className="text-[10px] text-white/15 font-mono ml-auto">
              {feed.length} eventos
            </span>
          </div>

          <div
            ref={feedContainerRef}
            className="flex-1 overflow-y-auto rounded-lg border border-white/[0.04] bg-white/[0.01] px-3 py-2"
            style={{ scrollbarWidth: 'thin' }}
          >
            {feed.length === 0 && !isLoading && (
              <div className="flex flex-col items-center justify-center h-full gap-2">
                <span className="text-white/15 font-mono text-xs">Aguardando eventos...</span>
                <span className="text-white/10 font-mono text-[10px]">
                  Eventos de tasks, workflows e brain aparecem aqui em tempo real
                </span>
              </div>
            )}

            {feed.map(event => (
              <FeedItem key={event.id} event={event} />
            ))}
          </div>
        </div>

        {/* Right panel (Brain Activity / Content Manager) */}
        <div className="w-full md:w-[340px] flex-shrink-0 flex flex-col min-h-0">
          {/* Tab toggle */}
          <div className="flex items-center gap-1 mb-2">
            <button
              onClick={() => setRightPanel('brain')}
              className={[
                'text-[10px] font-mono px-2.5 py-1 rounded transition-colors uppercase tracking-widest',
                rightPanel === 'brain'
                  ? 'bg-white/10 text-white/70'
                  : 'bg-transparent text-white/25 hover:text-white/40',
              ].join(' ')}
            >
              Brain
            </button>
            <button
              onClick={() => setRightPanel('content')}
              className={[
                'text-[10px] font-mono px-2.5 py-1 rounded transition-colors uppercase tracking-widest',
                rightPanel === 'content'
                  ? 'bg-white/10 text-white/70'
                  : 'bg-transparent text-white/25 hover:text-white/40',
              ].join(' ')}
            >
              Content
            </button>
          </div>

          <div className="flex-1 overflow-y-auto pr-1" style={{ scrollbarWidth: 'thin' }}>
            {rightPanel === 'brain' ? <BrainActivity /> : <ContentManager />}
          </div>
        </div>
      </div>

      {/* ── Footer ──────────────────────────────────────────── */}
      <div className="flex items-center justify-between text-[10px] text-white/15 font-mono pt-1 border-t border-white/[0.03]">
        <span>SPARKLE AIOX // Command Panel SYS-6</span>
        {pulse && (
          <span>
            Ultimo pulse: {new Date(pulse.timestamp).toLocaleTimeString('pt-BR')}
          </span>
        )}
      </div>
    </main>
  )
}
