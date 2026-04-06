'use client'

/**
 * WorkflowList — tabular list of workflow_runs.
 * Story 3.2 — AC3, AC7, AC11
 *
 * Columns: workflow_type, step (N/total), status badge, agent, relative date.
 * Click opens DetailPanel via useDetailPanel().
 */

import React from 'react'
import { GitBranch, Clock, CheckCircle2, XCircle, Circle } from 'lucide-react'
import { useDetailPanel } from '@/components/hq/DetailPanelContext'
import WorkflowStepsBar from '@/components/hq/WorkflowStepsBar'
import type { WorkflowRun } from '@/hooks/useHQData'

// ── Helpers ──────────────────────────────────────────────────────────────────

export function relativeTime(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return 'agora'
  if (minutes < 60) return `${minutes}m atrás`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h atrás`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}d atrás`
  return new Date(dateStr).toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' })
}

// ── Status badge — AC11 ────────────────────────────────────────────────────

interface StatusBadgeProps {
  status: WorkflowRun['status']
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const configs: Record<
    WorkflowRun['status'],
    { icon: React.ReactNode; label: string; className: string }
  > = {
    running: {
      icon: <Clock size={11} strokeWidth={2} />,
      label: 'Running',
      className: 'text-yellow-400 bg-yellow-400/10',
    },
    completed: {
      icon: <CheckCircle2 size={11} strokeWidth={2} />,
      label: 'Completed',
      className: 'text-green-400 bg-green-400/10',
    },
    failed: {
      icon: <XCircle size={11} strokeWidth={2} />,
      label: 'Failed',
      className: 'text-red-400 bg-red-400/10',
    },
    pending: {
      icon: <Circle size={11} strokeWidth={2} />,
      label: 'Pending',
      className: 'text-white/50 bg-white/5',
    },
  }

  const cfg = configs[status] ?? configs.pending

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${cfg.className}`}
    >
      {cfg.icon}
      {cfg.label}
    </span>
  )
}

// ── Workflow detail panel content — AC7 ──────────────────────────────────────

function WorkflowDetailContent({ workflow }: { workflow: WorkflowRun }) {
  const ctx = workflow.context ?? {}
  const sprintItem = (ctx.sprint_item as string) ?? null
  const epic = (ctx.epic as string) ?? null
  const client = (ctx.client as string) ?? (ctx.cliente as string) ?? null
  const currentAgent = (ctx.current_agent as string) ?? workflow.agent_id ?? null

  return (
    <div className="flex flex-col gap-5 p-1">
      {/* Header */}
      <div className="flex items-center gap-2">
        <GitBranch size={16} className="text-purple-400" strokeWidth={1.75} />
        <span className="text-[0.9375rem] font-semibold text-white/80">
          {workflow.workflow_type}
        </span>
      </div>

      {/* Steps bar */}
      <div className="flex flex-col gap-1.5">
        <span className="text-[0.6875rem] text-white/40 uppercase tracking-wide">Pipeline</span>
        <WorkflowStepsBar currentStep={workflow.current_step} />
      </div>

      {/* Details */}
      <div className="flex flex-col gap-2 text-[0.8125rem]">
        <div>
          <span className="text-white/40">Status:</span>{' '}
          <StatusBadge status={workflow.status} />
        </div>

        {currentAgent && (
          <div>
            <span className="text-white/40">Agente atual:</span>{' '}
            <span className="text-white/70 font-mono text-[0.75rem]">{currentAgent}</span>
          </div>
        )}

        {sprintItem && (
          <div>
            <span className="text-white/40">Sprint item:</span>{' '}
            <span className="text-white/70">{sprintItem}</span>
          </div>
        )}

        {epic && (
          <div>
            <span className="text-white/40">Epic:</span>{' '}
            <span className="text-white/70">{epic}</span>
          </div>
        )}

        {client && (
          <div>
            <span className="text-white/40">Cliente:</span>{' '}
            <span className="text-white/70">{client}</span>
          </div>
        )}

        <div>
          <span className="text-white/40">Inicio:</span>{' '}
          <span className="text-white/50 font-mono text-[0.6875rem]">
            {new Date(workflow.created_at).toLocaleString('pt-BR')}
          </span>
        </div>

        <div>
          <span className="text-white/40">Conclusao:</span>{' '}
          <span className="text-white/50 font-mono text-[0.6875rem]">
            {workflow.completed_at
              ? new Date(workflow.completed_at).toLocaleString('pt-BR')
              : 'Em andamento'}
          </span>
        </div>
      </div>

      {/* Raw context */}
      {Object.keys(ctx).length > 0 && (
        <div className="flex flex-col gap-1.5 mt-1 pt-3 border-t border-white/[0.06]">
          <span className="text-[0.6875rem] text-white/30 uppercase tracking-wide">Contexto</span>
          <pre className="text-[0.6875rem] text-white/40 whitespace-pre-wrap break-all leading-relaxed bg-white/[0.03] rounded p-2">
            {JSON.stringify(ctx, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}

// ── WorkflowList ─────────────────────────────────────────────────────────────

interface WorkflowListProps {
  workflows: WorkflowRun[]
}

export default function WorkflowList({ workflows }: WorkflowListProps) {
  const { openPanel } = useDetailPanel()

  function handleClick(workflow: WorkflowRun) {
    openPanel(<WorkflowDetailContent workflow={workflow} />)
  }

  return (
    <div className="bg-white/[0.04] backdrop-blur-xl border border-white/[0.08] rounded-lg overflow-hidden">
      {/* Table header */}
      <div className="grid grid-cols-[1fr_auto_auto_auto] gap-3 px-4 py-2 border-b border-white/[0.06] bg-white/[0.02]">
        <span className="text-[0.6875rem] text-white/30 uppercase tracking-wide">Workflow</span>
        <span className="text-[0.6875rem] text-white/30 uppercase tracking-wide">Steps</span>
        <span className="text-[0.6875rem] text-white/30 uppercase tracking-wide">Status</span>
        <span className="text-[0.6875rem] text-white/30 uppercase tracking-wide">Inicio</span>
      </div>

      {/* Rows */}
      <div className="flex flex-col divide-y divide-white/[0.04]">
        {workflows.map((wf) => {
          const ctxAgent = (wf.context?.current_agent as string) ?? wf.agent_id ?? null

          return (
            <button
              key={wf.id}
              onClick={() => handleClick(wf)}
              className="grid grid-cols-[1fr_auto_auto_auto] gap-3 px-4 py-3 text-left hover:bg-white/[0.04] cursor-pointer transition-colors duration-100 focus:outline-none focus-visible:ring-1 focus-visible:ring-purple-500"
              aria-label={`Workflow ${wf.workflow_type}`}
            >
              {/* Type + agent */}
              <div className="flex items-center gap-2 min-w-0">
                <GitBranch size={13} className="text-purple-400/70 shrink-0" strokeWidth={1.75} />
                <div className="flex flex-col gap-0.5 min-w-0">
                  <span className="text-[0.8125rem] text-white/70 font-medium truncate">
                    {wf.workflow_type}
                  </span>
                  {ctxAgent && (
                    <span className="text-[0.6875rem] text-white/35 font-mono truncate">
                      {ctxAgent}
                    </span>
                  )}
                </div>
              </div>

              {/* Steps (compact text) */}
              <div className="flex items-center">
                <WorkflowStepsBar currentStep={wf.current_step} compact />
              </div>

              {/* Status badge */}
              <div className="flex items-center">
                <StatusBadge status={wf.status} />
              </div>

              {/* Relative date */}
              <div className="flex items-center">
                <span className="text-[0.6875rem] text-white/35 font-mono whitespace-nowrap">
                  {relativeTime(wf.created_at)}
                </span>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
