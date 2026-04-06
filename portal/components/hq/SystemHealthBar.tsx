'use client'

/**
 * SystemHealthBar — shows Runtime, Crons, Brain, Z-API health.
 * AC13: indicator per service (green/yellow/red) from /api/hq/pulse.
 * AC14: green = opacity 0.6, yellow/red = opacity 1.0 + border.
 * AC16: "System Offline" in red when runtime unreachable.
 */

import React, { useState } from 'react'
import { CheckCircle2, AlertTriangle, XCircle, Wifi, WifiOff } from 'lucide-react'
import { usePulse, type PulseData } from '@/hooks/useHQData'
import { SystemHealthSkeleton } from './LoadingSkeleton'

// ── Types ─────────────────────────────────────────────────────────────────────

type ServiceStatus = 'ok' | 'warn' | 'error' | 'unknown'

interface ServiceCheck {
  name: string
  status: ServiceStatus
  detail?: string
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function deriveServices(data: PulseData): ServiceCheck[] {
  const checks = data.checks ?? {}

  // Runtime: if we got a response at all, Runtime is up
  const runtime: ServiceCheck = {
    name: 'Runtime',
    status: 'ok',
    detail: 'Operational',
  }

  // Brain
  const brainStatus = data.brain?.status
  const brain: ServiceCheck = {
    name: 'Brain',
    status:
      brainStatus === 'ok' || brainStatus === 'healthy' || brainStatus === undefined
        ? 'ok'
        : brainStatus === 'warn'
        ? 'warn'
        : 'error',
    detail: brainStatus ?? 'ok',
  }

  // Crons — infer from any cron-related check
  const crons: ServiceCheck = {
    name: 'Crons',
    status: checks.supabase === false ? 'warn' : 'ok',
    detail: checks.supabase === false ? 'DB connection issue' : 'Running',
  }

  // Z-API
  const zapiOk = checks.zapi_connected !== false && checks.zapi_configured !== false
  const zapi: ServiceCheck = {
    name: 'Z-API',
    status:
      checks.zapi_connected === false
        ? 'error'
        : checks.zapi_configured === false
        ? 'warn'
        : 'ok',
    detail: zapiOk ? 'Connected' : checks.zapi_connected === false ? 'Disconnected' : 'Misconfigured',
  }

  return [runtime, crons, brain, zapi]
}

function StatusIcon({ status }: { status: ServiceStatus }) {
  if (status === 'ok')
    return <CheckCircle2 size={13} className="text-green-400" strokeWidth={2} aria-hidden="true" />
  if (status === 'warn')
    return <AlertTriangle size={13} className="text-yellow-400" strokeWidth={2} aria-hidden="true" />
  if (status === 'error')
    return <XCircle size={13} className="text-red-400" strokeWidth={2} aria-hidden="true" />
  return <Wifi size={13} className="text-white/30" strokeWidth={2} aria-hidden="true" />
}

// ── Service chip ──────────────────────────────────────────────────────────────

function ServiceChip({ check }: { check: ServiceCheck }) {
  const [showTooltip, setShowTooltip] = useState(false)

  const isHealthy = check.status === 'ok'
  const chipClass = [
    'relative flex items-center gap-1.5 px-2 py-1 rounded-md text-[0.6875rem] font-medium',
    'cursor-default select-none transition-opacity duration-150',
    isHealthy
      ? 'opacity-60 text-white/50'
      : check.status === 'warn'
      ? 'opacity-100 text-yellow-300 border border-yellow-400/30 bg-yellow-400/[0.06]'
      : 'opacity-100 text-red-300 border border-red-400/30 bg-red-400/[0.06]',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div
      className={chipClass}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
      aria-label={`${check.name}: ${check.detail ?? check.status}`}
    >
      <StatusIcon status={check.status} />
      <span>{check.name}</span>

      {/* Tooltip */}
      {showTooltip && check.detail && (
        <div
          className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 px-2 py-1 rounded-md bg-[#1a1a2e] border border-white/10 text-[0.6875rem] text-white/70 whitespace-nowrap z-20 pointer-events-none"
          role="tooltip"
        >
          {check.detail}
        </div>
      )}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function SystemHealthBar() {
  const { data, error, isLoading } = usePulse()

  if (isLoading) return <SystemHealthSkeleton />

  // Runtime offline
  if (error || (data as { error?: string })?.error) {
    return (
      <div className="glass rounded-xl px-4 py-2.5 flex items-center gap-2 border border-red-500/30 bg-red-500/[0.04]">
        <WifiOff size={14} className="text-red-400 shrink-0" strokeWidth={1.75} />
        <span className="text-[0.8125rem] font-medium text-red-300">System Offline</span>
        <span className="text-[0.6875rem] text-red-400/60 ml-1">
          — Runtime nao acessivel. Verificando...
        </span>
      </div>
    )
  }

  const services = data ? deriveServices(data) : []
  const allOk = services.every((s) => s.status === 'ok')
  const anyError = services.some((s) => s.status === 'error')

  const barBorder = allOk
    ? ''
    : anyError
    ? 'border-red-500/20'
    : 'border-yellow-500/20'

  return (
    <div
      className={`glass rounded-xl px-4 py-2.5 flex flex-wrap items-center gap-3 ${barBorder}`}
      role="region"
      aria-label="System health"
    >
      {/* Label */}
      <span
        className={[
          'text-[0.6875rem] uppercase tracking-wide font-medium shrink-0',
          allOk ? 'text-white/30 opacity-60' : anyError ? 'text-red-300' : 'text-yellow-300',
        ].join(' ')}
      >
        {allOk ? 'System OK' : anyError ? 'System Alert' : 'System Warning'}
      </span>

      {/* Divider */}
      <div className="w-px h-3 bg-white/10 shrink-0" />

      {/* Service chips */}
      <div className="flex flex-wrap items-center gap-1">
        {services.map((s) => (
          <ServiceChip key={s.name} check={s} />
        ))}
      </div>
    </div>
  )
}
