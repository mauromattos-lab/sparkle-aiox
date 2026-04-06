'use client'

/**
 * CurationBadge — badge de status de curadoria do Brain.
 * Mapeia curation_status (approved/pending/review/rejected) para cores.
 * Story 3.3: complementa StatusBadge (que usa health: green/yellow/red).
 */

import React from 'react'

export type CurationStatus = 'pending' | 'approved' | 'rejected' | 'review'

interface CurationBadgeProps {
  status: CurationStatus
  size?: 'sm' | 'md'
}

const STATUS_CONFIG: Record<CurationStatus, { dot: string; label: string; text: string }> = {
  approved: { dot: '#22c55e', label: 'Aprovado',  text: 'text-green-400' },
  pending:  { dot: '#eab308', label: 'Pendente',  text: 'text-yellow-400' },
  review:   { dot: '#eab308', label: 'Revisão',   text: 'text-yellow-400' },
  rejected: { dot: '#ef4444', label: 'Rejeitado', text: 'text-red-400' },
}

export default function CurationBadge({ status, size = 'sm' }: CurationBadgeProps) {
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG['pending']
  const dotPx = size === 'sm' ? 7 : 10

  return (
    <span className="inline-flex items-center gap-1.5 shrink-0">
      <span
        className="rounded-full shrink-0"
        style={{
          width: dotPx,
          height: dotPx,
          backgroundColor: cfg.dot,
          boxShadow: `0 0 5px ${cfg.dot}50`,
        }}
        aria-hidden="true"
      />
      <span className={`text-[0.6875rem] font-medium ${cfg.text}`}>
        {cfg.label}
      </span>
    </span>
  )
}
