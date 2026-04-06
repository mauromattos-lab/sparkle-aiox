'use client'

/**
 * Pipeline Page — Story 2.1
 * Kanban view of sales pipeline with BANT scores, follow-up indicators, filters.
 * AC1-AC16
 */

import React, { useMemo, useState } from 'react'
import { Filter, AlertCircle } from 'lucide-react'
import { usePipeline, type PipelineLead } from '@/hooks/useHQData'
import { useDetailPanel } from '@/components/hq/DetailPanelContext'
import KanbanBoard, { PIPELINE_STAGES } from '@/components/hq/KanbanBoard'
import PipelineFilters, { type PeriodFilter, type SortOption } from '@/components/hq/PipelineFilters'
import { PipelineSkeleton } from '@/components/hq/LoadingSkeleton'
import EmptyState from '@/components/hq/EmptyState'

// ── BANT normalization (shared with LeadCard) ────────────────────────────────

function bantScore(score: unknown): number {
  if (typeof score === 'number') return score
  if (typeof score === 'string') {
    const lower = score.toLowerCase()
    if (lower === 'alto' || lower === 'high' || lower === 'a') return 9
    if (lower === 'medio' || lower === 'medium' || lower === 'm') return 5
    return 2
  }
  return 5
}

// ── Lead detail panel content ────────────────────────────────────────────────

function LeadDetailContent({ lead }: { lead: PipelineLead }) {
  const stage = PIPELINE_STAGES.find((s) => s.id === (lead.stage?.toLowerCase() ?? 'novo'))

  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="flex items-center gap-2">
        <Filter size={16} className="text-purple-400" strokeWidth={1.75} />
        <span className="text-[0.9375rem] font-semibold text-white/80">Detalhes do Lead</span>
      </div>

      <div className="flex flex-col gap-2.5 text-[0.8125rem]">
        <div>
          <span className="text-white/40">Nome:</span>{' '}
          <span className="text-white/80 font-medium">{lead.name}</span>
        </div>

        {lead.empresa && (
          <div>
            <span className="text-white/40">Empresa:</span>{' '}
            <span className="text-white/70">{lead.empresa}</span>
          </div>
        )}

        {lead.phone && (
          <div>
            <span className="text-white/40">Telefone:</span>{' '}
            <span className="text-white/50 font-mono text-[0.6875rem]">{lead.phone}</span>
          </div>
        )}

        {lead.source && (
          <div>
            <span className="text-white/40">Canal de entrada:</span>{' '}
            <span className="text-white/70">{lead.source}</span>
          </div>
        )}

        {stage && (
          <div>
            <span className="text-white/40">Estagio:</span>{' '}
            <span className="font-mono text-[0.75rem]" style={{ color: stage.color }}>
              {stage.label}
            </span>
          </div>
        )}

        {lead.bant_score != null && (
          <div>
            <span className="text-white/40">BANT Score:</span>{' '}
            <span className="text-white/70">{String(lead.bant_score)}</span>
          </div>
        )}

        {lead.follow_up_date && (
          <div>
            <span className="text-white/40">Proximo follow-up:</span>{' '}
            <span
              className={`font-mono text-[0.6875rem] ${
                new Date(lead.follow_up_date).getTime() < Date.now()
                  ? 'text-red-400 font-medium'
                  : 'text-white/50'
              }`}
            >
              {lead.follow_up_date}
            </span>
          </div>
        )}

        {lead.last_contact && (
          <div>
            <span className="text-white/40">Ultimo contato:</span>{' '}
            <span className="text-white/50 font-mono text-[0.6875rem]">
              {lead.last_contact}
            </span>
          </div>
        )}

        {lead.notes && (
          <div className="mt-2 pt-2 border-t border-white/[0.06]">
            <span className="text-white/40 block mb-1">Notas:</span>
            <p className="text-white/50 text-[0.75rem] leading-relaxed whitespace-pre-wrap">
              {lead.notes}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Main page ────────────────────────────────────────────────────────────────

export default function PipelinePage() {
  const { data, error, isLoading } = usePipeline()
  const { openPanel } = useDetailPanel()

  const [period, setPeriod] = useState<PeriodFilter>('all')
  const [sort, setSort] = useState<SortOption>('date')

  // Normalize leads array
  const rawLeads: PipelineLead[] = useMemo(() => {
    if (Array.isArray(data?.leads)) return data!.leads
    if (Array.isArray(data)) return data as unknown as PipelineLead[]
    return []
  }, [data])

  // AC7: client-side filters
  const filteredLeads = useMemo(() => {
    let leads = [...rawLeads]

    // Period filter on created_at or updated_at
    if (period !== 'all') {
      const days = period === '7d' ? 7 : 30
      const cutoff = Date.now() - days * 24 * 60 * 60 * 1000
      leads = leads.filter((l) => {
        const dateStr = (l.updated_at as string) || (l.created_at as string) || ''
        if (!dateStr) return true // keep leads without dates
        return new Date(dateStr).getTime() >= cutoff
      })
    }

    // Sort
    if (sort === 'score') {
      leads.sort((a, b) => bantScore(b.bant_score) - bantScore(a.bant_score))
    } else {
      leads.sort((a, b) => {
        const aDate = (a.updated_at as string) || (a.created_at as string) || ''
        const bDate = (b.updated_at as string) || (b.created_at as string) || ''
        return new Date(bDate).getTime() - new Date(aDate).getTime()
      })
    }

    return leads
  }, [rawLeads, period, sort])

  // AC8: count active leads (exclude "perdido")
  const activeCount = filteredLeads.filter(
    (l) => (l.stage?.toLowerCase() ?? 'novo') !== 'perdido'
  ).length

  // AC6: open detail panel on lead click
  function handleLeadClick(lead: PipelineLead) {
    openPanel(<LeadDetailContent lead={lead} />)
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="hq-page-enter hq-density flex flex-col gap-4 h-full">
      {/* AC8: Title with icon + active lead count */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <Filter size={20} className="text-purple-400 shrink-0" strokeWidth={1.75} aria-hidden="true" />
          <div>
            <h1 className="text-[0.9375rem] font-semibold text-white/80 leading-tight">
              Pipeline
              {!isLoading && (
                <span className="text-white/30 font-mono text-[0.75rem] ml-2">
                  {activeCount} ativo{activeCount !== 1 ? 's' : ''}
                </span>
              )}
            </h1>
          </div>
        </div>

        {/* AC7: Filters */}
        <PipelineFilters
          period={period}
          sort={sort}
          onPeriodChange={setPeriod}
          onSortChange={setSort}
        />
      </div>

      {/* Content */}
      {isLoading ? (
        // AC10: Pipeline skeleton
        <PipelineSkeleton />
      ) : error || (data as { error?: string })?.error ? (
        // AC11: Error state
        <div className="flex flex-col items-center justify-center flex-1 gap-3">
          <AlertCircle size={32} className="text-red-400/60" strokeWidth={1.5} />
          <p className="text-[0.8125rem] text-white/40 text-center">
            Nao foi possivel carregar o pipeline.
            <br />
            Tentando novamente...
          </p>
        </div>
      ) : filteredLeads.length === 0 && period !== 'all' ? (
        // Filtered empty
        <EmptyState
          icon={Filter}
          title="Nenhum lead no periodo"
          description={`Sem leads nos ultimos ${period === '7d' ? '7' : '30'} dias. Tente "All".`}
        />
      ) : (
        // AC1, AC2: Kanban board with real data
        <KanbanBoard leads={filteredLeads} onLeadClick={handleLeadClick} />
      )}
    </div>
  )
}
