'use client'

/**
 * KPICard — metric tile for Command Center.
 * AC7: icon, label, value (24px bold), optional trend arrow, color.
 * AC8: used for MRR, Clientes, Leads, Tasks.
 * AC9: responsive grid (parent does layout).
 * AC10: optional click navigation or tooltip.
 */

import React, { useState } from 'react'
import {
  DollarSign,
  Users,
  GitBranch,
  Activity,
  TrendingUp,
  TrendingDown,
  Minus,
  LucideIcon,
} from 'lucide-react'
import { useRouter } from 'next/navigation'

// ── Icon registry ─────────────────────────────────────────────────────────────

const ICON_MAP: Record<string, LucideIcon> = {
  DollarSign,
  Users,
  GitBranch,
  Activity,
  TrendingUp,
  TrendingDown,
}

function resolveIcon(name: string): LucideIcon {
  return ICON_MAP[name] ?? Activity
}

// ── Types ─────────────────────────────────────────────────────────────────────

export interface KPICardProps {
  label: string
  value: string | number
  icon: string                    // Lucide icon name
  trend?: 'up' | 'down' | 'neutral'
  color?: string                  // Tailwind text color class, e.g. "text-purple-400"
  href?: string                   // navigate on click
  tooltip?: string                // show tooltip on click (used for Tasks)
  className?: string
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function TrendIcon({ trend }: { trend?: 'up' | 'down' | 'neutral' }) {
  if (!trend || trend === 'neutral') return <Minus size={10} className="text-white/30" />
  if (trend === 'up') return <TrendingUp size={10} className="text-green-400" />
  return <TrendingDown size={10} className="text-red-400" />
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function KPICard({
  label,
  value,
  icon,
  trend,
  color = 'text-purple-400',
  href,
  tooltip,
  className = '',
}: KPICardProps) {
  const router = useRouter()
  const [showTooltip, setShowTooltip] = useState(false)
  const Icon = resolveIcon(icon)

  const isInteractive = Boolean(href || tooltip)

  function handleClick() {
    if (href) {
      router.push(href)
    } else if (tooltip) {
      setShowTooltip(true)
      setTimeout(() => setShowTooltip(false), 2500)
    }
  }

  return (
    <div
      className={[
        'glass rounded-xl p-3 flex flex-col gap-1.5 min-h-[80px] relative',
        'transition-all duration-150',
        isInteractive
          ? 'cursor-pointer hover:-translate-y-0.5 hover:border-purple-500/30 hover:shadow-[0_0_16px_rgba(124,58,237,0.12)]'
          : '',
        className,
      ]
        .filter(Boolean)
        .join(' ')}
      onClick={isInteractive ? handleClick : undefined}
      role={isInteractive ? 'button' : undefined}
      tabIndex={isInteractive ? 0 : undefined}
      onKeyDown={
        isInteractive
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') handleClick()
            }
          : undefined
      }
      aria-label={`${label}: ${value}`}
    >
      {/* Label row */}
      <div className="flex items-center justify-between">
        <span className="text-[0.6875rem] text-white/40 uppercase tracking-wide font-medium">
          {label}
        </span>
        <Icon size={13} className={`${color} opacity-70`} strokeWidth={1.75} aria-hidden="true" />
      </div>

      {/* Value */}
      <span className="text-[1.5rem] font-bold text-white leading-none tracking-tight">
        {value}
      </span>

      {/* Trend */}
      {trend !== undefined && (
        <div className="flex items-center gap-0.5 mt-auto">
          <TrendIcon trend={trend} />
        </div>
      )}

      {/* Tooltip overlay */}
      {showTooltip && tooltip && (
        <div
          className="absolute inset-0 flex items-center justify-center rounded-xl bg-[#020208]/80 backdrop-blur-sm z-10"
          aria-live="polite"
        >
          <span className="text-[0.75rem] text-white/60 text-center px-2">{tooltip}</span>
        </div>
      )}
    </div>
  )
}
