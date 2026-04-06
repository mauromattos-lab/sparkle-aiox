'use client'

/**
 * LeadCard — Individual lead card for pipeline kanban.
 * Story 2.1: AC4, AC5, AC14, AC15
 */

import React from 'react'
import { AlertTriangle } from 'lucide-react'
import type { PipelineLead } from '@/hooks/useHQData'

// ── BANT helpers ─────────────────────────────────────────────────────────────

type BantLevel = 'alto' | 'medio' | 'baixo'

const BANT_CONFIG: Record<BantLevel, { label: string; letter: string; color: string }> = {
  alto:  { label: 'Alto',  letter: 'A', color: 'text-green-400 bg-green-400/20' },
  medio: { label: 'Medio', letter: 'M', color: 'text-yellow-400 bg-yellow-400/20' },
  baixo: { label: 'Baixo', letter: 'B', color: 'text-red-400 bg-red-400/20' },
}

function normalizeBant(score: unknown): BantLevel {
  if (typeof score === 'string') {
    const lower = score.toLowerCase()
    if (lower === 'alto' || lower === 'high' || lower === 'a') return 'alto'
    if (lower === 'medio' || lower === 'medium' || lower === 'm') return 'medio'
    return 'baixo'
  }
  if (typeof score === 'number') {
    if (score >= 7) return 'alto'
    if (score >= 4) return 'medio'
    return 'baixo'
  }
  return 'medio'
}

// ── Date helpers ─────────────────────────────────────────────────────────────

function formatRelativeDate(dateStr?: string): string {
  if (!dateStr) return ''
  try {
    const date = new Date(dateStr)
    const now = Date.now()
    const diffMs = now - date.getTime()
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60))

    if (diffDays < 0) {
      const futureDays = Math.abs(diffDays)
      if (futureDays === 0) return 'hoje'
      if (futureDays === 1) return 'amanha'
      return `em ${futureDays} dias`
    }
    if (diffDays === 0) {
      if (diffHours < 1) return 'agora'
      return `ha ${diffHours}h`
    }
    if (diffDays === 1) return 'ha 1 dia'
    return `ha ${diffDays} dias`
  } catch {
    return dateStr
  }
}

function isOverdue(followUpDate?: string): boolean {
  if (!followUpDate) return false
  return new Date(followUpDate).getTime() < Date.now()
}

// ── Props ────────────────────────────────────────────────────────────────────

interface LeadCardProps {
  lead: PipelineLead
  onClick: () => void
}

// ── Component ────────────────────────────────────────────────────────────────

export default function LeadCard({ lead, onClick }: LeadCardProps) {
  const overdue = isOverdue(lead.follow_up_date)
  const bant = normalizeBant(lead.bant_score)
  const bantConfig = BANT_CONFIG[bant]
  const lastContact = formatRelativeDate(lead.last_contact as string | undefined)
  const followUp = formatRelativeDate(lead.follow_up_date)

  return (
    <div
      className={[
        // AC15: glass card style, density padding
        'bg-white/[0.04] backdrop-blur-xl border rounded-lg p-3 cursor-pointer',
        'transition-all duration-150',
        // AC14: hover lift + border glow
        'hover:-translate-y-[1px] hover:border-white/20',
        // AC5: overdue visual
        overdue
          ? 'border-red-500/40 bg-red-500/[0.1]'
          : 'border-white/10',
      ]
        .filter(Boolean)
        .join(' ')}
      onClick={onClick}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onClick() }}
      tabIndex={0}
      role="button"
      aria-label={`Lead: ${lead.name}${lead.empresa ? ` - ${lead.empresa}` : ''}`}
    >
      {/* Row 1: name + BANT badge */}
      <div className="flex items-center justify-between gap-2 mb-1">
        <span className="text-[0.8125rem] text-white/80 font-medium truncate leading-tight">
          {lead.name}
        </span>
        <span
          className={`text-[0.625rem] font-mono font-bold px-1.5 py-0.5 rounded-full shrink-0 ${bantConfig.color}`}
        >
          {bantConfig.letter}
        </span>
      </div>

      {/* Row 2: company */}
      {lead.empresa && (
        <p className="text-[0.6875rem] text-white/40 truncate leading-tight mb-1.5">
          {lead.empresa}
        </p>
      )}

      {/* Row 3: follow-up */}
      {lead.follow_up_date && (
        <div className="flex items-center gap-1 mb-0.5">
          {overdue && (
            <AlertTriangle
              size={11}
              className="text-red-400 shrink-0"
              strokeWidth={2}
              aria-label="Follow-up vencido"
            />
          )}
          <span
            className={`text-[0.6875rem] leading-tight ${
              overdue ? 'text-red-400 font-medium' : 'text-white/40'
            }`}
          >
            Follow-up: {followUp}
          </span>
        </div>
      )}

      {/* Row 4: last contact */}
      {lastContact && (
        <p className="text-[0.625rem] text-white/30 leading-tight">
          Ultimo: {lastContact}
        </p>
      )}
    </div>
  )
}
