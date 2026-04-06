'use client'

/**
 * Command Center — /hq (Story 1.3)
 *
 * Layout (design spec section 3.1):
 *   ┌──────────────────────────────────────────────┐
 *   │  KPI Cards (4-col >= xl, 2x2 < xl)          │
 *   ├────────────────────────┬─────────────────────┤
 *   │  Decisoes Pendentes    │  Activity Feed      │
 *   │  (60% — placeholder)   │  (40%)              │
 *   ├────────────────────────┴─────────────────────┤
 *   │  System Health Bar                           │
 *   └──────────────────────────────────────────────┘
 *
 * Responsive:
 *   >= xl (1280px): 4-col KPIs + 60/40 split
 *   < xl:          2x2 KPIs + stacked sections
 */

import React from 'react'
import { LayoutDashboard } from 'lucide-react'
import { useOverview, usePulse } from '@/hooks/useHQData'
import KPICard from '@/components/hq/KPICard'
import ActivityFeed from '@/components/hq/ActivityFeed'
import SystemHealthBar from '@/components/hq/SystemHealthBar'
import DecisionsPending from '@/components/hq/DecisionsPending'
import { KPIRowSkeleton } from '@/components/hq/LoadingSkeleton'

// ── BRL formatter ─────────────────────────────────────────────────────────────

function formatMRR(value?: number): string {
  if (value == null) return '--'
  return value.toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })
}

function formatNumber(value?: number): string {
  if (value == null) return '--'
  return String(value)
}

// ── KPI row ───────────────────────────────────────────────────────────────────

function KPIRow() {
  const { data: overview, error: overviewError, isLoading: overviewLoading } = useOverview()
  const { data: pulse, isLoading: pulseLoading } = usePulse()

  if (overviewLoading || pulseLoading) return <KPIRowSkeleton />

  const mrr = overviewError ? '--' : formatMRR(overview?.mrr)
  const clients = overviewError ? '--' : formatNumber(overview?.client_count)

  // Leads: from pulse.pipeline.total or 0
  const leads = formatNumber(
    typeof pulse?.pipeline === 'object' && pulse?.pipeline !== null
      ? (pulse.pipeline as { total?: number }).total
      : typeof pulse?.pipeline === 'number'
      ? (pulse.pipeline as number)
      : undefined
  )

  // Tasks running: total - done - failed
  let tasks = '--'
  if (!overviewError && overview?.tasks_24h) {
    const { total = 0, done = 0, failed = 0 } = overview.tasks_24h
    const running = Math.max(0, total - done - failed)
    tasks = String(running)
  }

  return (
    <div
      className="grid grid-cols-2 xl:grid-cols-4 gap-3"
      role="region"
      aria-label="KPI metrics"
    >
      <KPICard
        label="MRR"
        value={mrr}
        icon="DollarSign"
        color="text-purple-400"
        href="/hq/clients"
        aria-label={`MRR: ${mrr}`}
      />
      <KPICard
        label="Clientes"
        value={clients}
        icon="Users"
        color="text-cyan-400"
        href="/hq/clients"
      />
      <KPICard
        label="Leads no funil"
        value={leads}
        icon="GitBranch"
        color="text-yellow-400"
        href="/hq/pipeline"
      />
      <KPICard
        label="Tasks rodando"
        value={tasks}
        icon="Activity"
        color="text-blue-400"
        tooltip="Em desenvolvimento — View Workflows em breve"
      />
    </div>
  )
}

// ── Activity section wrapper ──────────────────────────────────────────────────

function ActivitySection() {
  return (
    <section className="flex flex-col gap-3 h-full" aria-label="Activity Feed">
      {/* Section header */}
      <div className="flex items-center gap-2">
        <LayoutDashboard size={14} className="text-white/30" strokeWidth={1.75} aria-hidden="true" />
        <span className="text-[0.6875rem] text-white/30 uppercase tracking-wide font-medium">
          Atividade
        </span>
      </div>

      {/* Feed */}
      <div className="glass rounded-xl flex-1 overflow-hidden p-2 max-h-[360px] xl:max-h-none xl:overflow-y-auto">
        <ActivityFeed />
      </div>
    </section>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function CommandCenterPage() {
  return (
    <div className="hq-page-enter hq-density flex flex-col gap-4 h-full">
      {/* Page header */}
      <div className="flex items-center gap-3 shrink-0">
        <LayoutDashboard
          size={20}
          className="text-purple-400"
          strokeWidth={1.75}
          aria-hidden="true"
        />
        <div>
          <h1 className="text-[0.9375rem] font-semibold text-white/80 leading-tight">
            Command Center
          </h1>
          <p className="text-[0.6875rem] text-white/30 font-mono mt-0.5">/hq</p>
        </div>
      </div>

      {/* KPI Cards row — 4-col on xl+, 2x2 below */}
      <div className="shrink-0">
        <KPIRow />
      </div>

      {/* Mid section: Decisions (60%) + Activity Feed (40%) */}
      {/* On xl+: side by side. Below xl: stacked */}
      <div className="flex flex-col xl:flex-row gap-4 flex-1 min-h-0">
        {/* Decisions Pending — 60% on xl+ */}
        <div className="w-full xl:w-[60%] min-h-0">
          <DecisionsPending />
        </div>

        {/* Activity Feed — 40% on xl+ */}
        <div className="w-full xl:w-[40%] min-h-0">
          <ActivitySection />
        </div>
      </div>

      {/* System Health Bar — full width, pinned to bottom */}
      <div className="shrink-0">
        <SystemHealthBar />
      </div>
    </div>
  )
}
