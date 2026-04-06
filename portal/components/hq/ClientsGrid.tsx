'use client'

/**
 * ClientsGrid — responsive grid container for ClientCards.
 * AC3: CSS Grid with auto-fill, minmax(280px, 1fr), gap 12px.
 * AC7: click opens DetailPanel with full client info.
 * AC15: responsive columns (3-4 at >=1200, 2 at 960-1199, 1 at <960).
 */

import React from 'react'
import type { ClientRecord } from '@/hooks/useHQData'
import ClientCard from '@/components/hq/ClientCard'
import StatusBadge from '@/components/hq/StatusBadge'
import { useDetailPanel } from '@/components/hq/DetailPanelContext'

interface ClientsGridProps {
  clients: ClientRecord[]
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function formatAbsoluteDate(dateStr?: string): string {
  if (!dateStr) return '--'
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return '--'
  return d.toLocaleString('pt-BR')
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

function formatMRR(value?: number): string {
  if (value == null) return 'R$ 0/mes'
  return `R$ ${value.toLocaleString('pt-BR')}/mes`
}

// ── Detail Panel content ────────────────────────────────────────────────────

function ClientDetailContent({ client }: { client: ClientRecord }) {
  return (
    <div className="flex flex-col gap-3 p-4">
      <div className="flex items-center gap-2">
        <span className="text-[0.9375rem] font-semibold text-white/80">{client.name}</span>
        <StatusBadge status={client.health_status} size="md" showLabel={true} />
      </div>

      <div className="flex flex-col gap-2 text-[0.8125rem]">
        {client.empresa && (
          <div><span className="text-white/40">Empresa:</span> <span className="text-white/70">{client.empresa}</span></div>
        )}
        {client.plan && (
          <div><span className="text-white/40">Plano:</span> <span className="text-white/70">{client.plan}</span></div>
        )}
        <div><span className="text-white/40">MRR:</span> <span className="text-white/70">{formatMRR(client.mrr)}</span></div>

        {client.health_reason && (
          <div><span className="text-white/40">Razao health:</span> <span className="text-white/50">{client.health_reason}</span></div>
        )}

        <div>
          <span className="text-white/40">Ultima interacao:</span>{' '}
          <span className="text-white/50 font-mono text-[0.6875rem]">
            {formatAbsoluteDate(client.last_interaction)} ({relativeTime(client.last_interaction)})
          </span>
        </div>

        {client.service_type && (
          <div><span className="text-white/40">Servico:</span> <span className="text-white/70">{client.service_type}</span></div>
        )}

        {client.onboarding_status && (
          <div><span className="text-white/40">Onboarding:</span> <span className="text-white/70">{client.onboarding_status}</span></div>
        )}

        <div>
          <span className="text-white/40">Zenya:</span>{' '}
          <span className={client.zenya_active ? 'text-green-400' : 'text-white/30'}>
            {client.zenya_active ? 'Ativa' : 'Inativa'}
          </span>
        </div>

        {client.notes && (
          <div className="mt-2 pt-2 border-t border-white/[0.06]">
            <span className="text-white/40">Notas:</span>
            <p className="text-white/50 text-[0.75rem] leading-relaxed mt-1">{client.notes}</p>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Grid component ──────────────────────────────────────────────────────────

export default function ClientsGrid({ clients }: ClientsGridProps) {
  const { openPanel } = useDetailPanel()

  return (
    <div
      className="grid gap-3"
      style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))' }}
      role="list"
      aria-label="Grid de clientes"
    >
      {clients.map((client) => (
        <div key={client.id} role="listitem">
          <ClientCard
            client={client}
            onClick={() => openPanel(<ClientDetailContent client={client} />)}
          />
        </div>
      ))}
    </div>
  )
}
