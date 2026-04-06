'use client'

/**
 * BrainStats — 4 KPI cards para status de curadoria do Brain.
 * AC3 (Story 3.3): Total Chunks, Aprovados, Pendentes, Rejeitados.
 */

import React from 'react'
import { Brain, CheckCircle, Clock, XCircle } from 'lucide-react'
import type { BrainStats as BrainStatsData } from '@/hooks/useHQData'

interface BrainStatsProps {
  stats: BrainStatsData
}

interface KPICardProps {
  label: string
  value: number
  icon: React.ElementType
  colorClass: string
}

function BrainKPICard({ label, value, icon: Icon, colorClass }: KPICardProps) {
  return (
    <div className="bg-white/[0.04] backdrop-blur-xl border border-white/10 rounded-lg p-3 flex flex-col gap-1">
      <div className="flex items-center gap-1.5">
        <Icon size={14} className={colorClass} strokeWidth={1.75} aria-hidden="true" />
        <span className="text-[0.75rem] text-white/50 uppercase tracking-wide font-medium">
          {label}
        </span>
      </div>
      <span className={`text-2xl font-bold ${colorClass}`}>{value}</span>
    </div>
  )
}

export default function BrainStats({ stats }: BrainStatsProps) {
  return (
    <div className="grid grid-cols-2 xl:grid-cols-4 gap-3" aria-label="Brain KPI cards">
      <BrainKPICard
        label="Total Chunks"
        value={stats.total}
        icon={Brain}
        colorClass="text-white"
      />
      <BrainKPICard
        label="Aprovados"
        value={stats.approved}
        icon={CheckCircle}
        colorClass="text-green-400"
      />
      <BrainKPICard
        label="Pendentes"
        value={stats.pending + stats.review}
        icon={Clock}
        colorClass="text-yellow-400"
      />
      <BrainKPICard
        label="Rejeitados"
        value={stats.rejected}
        icon={XCircle}
        colorClass="text-red-400"
      />
    </div>
  )
}
