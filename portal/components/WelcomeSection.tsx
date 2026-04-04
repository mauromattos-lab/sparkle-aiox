'use client'

import { UseClientIdentityReturn, planLabel } from '@/hooks/useClientIdentity'

// ── Stat Card ──────────────────────────────────────────────

function StatMini({
  label,
  value,
  color,
  suffix,
}: {
  label: string
  value: number | string
  color: string
  suffix?: string
}) {
  return (
    <div className="flex flex-col gap-0.5 px-3 py-2 rounded-lg bg-white/[0.02] border border-white/[0.05]">
      <span className="text-[10px] font-mono text-white/25 uppercase tracking-widest">
        {label}
      </span>
      <div className="flex items-baseline gap-1">
        <span className={`text-lg font-bold font-mono ${color}`}>
          {value}
        </span>
        {suffix && (
          <span className="text-[10px] text-white/20 font-mono">{suffix}</span>
        )}
      </div>
    </div>
  )
}

// ── Welcome Section Component ──────────────────────────────

interface WelcomeSectionProps {
  identity: UseClientIdentityReturn
}

export default function WelcomeSection({ identity }: WelcomeSectionProps) {
  const { isLoading, greeting, brandColor } = identity
  const stats = identity.identity?.stats
  const hasZenya = identity.identity?.client.hasZenya ?? false

  if (isLoading) {
    return (
      <div className="rounded-xl px-4 py-4 bg-white/[0.02] border border-white/[0.05] animate-pulse">
        <div className="h-6 w-64 bg-white/5 rounded mb-3" />
        <div className="flex gap-3">
          <div className="h-16 w-32 bg-white/5 rounded-lg" />
          <div className="h-16 w-32 bg-white/5 rounded-lg" />
          <div className="h-16 w-32 bg-white/5 rounded-lg" />
        </div>
      </div>
    )
  }

  if (!identity.identity) return null

  // Accent line style using brand color
  const accentStyle = brandColor
    ? { borderLeftColor: brandColor }
    : { borderLeftColor: '#7c3aed' }

  return (
    <div
      className="rounded-xl px-4 py-4 bg-white/[0.02] border border-white/[0.05] border-l-2"
      style={accentStyle}
    >
      {/* Greeting */}
      <h2 className="text-base font-semibold text-white/90 mb-3 font-mono">
        {greeting}
      </h2>

      {/* Quick stats row */}
      <div className="flex flex-wrap gap-2">
        {hasZenya && stats && stats.conversationsToday > 0 && (
          <StatMini
            label="Zenya hoje"
            value={stats.resolvedToday}
            color="text-[#0ea5e9]"
            suffix={`/ ${stats.conversationsToday} conversas`}
          />
        )}

        {hasZenya && stats && stats.conversationsToday === 0 && (
          <StatMini
            label="Zenya hoje"
            value="--"
            color="text-white/30"
            suffix="aguardando"
          />
        )}

        {hasZenya && stats && stats.conversationsMonth > 0 && (
          <StatMini
            label="Este mes"
            value={stats.conversationsMonth}
            color="text-[#22c55e]"
            suffix="conversas"
          />
        )}

        {stats && stats.brainChunks > 0 && (
          <StatMini
            label="Brain"
            value={stats.brainChunks}
            color="text-[#3b82f6]"
            suffix="chunks"
          />
        )}

        {/* If no stats available, show plan info */}
        {(!stats || (stats.conversationsToday === 0 && stats.conversationsMonth === 0 && stats.brainChunks === 0)) && (
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/[0.02] border border-white/[0.05]">
            <span className="text-[10px] font-mono text-white/25">
              Plano ativo: {planLabel(identity.plan)}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
