'use client'

import React from 'react'

type CardProps = {
  title: string
  value: string
  subtitle?: string
  accent?: 'purple' | 'cyan' | 'green' | 'yellow'
  icon?: React.ReactNode
  /** Destaque maior: ocupa toda a largura, valor em fonte maior */
  highlight?: boolean
}

const accentMap = {
  purple: {
    border: 'border-accent/30',
    dot: 'bg-accent-light',
    text: 'text-gradient-accent',
    glow: 'glow-accent',
    bg: 'from-accent/5 to-transparent',
  },
  cyan: {
    border: 'border-cyan/30',
    dot: 'bg-cyan',
    text: 'text-gradient-cyan',
    glow: 'glow-cyan',
    bg: 'from-cyan/5 to-transparent',
  },
  green: {
    border: 'border-emerald-500/30',
    dot: 'bg-emerald-400',
    text: 'text-emerald-400',
    glow: '',
    bg: 'from-emerald-500/5 to-transparent',
  },
  yellow: {
    border: 'border-yellow-500/30',
    dot: 'bg-yellow-400',
    text: 'text-yellow-400',
    glow: '',
    bg: 'from-yellow-500/5 to-transparent',
  },
}

export default function Card({ title, value, subtitle, accent = 'purple', icon, highlight = false }: CardProps) {
  const colors = accentMap[accent]

  return (
    <div
      className={`glass glass-hover rounded-2xl ${colors.border} ${colors.glow} transition-all duration-200
        ${highlight
          ? `p-6 bg-gradient-to-br ${colors.bg} w-full`
          : 'p-5'
        }`}
    >
      <div className="flex items-start justify-between mb-3">
        <p className="text-sm font-medium text-slate-400 uppercase tracking-wider">{title}</p>
        {icon && <span className="text-slate-500">{icon}</span>}
      </div>
      <p className={`font-bold ${colors.text} ${highlight ? 'text-3xl' : 'text-2xl'}`}>{value}</p>
      {subtitle && <p className="text-sm text-slate-500 mt-1">{subtitle}</p>}
    </div>
  )
}
