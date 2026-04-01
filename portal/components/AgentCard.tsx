'use client'

import { AgentStatus, AgentView } from '@/hooks/useAgentWorkItems'

interface AgentCardProps {
  agent: AgentView
}

const STATUS_CONFIG: Record<AgentStatus, {
  label: string
  bgColor: string
  borderColor: string
  glowColor: string
  dotColor: string
  animate: boolean
}> = {
  idle: {
    label: 'Standby',
    bgColor: 'bg-zinc-900',
    borderColor: 'border-zinc-700',
    glowColor: '',
    dotColor: 'bg-zinc-500',
    animate: false,
  },
  active: {
    label: 'Executando',
    bgColor: 'bg-purple-950/40',
    borderColor: 'border-purple-500/60',
    glowColor: 'shadow-[0_0_20px_rgba(168,85,247,0.35)]',
    dotColor: 'bg-purple-400',
    animate: true,
  },
  blocked: {
    label: 'Aguardando',
    bgColor: 'bg-yellow-950/30',
    borderColor: 'border-yellow-500/50',
    glowColor: 'shadow-[0_0_16px_rgba(234,179,8,0.25)]',
    dotColor: 'bg-yellow-400',
    animate: false,
  },
  done: {
    label: 'Concluido',
    bgColor: 'bg-emerald-950/30',
    borderColor: 'border-emerald-500/50',
    glowColor: 'shadow-[0_0_16px_rgba(16,185,129,0.25)]',
    dotColor: 'bg-emerald-400',
    animate: false,
  },
  error: {
    label: 'Erro',
    bgColor: 'bg-red-950/40',
    borderColor: 'border-red-500/60',
    glowColor: 'shadow-[0_0_24px_rgba(239,68,68,0.4)]',
    dotColor: 'bg-red-500',
    animate: false,
  },
}

function formatElapsed(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}min`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`
  return `${Math.floor(seconds / 86400)}d`
}

export default function AgentCard({ agent }: AgentCardProps) {
  const cfg = STATUS_CONFIG[agent.status]

  return (
    <div
      className={[
        'rounded-xl border p-4 transition-all duration-300',
        'min-h-[140px] flex flex-col gap-2',
        cfg.bgColor,
        cfg.borderColor,
        cfg.glowColor,
      ].join(' ')}
    >
      {/* Header: agente + dot de status */}
      <div className="flex items-center justify-between">
        <span className="text-sm font-mono font-semibold text-white/90">
          {agent.agentId}
        </span>
        <div className="flex items-center gap-1.5">
          <span
            className={[
              'h-2.5 w-2.5 rounded-full',
              cfg.dotColor,
              cfg.animate ? 'animate-pulse' : '',
            ].join(' ')}
          />
          <span className="text-xs text-white/50 uppercase tracking-wide">
            {cfg.label}
          </span>
        </div>
      </div>

      {/* Artifact atual */}
      {agent.currentItem ? (
        <div className="flex-1">
          <p className="text-xs text-white/40 mb-0.5">Artefato</p>
          <p className="text-sm text-white/80 font-medium leading-snug line-clamp-2">
            {agent.currentItem.artifact_id ?? agent.currentItem.output_type ?? '—'}
          </p>
          {agent.currentItem.notes && (
            <p className="text-xs text-white/40 mt-1 line-clamp-1">
              {agent.currentItem.notes}
            </p>
          )}
        </div>
      ) : (
        <div className="flex-1 flex items-center">
          <p className="text-xs text-white/30 italic">Sem item ativo</p>
        </div>
      )}

      {/* Footer: tempo + contagem de itens */}
      <div className="flex items-center justify-between pt-1 border-t border-white/5">
        <span className="text-xs text-white/35">
          {agent.itemsLast24h.length} item{agent.itemsLast24h.length !== 1 ? 's' : ''} / 24h
        </span>
        {agent.currentItem && (
          <span className="text-xs text-white/35 font-mono">
            {formatElapsed(agent.timeInCurrentStatus)}
          </span>
        )}
      </div>
    </div>
  )
}
