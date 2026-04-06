'use client'

/**
 * MRRSummary — top bar showing MRR total, active client count, health breakdown.
 * AC2: MRR total formatted, client count, health counts (X green, Y yellow, Z red).
 * AC15: horizontal row >= 960px, stacked below.
 */

import React from 'react'
import { DollarSign, Users, Activity } from 'lucide-react'
import type { ClientRecord } from '@/hooks/useHQData'

interface MRRSummaryProps {
  clients: ClientRecord[]
}

function formatCurrency(value: number): string {
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

export default function MRRSummary({ clients }: MRRSummaryProps) {
  const totalMRR = clients.reduce((sum, c) => sum + (c.mrr ?? 0), 0)
  const activeCount = clients.length
  const greenCount = clients.filter((c) => c.health_status === 'green').length
  const yellowCount = clients.filter((c) => c.health_status === 'yellow').length
  const redCount = clients.filter((c) => c.health_status === 'red').length

  return (
    <div
      className="grid grid-cols-1 sm:grid-cols-3 gap-3"
      aria-label="Resumo MRR e saude dos clientes"
    >
      {/* MRR Total */}
      <div className="bg-white/[0.04] backdrop-blur-xl border border-white/10 rounded-lg p-3 flex items-center gap-3">
        <DollarSign size={16} className="text-green-400 opacity-70 shrink-0" strokeWidth={1.75} aria-hidden="true" />
        <div className="flex flex-col gap-0.5">
          <span className="text-[0.6875rem] text-white/40 uppercase tracking-wide font-medium">MRR Total</span>
          <span className="text-[1.125rem] font-bold text-white leading-none tracking-tight">
            {formatCurrency(totalMRR)}
          </span>
        </div>
      </div>

      {/* Active clients */}
      <div className="bg-white/[0.04] backdrop-blur-xl border border-white/10 rounded-lg p-3 flex items-center gap-3">
        <Users size={16} className="text-purple-400 opacity-70 shrink-0" strokeWidth={1.75} aria-hidden="true" />
        <div className="flex flex-col gap-0.5">
          <span className="text-[0.6875rem] text-white/40 uppercase tracking-wide font-medium">Clientes Ativos</span>
          <span className="text-[1.125rem] font-bold text-white leading-none tracking-tight">
            {activeCount}
          </span>
        </div>
      </div>

      {/* Health breakdown */}
      <div className="bg-white/[0.04] backdrop-blur-xl border border-white/10 rounded-lg p-3 flex items-center gap-3">
        <Activity size={16} className="text-cyan-400 opacity-70 shrink-0" strokeWidth={1.75} aria-hidden="true" />
        <div className="flex flex-col gap-0.5">
          <span className="text-[0.6875rem] text-white/40 uppercase tracking-wide font-medium">Saude</span>
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-[#22c55e]" aria-hidden="true" />
              <span className="text-[0.8125rem] font-semibold text-white/70">{greenCount}</span>
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-[#eab308]" aria-hidden="true" />
              <span className="text-[0.8125rem] font-semibold text-white/70">{yellowCount}</span>
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-[#ef4444]" aria-hidden="true" />
              <span className="text-[0.8125rem] font-semibold text-white/70">{redCount}</span>
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
