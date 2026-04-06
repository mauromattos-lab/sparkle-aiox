'use client'

/**
 * ClientCard — individual client card in the Clients grid.
 * AC4: name, empresa/service, plan badge, MRR, health status, last interaction (relative).
 * AC6: health text + color for accessibility.
 * AC7: click opens DetailPanel with full info.
 * AC17: hover lift + border glow.
 * AC18: glass card style, density padding/text.
 */

import React from 'react'
import type { ClientRecord } from '@/hooks/useHQData'
import StatusBadge from '@/components/hq/StatusBadge'

interface ClientCardProps {
  client: ClientRecord
  onClick: () => void
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function formatMRR(value?: number): string {
  if (value == null) return 'R$ 0/mes'
  return `R$ ${value.toLocaleString('pt-BR')}/mes`
}

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

const SERVICE_BADGE_COLORS: Record<string, string> = {
  zenya: 'bg-purple-500/20 text-purple-400',
  trafego: 'bg-cyan-500/20 text-cyan-400',
  ambos: 'bg-blue-500/20 text-blue-400',
}

function getServiceBadgeColor(serviceType?: string): string {
  if (!serviceType) return 'bg-white/[0.08] text-white/50'
  return SERVICE_BADGE_COLORS[serviceType.toLowerCase()] ?? 'bg-white/[0.08] text-white/50'
}

// ── Component ───────────────────────────────────────────────────────────────

export default function ClientCard({ client, onClick }: ClientCardProps) {
  return (
    <div
      className={[
        'bg-white/[0.04] backdrop-blur-xl border border-white/10 rounded-lg',
        'p-3 flex flex-col gap-2 cursor-pointer',
        'transition-all duration-150',
        'hover:-translate-y-[1px] hover:border-white/20',
      ].join(' ')}
      onClick={onClick}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onClick() }}
      tabIndex={0}
      role="button"
      aria-label={`Cliente ${client.name}`}
    >
      {/* Top row: name + health */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-col gap-0.5 min-w-0 flex-1">
          <span className="text-[0.8125rem] font-semibold text-white/80 leading-snug truncate">
            {client.name}
          </span>
          {client.empresa && (
            <span className="text-[0.6875rem] text-white/40 truncate">
              {client.empresa}
            </span>
          )}
        </div>
        <StatusBadge status={client.health_status} size="sm" showLabel={true} />
      </div>

      {/* Badges row: plan + service */}
      <div className="flex items-center gap-1.5 flex-wrap">
        {client.plan && (
          <span className="text-[0.625rem] font-mono px-1.5 py-0.5 rounded bg-white/[0.08] text-white/60">
            {client.plan}
          </span>
        )}
        {client.service_type && (
          <span className={`text-[0.625rem] font-mono px-1.5 py-0.5 rounded ${getServiceBadgeColor(client.service_type)}`}>
            {client.service_type}
          </span>
        )}
      </div>

      {/* Bottom row: MRR + last interaction */}
      <div className="flex items-center justify-between mt-auto pt-1 border-t border-white/[0.04]">
        <span className="text-[0.8125rem] font-bold text-white/70">
          {formatMRR(client.mrr)}
        </span>
        <span className="text-[0.625rem] text-white/30 font-mono">
          {relativeTime(client.last_interaction)}
        </span>
      </div>
    </div>
  )
}
