'use client'

import { UseClientIdentityReturn, planLabel } from '@/hooks/useClientIdentity'

// ── Plan badge colors ──────────────────────────────────────

function planBadgeClass(plan: string | null): string {
  switch (plan) {
    case 'zenya_premium':
    case 'full':
      return 'bg-accent/20 text-accent-light border-accent/30'
    case 'zenya_basico':
      return 'bg-[#0ea5e9]/15 text-[#0ea5e9] border-[#0ea5e9]/25'
    case 'trafego':
      return 'bg-[#22c55e]/15 text-[#22c55e] border-[#22c55e]/25'
    default:
      return 'bg-white/10 text-white/50 border-white/10'
  }
}

// ── Initials Avatar ────────────────────────────────────────

function InitialsAvatar({ name, brandColor }: { name: string; brandColor: string | null }) {
  const initials = name
    .split(' ')
    .slice(0, 2)
    .map(w => w[0])
    .join('')
    .toUpperCase()

  const bgStyle = brandColor
    ? { backgroundColor: `${brandColor}20`, borderColor: `${brandColor}40` }
    : undefined

  return (
    <div
      className={`w-10 h-10 rounded-xl flex items-center justify-center font-semibold text-sm tracking-tight border ${
        brandColor ? '' : 'bg-accent/15 border-accent/30 text-accent-light'
      }`}
      style={brandColor ? { ...bgStyle, color: brandColor } : undefined}
    >
      {initials}
    </div>
  )
}

// ── Zenya Badge ────────────────────────────────────────────

function ZenyaBadge({ name, avatarUrl }: { name: string; avatarUrl: string | null }) {
  return (
    <div className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-[#0ea5e9]/10 border border-[#0ea5e9]/20">
      {avatarUrl ? (
        <img src={avatarUrl} alt={name} className="w-4 h-4 rounded-full" />
      ) : (
        <span className="w-4 h-4 rounded-full bg-[#0ea5e9]/30 flex items-center justify-center">
          <svg width="8" height="8" viewBox="0 0 24 24" fill="none"
            stroke="#0ea5e9" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" />
          </svg>
        </span>
      )}
      <span className="text-[10px] font-mono text-[#0ea5e9]/80 uppercase tracking-wider">
        {name}
      </span>
    </div>
  )
}

// ── ClientHeader Component ─────────────────────────────────

interface ClientHeaderProps {
  identity: UseClientIdentityReturn
  /** Additional right-side content */
  rightContent?: React.ReactNode
}

export default function ClientHeader({ identity, rightContent }: ClientHeaderProps) {
  const { isLoading, businessName, clientName, plan, zenyaName, brandColor } = identity
  const zenya = identity.identity?.zenya ?? null

  if (isLoading) {
    return (
      <div className="flex items-center gap-3 rounded-xl px-4 py-3 bg-white/[0.02] border border-white/[0.05] animate-pulse">
        <div className="w-10 h-10 rounded-xl bg-white/5" />
        <div className="flex-1">
          <div className="h-4 w-40 bg-white/5 rounded mb-1.5" />
          <div className="h-3 w-24 bg-white/5 rounded" />
        </div>
      </div>
    )
  }

  if (!businessName) return null

  return (
    <div className="flex items-center gap-3 rounded-xl px-4 py-3 bg-white/[0.03] backdrop-blur-md border border-white/[0.06]">
      {/* Logo / Initials */}
      <InitialsAvatar name={businessName} brandColor={brandColor} />

      {/* Business info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <h2 className="text-sm font-semibold text-white truncate">
            {businessName}
          </h2>
          {/* Plan badge */}
          <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${planBadgeClass(plan)}`}>
            {planLabel(plan)}
          </span>
        </div>

        <div className="flex items-center gap-2 mt-0.5">
          {clientName && clientName !== businessName && (
            <span className="text-[11px] text-white/30 font-mono truncate">
              {clientName}
            </span>
          )}
          {zenya && (
            <ZenyaBadge name={zenya.name} avatarUrl={zenya.avatar_url} />
          )}
        </div>
      </div>

      {/* Right content (nav links, logout, etc.) */}
      {rightContent}
    </div>
  )
}
