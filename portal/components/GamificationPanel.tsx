'use client'

import { useGamification, Achievement, TimelineEntry } from '@/hooks/useGamification'

// ── Icons ──────────────────────────────────────────────────

function BrainIcon({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="#06b6d4" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2a7 7 0 0 1 7 7c0 2.38-1.19 4.47-3 5.74V17a2 2 0 0 1-2 2H10a2 2 0 0 1-2-2v-2.26C6.19 13.47 5 11.38 5 9a7 7 0 0 1 7-7z" />
      <path d="M10 21h4" />
      <path d="M12 17v4" />
    </svg>
  )
}

function ZenyaIcon({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="#8b5cf6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  )
}

function StarIcon({ size = 14, filled = false }: { size?: number; filled?: boolean }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={filled ? '#eab308' : 'none'}
      stroke="#eab308" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" />
    </svg>
  )
}

function TrophyIcon({ size = 14 }: { size?: number }) {
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

function LockIcon({ size = 12 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  )
}

function TimelineIcon({ type }: { type: string }) {
  const size = 12
  switch (type) {
    case 'conversa':
      return <ZenyaIcon size={size} />
    case 'brain':
      return <BrainIcon size={size} />
    case 'conquista':
      return <TrophyIcon size={size} />
    default:
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
        </svg>
      )
  }
}

// ── Animated XP Bar ────────────────────────────────────────

function XPBar({
  progress,
  gradientFrom,
  gradientTo,
}: {
  progress: number
  gradientFrom: string
  gradientTo: string
}) {
  const percent = Math.min(progress * 100, 100)

  return (
    <div className="w-full h-2.5 rounded-full bg-white/[0.06] overflow-hidden relative">
      {/* Animated fill */}
      <div
        className="h-full rounded-full transition-all duration-1000 ease-out relative"
        style={{
          width: `${percent}%`,
          background: `linear-gradient(90deg, ${gradientFrom}, ${gradientTo})`,
          boxShadow: `0 0 12px ${gradientFrom}50, 0 0 4px ${gradientTo}40`,
        }}
      >
        {/* Shimmer effect */}
        <div
          className="absolute inset-0 rounded-full animate-shimmer"
          style={{
            background: 'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.15) 50%, transparent 100%)',
          }}
        />
      </div>
    </div>
  )
}

// ── Star Rating Display ────────────────────────────────────

function StarRating({ stars, maxStars = 5 }: { stars: number; maxStars?: number }) {
  return (
    <div className="flex items-center gap-0.5">
      {Array.from({ length: maxStars }).map((_, i) => (
        <StarIcon key={i} filled={i < stars} size={14} />
      ))}
    </div>
  )
}

// ── Achievement Badge ──────────────────────────────────────

function AchievementBadge({ achievement }: { achievement: Achievement }) {
  const categoryColors = {
    brain: { border: 'border-[#06b6d4]/30', bg: 'bg-[#06b6d4]/10', text: 'text-[#06b6d4]' },
    zenya: { border: 'border-[#8b5cf6]/30', bg: 'bg-[#8b5cf6]/10', text: 'text-[#8b5cf6]' },
    quality: { border: 'border-[#22c55e]/30', bg: 'bg-[#22c55e]/10', text: 'text-[#22c55e]' },
    milestone: { border: 'border-[#eab308]/30', bg: 'bg-[#eab308]/10', text: 'text-[#eab308]' },
  }

  const colors = categoryColors[achievement.category]
  const unlocked = achievement.unlocked

  return (
    <div
      className={`
        relative flex items-center gap-2 px-3 py-2 rounded-lg border transition-all duration-300
        ${unlocked
          ? `${colors.border} ${colors.bg} ${colors.text}`
          : 'border-white/[0.05] bg-white/[0.02] text-white/20'
        }
      `}
      title={achievement.description}
    >
      {unlocked ? (
        <TrophyIcon size={14} />
      ) : (
        <LockIcon size={12} />
      )}
      <div className="flex flex-col">
        <span className={`text-[11px] font-mono font-medium ${unlocked ? '' : 'text-white/25'}`}>
          {achievement.label}
        </span>
        {unlocked && (
          <span className="text-[9px] font-mono opacity-60">
            {achievement.description}
          </span>
        )}
      </div>
    </div>
  )
}

// ── Timeline Item ──────────────────────────────────────────

function TimelineItem({ entry, isLast }: { entry: TimelineEntry; isLast: boolean }) {
  const time = new Date(entry.timestamp)
  const timeStr = time.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' })

  const typeColors: Record<string, string> = {
    conversa: 'border-[#8b5cf6]/40 text-[#8b5cf6]',
    brain: 'border-[#06b6d4]/40 text-[#06b6d4]',
    conquista: 'border-[#eab308]/40 text-[#eab308]',
    nivel: 'border-[#22c55e]/40 text-[#22c55e]',
  }

  const dotColors: Record<string, string> = {
    conversa: 'bg-[#8b5cf6]',
    brain: 'bg-[#06b6d4]',
    conquista: 'bg-[#eab308]',
    nivel: 'bg-[#22c55e]',
  }

  return (
    <div className="flex gap-3 relative">
      {/* Vertical line + dot */}
      <div className="flex flex-col items-center">
        <div className={`w-2 h-2 rounded-full flex-shrink-0 mt-1 ${dotColors[entry.type] ?? 'bg-white/20'}`} />
        {!isLast && (
          <div className="w-px flex-1 bg-white/[0.06] mt-1" />
        )}
      </div>

      {/* Content */}
      <div className={`flex-1 pb-4 ${typeColors[entry.type] ?? 'text-white/40'}`}>
        <div className="flex items-center gap-2 mb-0.5">
          <TimelineIcon type={entry.type} />
          <span className="text-[11px] font-mono font-medium">{entry.label}</span>
          <span className="text-[9px] font-mono text-white/20 ml-auto">{timeStr}</span>
        </div>
        <p className="text-[10px] text-white/30 font-mono">{entry.detail}</p>
      </div>
    </div>
  )
}

// ── Loading Skeleton ───────────────────────────────────────

function GamificationSkeleton() {
  return (
    <section className="space-y-4 animate-pulse">
      {/* Section label */}
      <div className="flex items-center gap-2">
        <div className="h-px flex-1 bg-white/[0.05]" />
        <div className="h-3 w-32 bg-white/5 rounded" />
        <div className="h-px flex-1 bg-white/[0.05]" />
      </div>

      {/* Level cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="glass rounded-2xl p-5">
          <div className="h-4 w-24 bg-white/5 rounded mb-3" />
          <div className="h-2.5 w-full bg-white/[0.03] rounded-full mb-2" />
          <div className="h-3 w-40 bg-white/5 rounded" />
        </div>
        <div className="glass rounded-2xl p-5">
          <div className="h-4 w-24 bg-white/5 rounded mb-3" />
          <div className="h-2.5 w-full bg-white/[0.03] rounded-full mb-2" />
          <div className="h-3 w-40 bg-white/5 rounded" />
        </div>
      </div>

      {/* Achievements */}
      <div className="glass rounded-2xl p-5">
        <div className="h-3 w-20 bg-white/5 rounded mb-3" />
        <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-12 bg-white/[0.02] rounded-lg" />
          ))}
        </div>
      </div>
    </section>
  )
}

// ── Main Component ─────────────────────────────────────────

export default function GamificationPanel() {
  const {
    data,
    isLoading,
    error,
    brainLevel,
    zenyaLevel,
    unlockedAchievements,
    lockedAchievements,
    unlockedCount,
    totalAchievements,
  } = useGamification()

  if (isLoading) return <GamificationSkeleton />
  if (error || !data) return null

  // Only show if there is meaningful data
  const hasData = data.stats.brainChunks > 0 || data.stats.totalConversations > 0
  if (!hasData) return null

  return (
    <section className="space-y-4">
      {/* ── Section label ──────────────────────────────── */}
      <div className="flex items-center gap-2">
        <div className="h-px flex-1 bg-white/[0.05]" />
        <span className="text-[10px] font-mono text-white/20 uppercase tracking-[0.2em]">
          Progresso & Conquistas
        </span>
        <div className="h-px flex-1 bg-white/[0.05]" />
      </div>

      {/* ── Level Cards Grid ───────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

        {/* Brain XP Card */}
        {brainLevel && (
          <div className="glass glass-hover rounded-2xl p-5 group relative overflow-hidden transition-all duration-300">
            {/* Ambient glow */}
            <div
              className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"
              style={{ background: 'radial-gradient(ellipse at 50% 0%, rgba(6,182,212,0.06) 0%, transparent 70%)' }}
            />

            <div className="relative z-10">
              {/* Header */}
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center"
                    style={{ background: 'rgba(6,182,212,0.12)', border: '1px solid rgba(6,182,212,0.2)' }}>
                    <BrainIcon size={18} />
                  </div>
                  <div className="flex flex-col">
                    <span className="text-[11px] font-mono text-white/30 uppercase tracking-widest">
                      Brain XP
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-2xl font-bold font-mono text-[#06b6d4]">
                    {brainLevel.level}
                  </span>
                  <span className="text-[10px] font-mono text-white/20 self-end mb-1">
                    / 10
                  </span>
                </div>
              </div>

              {/* XP Bar */}
              <XPBar
                progress={brainLevel.progress}
                gradientFrom="#06b6d4"
                gradientTo="#8b5cf6"
              />

              {/* XP details */}
              <div className="flex items-center justify-between mt-2">
                <span className="text-[10px] font-mono text-white/25">
                  {brainLevel.xp.toLocaleString('pt-BR')} XP
                </span>
                {!brainLevel.isMaxLevel ? (
                  <span className="text-[10px] font-mono text-white/25">
                    {brainLevel.xpInLevel} / {brainLevel.xpForNext} para nivel {brainLevel.level + 1}
                  </span>
                ) : (
                  <span className="text-[10px] font-mono text-[#06b6d4]/60">
                    Nivel maximo
                  </span>
                )}
              </div>

              {/* Brain stats */}
              <div className="flex items-center gap-3 mt-3 pt-3 border-t border-white/[0.04]">
                <div className="flex items-center gap-1">
                  <span className="text-[10px] font-mono text-white/20">Chunks:</span>
                  <span className="text-xs font-mono font-medium text-[#06b6d4]">
                    {data.stats.brainChunks.toLocaleString('pt-BR')}
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="text-[10px] font-mono text-white/20">Dominios:</span>
                  <span className="text-xs font-mono font-medium text-[#06b6d4]">
                    {data.stats.brainDomains}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Zenya Level Card */}
        {zenyaLevel && zenyaLevel.hasZenya && (
          <div className="glass glass-hover rounded-2xl p-5 group relative overflow-hidden transition-all duration-300">
            {/* Ambient glow */}
            <div
              className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"
              style={{ background: 'radial-gradient(ellipse at 50% 0%, rgba(139,92,246,0.06) 0%, transparent 70%)' }}
            />

            <div className="relative z-10">
              {/* Header */}
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center"
                    style={{ background: 'rgba(139,92,246,0.12)', border: '1px solid rgba(139,92,246,0.2)' }}>
                    <ZenyaIcon size={18} />
                  </div>
                  <div className="flex flex-col">
                    <span className="text-[11px] font-mono text-white/30 uppercase tracking-widest">
                      Zenya Level
                    </span>
                  </div>
                </div>
                <div className="flex flex-col items-end gap-1">
                  <div className="flex items-center gap-1.5">
                    <span className="text-2xl font-bold font-mono text-[#8b5cf6]">
                      {zenyaLevel.level}
                    </span>
                    <span className="text-[10px] font-mono text-white/20 self-end mb-1">
                      / 10
                    </span>
                  </div>
                  <StarRating stars={zenyaLevel.stars} />
                </div>
              </div>

              {/* XP Bar */}
              <XPBar
                progress={zenyaLevel.progress}
                gradientFrom="#8b5cf6"
                gradientTo="#06b6d4"
              />

              {/* Progress details */}
              <div className="flex items-center justify-between mt-2">
                <span className="text-[10px] font-mono text-white/25">
                  {zenyaLevel.conversationsHandled.toLocaleString('pt-BR')} resolvidas
                </span>
                {!zenyaLevel.isMaxLevel ? (
                  <span className="text-[10px] font-mono text-white/25">
                    {zenyaLevel.inLevel} / {zenyaLevel.forNext} para nivel {zenyaLevel.level + 1}
                  </span>
                ) : (
                  <span className="text-[10px] font-mono text-[#8b5cf6]/60">
                    Nivel maximo
                  </span>
                )}
              </div>

              {/* Zenya stats */}
              <div className="flex items-center gap-3 mt-3 pt-3 border-t border-white/[0.04]">
                <div className="flex items-center gap-1">
                  <span className="text-[10px] font-mono text-white/20">Este mes:</span>
                  <span className="text-xs font-mono font-medium text-[#8b5cf6]">
                    {data.stats.currentMonthResolved}
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="text-[10px] font-mono text-white/20">Convertidas:</span>
                  <span className="text-xs font-mono font-medium text-[#22c55e]">
                    {data.stats.convertedConversations}
                  </span>
                </div>
                {data.stats.avgSentiment && (
                  <div className="flex items-center gap-1">
                    <span className="text-[10px] font-mono text-white/20">Sentiment:</span>
                    <span className="text-xs font-mono font-medium text-[#eab308]">
                      {data.stats.avgSentiment}
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Achievements Grid ──────────────────────────── */}
      <div className="glass rounded-2xl p-5 relative overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <span className="text-[#eab308]">
              <TrophyIcon size={16} />
            </span>
            <span className="text-[11px] font-mono text-white/30 uppercase tracking-widest">
              Conquistas
            </span>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full border border-[#eab308]/20 bg-[#eab308]/10 text-[#eab308]">
            {unlockedCount} / {totalAchievements}
          </span>
        </div>

        {/* Unlocked badges */}
        {unlockedAchievements.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2 mb-3">
            {unlockedAchievements.map((a) => (
              <AchievementBadge key={a.id} achievement={a} />
            ))}
          </div>
        )}

        {/* Locked badges (dimmed) */}
        {lockedAchievements.length > 0 && (
          <>
            {unlockedAchievements.length > 0 && (
              <div className="h-px bg-white/[0.04] my-3" />
            )}
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
              {lockedAchievements.map((a) => (
                <AchievementBadge key={a.id} achievement={a} />
              ))}
            </div>
          </>
        )}
      </div>

      {/* ── Activity Timeline ──────────────────────────── */}
      {data.timeline.length > 0 && (
        <div className="glass rounded-2xl p-5 relative overflow-hidden">
          {/* Header */}
          <div className="flex items-center gap-2 mb-4">
            <span className="text-[11px] font-mono text-white/30 uppercase tracking-widest">
              Linha do Tempo
            </span>
            <span className="text-[9px] font-mono text-white/15 ml-auto">
              Ultimos eventos
            </span>
          </div>

          {/* Timeline entries */}
          <div className="space-y-0">
            {data.timeline.map((entry, i) => (
              <TimelineItem
                key={entry.id}
                entry={entry}
                isLast={i === data.timeline.length - 1}
              />
            ))}
          </div>
        </div>
      )}

    </section>
  )
}
