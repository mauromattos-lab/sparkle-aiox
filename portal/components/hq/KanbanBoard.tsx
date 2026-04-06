'use client'

/**
 * KanbanBoard — Pipeline kanban with columns per stage.
 * Story 2.1: AC2, AC3, AC5, AC9, AC12, AC15
 */

import React from 'react'
import type { PipelineLead } from '@/hooks/useHQData'
import LeadCard from './LeadCard'

// ── Stage definitions (design spec 4.1) ──────────────────────────────────────

export const PIPELINE_STAGES = [
  { id: 'novo',        label: 'Novo',        color: '#6366f1' },
  { id: 'qualificado', label: 'Qualificado', color: '#8b5cf6' },
  { id: 'demo',        label: 'Demo',        color: '#a855f7' },
  { id: 'proposta',    label: 'Proposta',    color: '#c084fc' },
  { id: 'fechado',     label: 'Fechado',     color: '#22c55e' },
  { id: 'perdido',     label: 'Perdido',     color: '#ef4444' },
] as const

// ── Helpers ──────────────────────────────────────────────────────────────────

function isOverdue(followUpDate?: string): boolean {
  if (!followUpDate) return false
  return new Date(followUpDate).getTime() < Date.now()
}

function groupByStage(leads: PipelineLead[]): Record<string, PipelineLead[]> {
  const grouped: Record<string, PipelineLead[]> = {}
  for (const stage of PIPELINE_STAGES) {
    grouped[stage.id] = []
  }

  for (const lead of leads) {
    const stageId = lead.stage?.toLowerCase() ?? 'novo'
    const bucket = grouped[stageId] ?? grouped['novo']
    bucket.push(lead)
  }

  // AC5: leads with overdue follow-up at top of their column
  for (const stageId of Object.keys(grouped)) {
    grouped[stageId].sort((a, b) => {
      const aOverdue = isOverdue(a.follow_up_date) ? 0 : 1
      const bOverdue = isOverdue(b.follow_up_date) ? 0 : 1
      return aOverdue - bOverdue
    })
  }

  return grouped
}

// ── Props ────────────────────────────────────────────────────────────────────

interface KanbanBoardProps {
  leads: PipelineLead[]
  onLeadClick: (lead: PipelineLead) => void
}

// ── Component ────────────────────────────────────────────────────────────────

export default function KanbanBoard({ leads, onLeadClick }: KanbanBoardProps) {
  const grouped = groupByStage(leads)

  return (
    <div
      className="grid gap-3 flex-1 min-h-0 pb-2 kanban-board-grid"
      role="region"
      aria-label="Pipeline kanban board"
    >
      {PIPELINE_STAGES.map((stage) => {
        const stageLeads = grouped[stage.id] ?? []
        return (
          <KanbanColumn
            key={stage.id}
            stage={stage}
            leads={stageLeads}
            onLeadClick={onLeadClick}
          />
        )
      })}
    </div>
  )
}

// ── Column ───────────────────────────────────────────────────────────────────

interface KanbanColumnProps {
  stage: (typeof PIPELINE_STAGES)[number]
  leads: PipelineLead[]
  onLeadClick: (lead: PipelineLead) => void
}

function KanbanColumn({ stage, leads, onLeadClick }: KanbanColumnProps) {
  return (
    <div
      className="flex flex-col gap-2 min-w-[220px] snap-start"
      role="group"
      aria-label={`${stage.label} (${leads.length})`}
    >
      {/* Column header — AC2: label + count, AC3: color border top */}
      <div
        className="glass rounded-lg px-3 py-2 flex items-center justify-between"
        style={{ borderTop: `2px solid ${stage.color}` }}
      >
        <span className="text-[0.8125rem] text-white/70 font-medium">
          {stage.label}
        </span>
        <span
          className="text-[0.6875rem] font-mono px-1.5 py-0.5 rounded-full"
          style={{
            backgroundColor: `${stage.color}20`,
            color: stage.color,
          }}
        >
          {leads.length}
        </span>
      </div>

      {/* Cards — AC9: empty state, AC15: gap 8px */}
      <div className="flex flex-col gap-2 flex-1 overflow-y-auto max-h-[calc(100vh-240px)]">
        {leads.length === 0 ? (
          <p className="text-[0.75rem] text-white/[0.4] text-center py-4">
            Nenhum lead
          </p>
        ) : (
          leads.map((lead) => (
            <LeadCard
              key={lead.id}
              lead={lead}
              onClick={() => onLeadClick(lead)}
            />
          ))
        )}
      </div>
    </div>
  )
}
