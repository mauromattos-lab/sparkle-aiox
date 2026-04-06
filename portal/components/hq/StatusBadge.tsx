'use client'

/**
 * StatusBadge — reusable health status indicator.
 * AC5: props { status, size? }. Circle + optional label.
 * AC6: text labels for accessibility (green=Ativo, yellow=Atencao, red=Critico).
 *
 * Reused across Clients view, Agentes view, and anywhere health indicators appear.
 */

import React from 'react'

export type HealthStatus = 'green' | 'yellow' | 'red'

interface StatusBadgeProps {
  status: HealthStatus
  size?: 'sm' | 'md'
  showLabel?: boolean
  className?: string
}

const STATUS_CONFIG: Record<HealthStatus, { color: string; label: string }> = {
  green:  { color: '#22c55e', label: 'Ativo' },
  yellow: { color: '#eab308', label: 'Atencao' },
  red:    { color: '#ef4444', label: 'Critico' },
}

export default function StatusBadge({
  status,
  size = 'sm',
  showLabel = true,
  className = '',
}: StatusBadgeProps) {
  const config = STATUS_CONFIG[status]
  const dotSize = size === 'sm' ? 8 : 12

  return (
    <span className={`inline-flex items-center gap-1.5 ${className}`}>
      <span
        className="rounded-full shrink-0"
        style={{
          width: dotSize,
          height: dotSize,
          backgroundColor: config.color,
          boxShadow: `0 0 6px ${config.color}40`,
        }}
        aria-hidden="true"
      />
      {showLabel && (
        <span
          className="text-[0.6875rem] font-medium"
          style={{ color: config.color }}
        >
          {config.label}
        </span>
      )}
      <span className="sr-only">{config.label}</span>
    </span>
  )
}
