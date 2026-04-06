'use client'

/**
 * WorkflowFilters — status tabs + period button group.
 * Story 3.2 — AC4, AC5
 */

import React from 'react'

export type StatusFilter = 'all' | 'running' | 'completed' | 'failed'
export type PeriodFilter = '7d' | '30d' | 'all'

interface WorkflowFiltersProps {
  status: StatusFilter
  period: PeriodFilter
  onStatusChange: (s: StatusFilter) => void
  onPeriodChange: (p: PeriodFilter) => void
}

const STATUS_OPTIONS: { value: StatusFilter; label: string }[] = [
  { value: 'all', label: 'Todos' },
  { value: 'running', label: 'Running' },
  { value: 'completed', label: 'Completed' },
  { value: 'failed', label: 'Failed' },
]

const PERIOD_OPTIONS: { value: PeriodFilter; label: string }[] = [
  { value: '7d', label: '7d' },
  { value: '30d', label: '30d' },
  { value: 'all', label: 'Todos' },
]

export default function WorkflowFilters({
  status,
  period,
  onStatusChange,
  onPeriodChange,
}: WorkflowFiltersProps) {
  return (
    <div className="flex items-center gap-4 flex-wrap">
      {/* Status tabs — AC4 */}
      <div className="flex items-center gap-0 border border-white/[0.08] rounded-lg overflow-hidden">
        {STATUS_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            onClick={() => onStatusChange(opt.value)}
            className={`px-3 py-1.5 text-[0.75rem] font-medium transition-colors duration-100 focus:outline-none focus-visible:ring-1 focus-visible:ring-purple-500 ${
              status === opt.value
                ? 'bg-purple-500/20 text-purple-300 border-b-2 border-purple-500'
                : 'text-white/40 hover:text-white/60 hover:bg-white/[0.04]'
            }`}
            aria-pressed={status === opt.value}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* Period selector — AC5 */}
      <div className="flex items-center gap-0 border border-white/[0.08] rounded-lg overflow-hidden">
        {PERIOD_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            onClick={() => onPeriodChange(opt.value)}
            className={`px-3 py-1.5 text-[0.75rem] font-medium transition-colors duration-100 focus:outline-none focus-visible:ring-1 focus-visible:ring-purple-500 ${
              period === opt.value
                ? 'bg-white/10 text-white/80'
                : 'text-white/40 hover:text-white/60 hover:bg-white/[0.04]'
            }`}
            aria-pressed={period === opt.value}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  )
}
