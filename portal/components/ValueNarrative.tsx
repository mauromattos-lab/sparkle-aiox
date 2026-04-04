'use client'

import { useValueMetrics, MilestoneBadge } from '@/hooks/useValueMetrics'

// ── Icons ──────────────────────────────────────────────────

function ZenyaIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#0ea5e9" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  )
}

function BrainIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2a7 7 0 0 1 7 7c0 2.38-1.19 4.47-3 5.74V17a2 2 0 0 1-2 2H10a2 2 0 0 1-2-2v-2.26C6.19 13.47 5 11.38 5 9a7 7 0 0 1 7-7z" />
      <path d="M10 21h4" />
      <path d="M12 17v4" />
    </svg>
  )
}

function ClockIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#22c55e" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  )
}

function TrophyIcon({ size = 12 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6" />
      <path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18" />
      <path d="M4 22h16" />
      <path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22" />
      <path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22" />
      <path d="M18 2H6v7a6 6 0 0 0 12 0V2Z" />
    </svg>
  )
}

// ── Animated Progress Bar ──────────────────────────────────

function ProgressBar({
  value,
  max,
  color,
}: {
  value: number
  max: number
  color: string
}) {
  const percent = max > 0 ? Math.min((value / max) * 100, 100) : 0

  return (
    <div className="w-full h-1.5 rounded-full bg-white/[0.06] overflow-hidden mt-2">
      <div
        className="h-full rounded-full transition-all duration-1000 ease-out"
        style={{
          width: `${percent}%`,
          background: `linear-gradient(90deg, ${color}80, ${color})`,
          boxShadow: `0 0 8px ${color}40`,
        }}
      />
    </div>
  )
}

// ── Milestone Badge ────────────────────────────────────────

function MilestoneBadgeComponent({ badge }: { badge: MilestoneBadge }) {
  const colorMap = {
    conversations: 'text-[#0ea5e9] border-[#0ea5e9]/20 bg-[#0ea5e9]/5',
    brain: 'text-[#3b82f6] border-[#3b82f6]/20 bg-[#3b82f6]/5',
    economy: 'text-[#22c55e] border-[#22c55e]/20 bg-[#22c55e]/5',
  }

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[10px] font-mono ${colorMap[badge.icon]}`}>
      <TrophyIcon size={10} />
      {badge.label}
    </span>
  )
}

// ── Narrative Card ─────────────────────────────────────────

function NarrativeCard({
  icon,
  title,
  headline,
  detail,
  accentColor,
  growthBadge,
  progressValue,
  progressMax,
  children,
}: {
  icon: React.ReactNode
  title: string
  headline: string
  detail: string
  accentColor: string
  growthBadge?: string | null
  progressValue?: number
  progressMax?: number
  children?: React.ReactNode
}) {
  return (
    <div className="glass glass-hover rounded-2xl p-5 group relative overflow-hidden transition-all duration-300">
      {/* Subtle accent glow on hover */}
      <div
        className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"
        style={{
          background: `radial-gradient(ellipse at 50% 0%, ${accentColor}08 0%, transparent 70%)`,
        }}
      />

      <div className="relative z-10">
        {/* Header row */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center"
              style={{ background: `${accentColor}15`, border: `1px solid ${accentColor}25` }}
            >
              {icon}
            </div>
            <span className="text-[11px] font-mono text-white/30 uppercase tracking-widest">
              {title}
            </span>
          </div>
          {growthBadge && (
            <span
              className="text-[11px] font-mono font-medium px-2 py-0.5 rounded-full"
              style={{
                color: growthBadge.startsWith('-') ? '#ef4444' : '#22c55e',
                background: growthBadge.startsWith('-') ? '#ef444415' : '#22c55e15',
                border: `1px solid ${growthBadge.startsWith('-') ? '#ef444425' : '#22c55e25'}`,
              }}
            >
              {growthBadge}
            </span>
          )}
        </div>

        {/* Headline */}
        <p className="text-sm font-medium text-white/90 leading-relaxed mb-1">
          {headline}
        </p>

        {/* Detail */}
        <p className="text-xs text-white/35 leading-relaxed">
          {detail}
        </p>

        {/* Progress bar */}
        {progressValue !== undefined && progressMax !== undefined && progressMax > 0 && (
          <ProgressBar value={progressValue} max={progressMax} color={accentColor} />
        )}

        {/* Children (milestones etc.) */}
        {children}
      </div>
    </div>
  )
}

// ── Loading Skeleton ───────────────────────────────────────

function ValueNarrativeSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {[1, 2, 3].map((i) => (
        <div key={i} className="glass rounded-2xl p-5 animate-pulse">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-8 h-8 rounded-lg bg-white/5" />
            <div className="h-3 w-20 bg-white/5 rounded" />
          </div>
          <div className="h-4 w-full bg-white/5 rounded mb-2" />
          <div className="h-3 w-3/4 bg-white/5 rounded mb-3" />
          <div className="h-1.5 w-full bg-white/[0.03] rounded-full" />
        </div>
      ))}
    </div>
  )
}

// ── Main Component ─────────────────────────────────────────

export default function ValueNarrative() {
  const { metrics, narrative, isLoading, error } = useValueMetrics()

  if (isLoading) return <ValueNarrativeSkeleton />

  if (error || !narrative || !metrics) {
    // Silently skip if no data — this is a progressive enhancement
    return null
  }

  // Only show if client has some data
  const hasAnyData =
    metrics.conversations.currentMonth > 0 ||
    metrics.brain.totalChunks > 0

  if (!hasAnyData) return null

  // Find next milestone for progress bars
  const nextConvMilestone = [100, 500, 1000, 5000].find(m => m > metrics.conversations.currentResolved) ?? 5000
  const nextBrainMilestone = [500, 1000, 5000].find(m => m > metrics.brain.totalChunks) ?? 5000

  return (
    <section className="space-y-3">
      {/* Section label */}
      <div className="flex items-center gap-2">
        <div className="h-px flex-1 bg-white/[0.05]" />
        <span className="text-[10px] font-mono text-white/20 uppercase tracking-[0.2em]">
          Valor acumulado
        </span>
        <div className="h-px flex-1 bg-white/[0.05]" />
      </div>

      {/* Cards grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Card 1: Sua Zenya */}
        {metrics.client.hasZenya && (
          <NarrativeCard
            icon={<ZenyaIcon />}
            title="Sua Zenya"
            headline={narrative.zenyaHeadline}
            detail={narrative.zenyaDetail}
            accentColor="#0ea5e9"
            growthBadge={narrative.growthBadge}
            progressValue={metrics.conversations.currentResolved}
            progressMax={nextConvMilestone}
          >
            {narrative.milestones.filter(m => m.icon === 'conversations').length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-3">
                {narrative.milestones.filter(m => m.icon === 'conversations').map(m => (
                  <MilestoneBadgeComponent key={m.id} badge={m} />
                ))}
              </div>
            )}
          </NarrativeCard>
        )}

        {/* Card 2: Seu Brain */}
        <NarrativeCard
          icon={<BrainIcon />}
          title="Seu Brain"
          headline={narrative.brainHeadline}
          detail={narrative.brainDetail}
          accentColor="#3b82f6"
          progressValue={metrics.brain.totalChunks}
          progressMax={nextBrainMilestone}
        >
          {narrative.milestones.filter(m => m.icon === 'brain').length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-3">
              {narrative.milestones.filter(m => m.icon === 'brain').map(m => (
                <MilestoneBadgeComponent key={m.id} badge={m} />
              ))}
            </div>
          )}
        </NarrativeCard>

        {/* Card 3: Economia */}
        <NarrativeCard
          icon={<ClockIcon />}
          title="Economia"
          headline={narrative.economyHeadline}
          detail={narrative.economyDetail}
          accentColor="#22c55e"
        >
          {metrics.economy.hoursSaved > 0 && (
            <div className="mt-3 flex items-baseline gap-1">
              <span className="text-2xl font-bold font-mono text-[#22c55e]">
                {metrics.economy.hoursSaved.toLocaleString('pt-BR')}h
              </span>
              <span className="text-[10px] text-white/20 font-mono">
                economizadas
              </span>
            </div>
          )}
          {narrative.milestones.filter(m => m.icon === 'economy').length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {narrative.milestones.filter(m => m.icon === 'economy').map(m => (
                <MilestoneBadgeComponent key={m.id} badge={m} />
              ))}
            </div>
          )}
        </NarrativeCard>
      </div>
    </section>
  )
}
