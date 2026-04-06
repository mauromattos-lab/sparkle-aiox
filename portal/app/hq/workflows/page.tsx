'use client'

/**
 * Workflows Page — Story 3.2
 * Lists workflow_runs with status/period filters, steps visualization in DetailPanel,
 * and Sprint Items section with agent_work_items grouped by status.
 * AC1-AC13, IV1-IV4
 */

import React, { useMemo, useState } from 'react'
import { GitBranch, AlertCircle } from 'lucide-react'
import { useWorkflowRuns, useAgentWorkItems } from '@/hooks/useHQData'
import WorkflowList from '@/components/hq/WorkflowList'
import WorkflowFilters, { type StatusFilter, type PeriodFilter } from '@/components/hq/WorkflowFilters'
import SprintItemsSection from '@/components/hq/SprintItemsSection'
import { WorkflowListSkeleton } from '@/components/hq/LoadingSkeleton'
import EmptyState from '@/components/hq/EmptyState'

// ── Counters — AC12 ───────────────────────────────────────────────────────────

function CounterBadge({ label, value }: { label: string; value: number }) {
  return (
    <span className="text-[0.75rem] text-white/40 font-mono">
      {label}:{' '}
      <span className="text-white/60 font-semibold">{value}</span>
    </span>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function WorkflowsPage() {
  const [status, setStatus] = useState<StatusFilter>('all')
  const [period, setPeriod] = useState<PeriodFilter>('30d')

  // AC1: all workflows (no server-side filter — filtering client-side for counter accuracy)
  const { data: allWorkflows, error, isLoading } = useWorkflowRuns()
  // AC2: agent work items
  const { data: workItems, isLoading: itemsLoading } = useAgentWorkItems()

  const workflows = allWorkflows ?? []
  const items = workItems ?? []

  // AC3, AC4, AC5: client-side filtering
  const filteredWorkflows = useMemo(() => {
    let list = [...workflows]

    // Status filter
    if (status !== 'all') {
      list = list.filter((w) => w.status === status)
    }

    // Period filter
    if (period !== 'all') {
      const days = period === '7d' ? 7 : 30
      const cutoff = Date.now() - days * 24 * 60 * 60 * 1000
      list = list.filter((w) => new Date(w.created_at).getTime() >= cutoff)
    }

    return list
  }, [workflows, status, period])

  // AC12: counters
  const totalCount = workflows.length
  const runningCount = workflows.filter((w) => w.status === 'running').length
  const completed7dCount = useMemo(() => {
    const cutoff7d = Date.now() - 7 * 24 * 60 * 60 * 1000
    return workflows.filter(
      (w) => w.status === 'completed' && new Date(w.created_at).getTime() >= cutoff7d
    ).length
  }, [workflows])

  // Compute empty state label for period
  const periodLabel = period === '7d' ? '7 dias' : period === '30d' ? '30 dias' : 'todos os periodos'

  return (
    <div className="hq-page-enter hq-density flex flex-col gap-5 h-full">
      {/* Header — AC12 */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <GitBranch size={20} className="text-purple-400 shrink-0" strokeWidth={1.75} aria-hidden="true" />
          <div>
            <h1 className="text-[0.9375rem] font-semibold text-white/80 leading-tight">
              Workflows
            </h1>
            {!isLoading && (
              <div className="flex items-center gap-3 mt-0.5 flex-wrap">
                <CounterBadge label="Total" value={totalCount} />
                <CounterBadge label="Em andamento" value={runningCount} />
                <CounterBadge label="Concluidos (7d)" value={completed7dCount} />
              </div>
            )}
          </div>
        </div>

        {/* AC4 + AC5: filters */}
        <WorkflowFilters
          status={status}
          period={period}
          onStatusChange={setStatus}
          onPeriodChange={setPeriod}
        />
      </div>

      {/* Workflow list content */}
      {isLoading ? (
        // AC10: loading skeleton
        <WorkflowListSkeleton />
      ) : error ? (
        // Error state
        <div className="flex flex-col items-center justify-center flex-1 gap-3">
          <AlertCircle size={32} className="text-red-400/60" strokeWidth={1.5} />
          <p className="text-[0.8125rem] text-white/40 text-center">
            Nao foi possivel carregar os workflows.
            <br />
            Tentando novamente...
          </p>
        </div>
      ) : filteredWorkflows.length === 0 ? (
        // AC9: empty state
        <EmptyState
          icon={GitBranch}
          title="Nenhum workflow encontrado"
          description={`Sem workflows nos ultimos ${periodLabel}.`}
        />
      ) : (
        // AC3, AC7, AC11: workflow list
        <WorkflowList workflows={filteredWorkflows} />
      )}

      {/* AC8: Sprint Items section */}
      {!itemsLoading && items.length > 0 && (
        <SprintItemsSection items={items} />
      )}
      {itemsLoading && (
        <div className="h-8 flex items-center">
          <span className="text-[0.75rem] text-white/30 font-mono">Carregando sprint items...</span>
        </div>
      )}
    </div>
  )
}
