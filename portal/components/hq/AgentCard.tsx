'use client'

/**
 * AgentCard — individual agent card in the Agents grid.
 * Story 3.1 — AC3, AC4, AC7, AC12, AC17
 *
 * AC3:  icon, name, agent_type, status bullet, last task, capabilities count
 * AC4:  status visual: working=green pulse, idle=grey, error=red
 * AC7:  click opens DetailPanel
 * AC12: badge colorido por agent_type
 */

import React from 'react'
import { Bot, Cpu, Users, Zap } from 'lucide-react'
import type { AgentRecord } from '@/hooks/useHQData'

interface AgentCardProps {
  agent: AgentRecord
  onClick: () => void
}

// ── Helpers ──────────────────────────────────────────────────────────────────

/** Relative time string from ISO timestamp */
function relativeTime(dateStr?: string): string {
  if (!dateStr) return '--'
  const now = Date.now()
  const then = new Date(dateStr).getTime()
  if (isNaN(then)) return '--'

  const diffMs = now - then
  if (diffMs < 0) return 'agora'

  const minutes = Math.floor(diffMs / 60000)
  if (minutes < 1) return 'agora'
  if (minutes < 60) return `ha ${minutes}min`

  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `ha ${hours}h`

  const days = Math.floor(hours / 24)
  if (days < 30) return `ha ${days} dia${days !== 1 ? 's' : ''}`

  const months = Math.floor(days / 30)
  return `ha ${months} mes${months !== 1 ? 'es' : ''}`
}

/** Icon component by agent_type */
function AgentIcon({ agentType }: { agentType: string }) {
  const cls = 'text-white/40'
  switch (agentType) {
    case 'system':
      return <Cpu size={20} className={cls} strokeWidth={1.5} />
    case 'client-facing':
      return <Users size={20} className={cls} strokeWidth={1.5} />
    case 'specialist':
      return <Zap size={20} className={cls} strokeWidth={1.5} />
    default:
      return <Bot size={20} className={cls} strokeWidth={1.5} />
  }
}

/** Status bullet: working=green pulse-glow, idle=grey, error=red */
function StatusBullet({ status }: { status: AgentRecord['status'] }) {
  if (status === 'working') {
    return (
      <span
        className="w-2 h-2 rounded-full bg-green-400 animate-pulse-glow flex-shrink-0"
        title="working"
        aria-label="Ativo"
      />
    )
  }
  if (status === 'error') {
    return (
      <span
        className="w-2 h-2 rounded-full bg-red-400 flex-shrink-0"
        title="error"
        aria-label="Erro"
      />
    )
  }
  // idle + any unknown status
  return (
    <span
      className="w-2 h-2 rounded-full bg-white/20 flex-shrink-0"
      title="idle"
      aria-label="Ocioso"
    />
  )
}

/** AC12: badge colorido por agent_type */
function AgentTypeBadge({ agentType }: { agentType: string }) {
  const styles: Record<string, string> = {
    system: 'bg-violet-600/20 text-violet-400',
    'client-facing': 'bg-blue-600/20 text-blue-400',
    specialist: 'bg-green-600/20 text-green-400',
  }
  const style = styles[agentType]
  if (!style) return null

  return (
    <span className={`text-[0.5625rem] font-mono px-1.5 py-0.5 rounded ${style}`}>
      {agentType}
    </span>
  )
}

// ── Component ────────────────────────────────────────────────────────────────

export default function AgentCard({ agent, onClick }: AgentCardProps) {
  const lastTaskTime =
    agent.last_action_at ?? agent.last_task?.timestamp

  return (
    <div
      className={[
        'bg-white/[0.04] backdrop-blur-xl border border-white/[0.08] rounded-xl',
        'p-4 flex flex-col gap-3 cursor-pointer',
        'transition-all duration-150',
        'hover:bg-white/[0.08] hover:border-white/[0.14] hover:-translate-y-[1px]',
      ].join(' ')}
      onClick={onClick}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onClick() }}
      tabIndex={0}
      role="button"
      aria-label={`Agente ${agent.display_name}`}
    >
      {/* Top row: icon + name + status bullet */}
      <div className="flex items-start gap-3">
        {/* Icon container */}
        <div className="w-10 h-10 rounded-lg bg-white/[0.06] border border-white/[0.08] flex items-center justify-center flex-shrink-0">
          <AgentIcon agentType={agent.agent_type} />
        </div>

        {/* Name + type */}
        <div className="flex flex-col gap-0.5 min-w-0 flex-1">
          <span className="text-[0.875rem] font-semibold text-white leading-snug truncate">
            {agent.display_name}
          </span>
          <span className="text-[0.6875rem] text-white/50 truncate">
            {agent.agent_type}
          </span>
        </div>

        {/* Status bullet */}
        <StatusBullet status={agent.status} />
      </div>

      {/* Last task */}
      {(agent.last_action ?? agent.last_task) && (
        <div className="text-[0.6875rem] text-white/40 font-mono leading-relaxed">
          Ultima task:{' '}
          <span className="text-white/60">
            {agent.last_action ?? agent.last_task?.type ?? '—'}
          </span>
          {lastTaskTime && (
            <span className="text-white/30 ml-1">
              {relativeTime(lastTaskTime)}
            </span>
          )}
        </div>
      )}

      {/* Bottom row: capabilities count + type badge */}
      <div className="flex items-center justify-between mt-auto">
        {agent.capabilities_count != null ? (
          <span className="text-[0.625rem] text-white/30">
            {agent.capabilities_count} capabilities
          </span>
        ) : (
          <span />
        )}
        <AgentTypeBadge agentType={agent.agent_type} />
      </div>
    </div>
  )
}
