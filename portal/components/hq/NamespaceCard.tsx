'use client'

/**
 * NamespaceCard — card individual de namespace do Brain.
 * AC4 (Story 3.3): nome, total, barra de progresso, contadores, hover.
 */

import React from 'react'
import type { BrainNamespaceStat } from '@/hooks/useHQData'

interface NamespaceCardProps {
  stat: BrainNamespaceStat
  onClick?: () => void
}

export default function NamespaceCard({ stat, onClick }: NamespaceCardProps) {
  const { namespace, total, approved, pending, rejected, review } = stat
  const pendingTotal = pending + review
  const approvedPct = total > 0 ? (approved / total) * 100 : 0
  const pendingPct = total > 0 ? (pendingTotal / total) * 100 : 0

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onClick?.() }}
      className="bg-white/[0.04] backdrop-blur-xl border border-white/10 rounded-lg p-4 flex flex-col gap-2 hover:-translate-y-[1px] hover:border-white/20 transition-all duration-150 cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-purple-500"
      aria-label={`Namespace ${namespace}: ${total} chunks`}
    >
      {/* Namespace name + total */}
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-white/80 truncate">{namespace}</span>
        <span className="text-xl font-bold text-purple-300 ml-2 shrink-0">{total}</span>
      </div>

      {/* Empty namespace */}
      {total === 0 && (
        <span className="text-[0.75rem] text-white/40">Namespace vazio</span>
      )}

      {/* Progress bar */}
      {total > 0 && (
        <div className="flex bg-white/10 rounded-full h-1.5 overflow-hidden" aria-hidden="true">
          <div
            className="bg-purple-500 h-full rounded-l-full"
            style={{ width: `${approvedPct}%` }}
          />
          <div
            className="bg-yellow-400 h-full"
            style={{ width: `${pendingPct}%` }}
          />
        </div>
      )}

      {/* Counters */}
      {total > 0 && (
        <div className="flex flex-wrap gap-x-3 gap-y-0.5">
          <span className="text-xs text-green-400">✓ {approved} aprovados</span>
          {pendingTotal > 0 && (
            <span className="text-xs text-yellow-400">⏳ {pendingTotal} pendentes</span>
          )}
          {rejected > 0 && (
            <span className="text-xs text-red-400">✗ {rejected} rejeitados</span>
          )}
        </div>
      )}
    </div>
  )
}
