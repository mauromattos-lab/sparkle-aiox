'use client'

/**
 * PipelineFilters — Period and sort filters for pipeline view.
 * Story 2.1: AC7
 */

import React from 'react'

// ── Types ────────────────────────────────────────────────────────────────────

export type PeriodFilter = '7d' | '30d' | 'all'
export type SortOption = 'date' | 'score'

interface PipelineFiltersProps {
  period: PeriodFilter
  sort: SortOption
  onPeriodChange: (period: PeriodFilter) => void
  onSortChange: (sort: SortOption) => void
}

// ── Filter options ───────────────────────────────────────────────────────────

const PERIODS: { value: PeriodFilter; label: string }[] = [
  { value: '7d',  label: '7d' },
  { value: '30d', label: '30d' },
  { value: 'all', label: 'All' },
]

const SORTS: { value: SortOption; label: string }[] = [
  { value: 'date',  label: 'Data' },
  { value: 'score', label: 'Score' },
]

// ── Component ────────────────────────────────────────────────────────────────

export default function PipelineFilters({
  period,
  sort,
  onPeriodChange,
  onSortChange,
}: PipelineFiltersProps) {
  return (
    <div className="flex items-center gap-3 flex-wrap" role="toolbar" aria-label="Pipeline filters">
      {/* Period filter */}
      <div className="flex items-center gap-1">
        <span className="text-[0.6875rem] text-white/30 mr-1">Periodo:</span>
        {PERIODS.map((p) => (
          <button
            key={p.value}
            onClick={() => onPeriodChange(p.value)}
            className={[
              'text-[0.6875rem] font-mono px-2 py-1 rounded-md transition-colors duration-150',
              period === p.value
                ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
                : 'text-white/40 hover:text-white/60 hover:bg-white/[0.04] border border-transparent',
            ].join(' ')}
            aria-pressed={period === p.value}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Sort */}
      <div className="flex items-center gap-1">
        <span className="text-[0.6875rem] text-white/30 mr-1">Ordenar:</span>
        {SORTS.map((s) => (
          <button
            key={s.value}
            onClick={() => onSortChange(s.value)}
            className={[
              'text-[0.6875rem] font-mono px-2 py-1 rounded-md transition-colors duration-150',
              sort === s.value
                ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
                : 'text-white/40 hover:text-white/60 hover:bg-white/[0.04] border border-transparent',
            ].join(' ')}
            aria-pressed={sort === s.value}
          >
            {s.label}
          </button>
        ))}
      </div>
    </div>
  )
}
