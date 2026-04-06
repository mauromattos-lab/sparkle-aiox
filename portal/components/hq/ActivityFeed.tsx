'use client'

/**
 * ActivityFeed — timeline of the last 20 runtime events.
 * AC11: timestamp (monospace 11px), icon by event type, short description.
 * AC12: auto-refresh via SWR (30s), new items appear at top with highlight fade-out.
 * AC16: error state.
 */

import React, { useEffect, useRef, useState } from 'react'
import {
  Brain,
  Clock,
  MessageCircle,
  Bot,
  GitBranch,
  Zap,
  AlertCircle,
  Activity,
  LucideIcon,
} from 'lucide-react'
import { useActivity, type ActivityEvent } from '@/hooks/useHQData'
import { ActivityFeedSkeleton } from './LoadingSkeleton'

// ── Event type → Lucide icon ──────────────────────────────────────────────────

const EVENT_ICONS: Record<string, { icon: LucideIcon; color: string }> = {
  brain: { icon: Brain, color: 'text-purple-400' },
  cron: { icon: Clock, color: 'text-cyan-400' },
  zenya: { icon: MessageCircle, color: 'text-green-400' },
  agent: { icon: Bot, color: 'text-blue-400' },
  pipeline: { icon: GitBranch, color: 'text-yellow-400' },
  trigger: { icon: Zap, color: 'text-orange-400' },
  error: { icon: AlertCircle, color: 'text-red-400' },
}

function getEventMeta(type: string) {
  const lower = type?.toLowerCase() ?? ''
  for (const [key, meta] of Object.entries(EVENT_ICONS)) {
    if (lower.includes(key)) return meta
  }
  return { icon: Activity, color: 'text-white/40' }
}

// ── Time formatter ────────────────────────────────────────────────────────────

function formatTime(ts: string): string {
  try {
    const d = new Date(ts)
    return d.toLocaleTimeString('pt-BR', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    })
  } catch {
    return '--:--:--'
  }
}

// ── Single feed item ──────────────────────────────────────────────────────────

interface FeedItemProps {
  event: ActivityEvent
  isNew: boolean
}

function FeedItem({ event, isNew }: FeedItemProps) {
  const meta = getEventMeta(event.event_type)
  const Icon = meta.icon

  return (
    <div
      className={[
        'flex gap-2 items-start px-2 py-1.5 rounded-md cursor-pointer min-h-[48px]',
        'transition-colors duration-150 hover:bg-white/[0.04]',
        isNew ? 'bg-purple-500/[0.08] animate-[highlightFade_2s_ease-out_forwards]' : '',
      ]
        .filter(Boolean)
        .join(' ')}
      role="listitem"
    >
      <Icon
        size={13}
        className={`${meta.color} shrink-0 mt-0.5`}
        strokeWidth={1.75}
        aria-hidden="true"
      />
      <div className="flex flex-col gap-0.5 flex-1 min-w-0">
        <span className="text-[0.6875rem] text-white/30 font-mono leading-none">
          {formatTime(event.timestamp)}
        </span>
        <span className="text-[0.8125rem] text-white/70 leading-snug line-clamp-2">
          {event.description ?? event.event_type}
        </span>
      </div>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function ActivityFeed() {
  const { data, error, isLoading } = useActivity()

  // Track IDs of newly appeared events to trigger highlight animation
  const prevIdsRef = useRef<Set<string>>(new Set())
  const [newIds, setNewIds] = useState<Set<string>>(new Set())

  const events: ActivityEvent[] = Array.isArray(data?.events)
    ? data!.events.slice(0, 20)
    : Array.isArray(data)
    ? (data as ActivityEvent[]).slice(0, 20)
    : []

  useEffect(() => {
    if (events.length === 0) return

    const incoming = new Set(events.map((e) => e.id ?? e.timestamp + e.event_type))
    const fresh = new Set<string>()
    incoming.forEach((id) => {
      if (!prevIdsRef.current.has(id)) fresh.add(id)
    })

    if (fresh.size > 0) {
      setNewIds(fresh)
      // Clear highlights after 2.5s
      const t = setTimeout(() => setNewIds(new Set()), 2500)
      prevIdsRef.current = incoming
      return () => clearTimeout(t)
    }

    prevIdsRef.current = incoming
  }, [events])

  if (isLoading) return <ActivityFeedSkeleton lines={8} />

  if (error || (data as { error?: string })?.error) {
    return (
      <div className="flex flex-col items-center justify-center h-32 gap-2">
        <AlertCircle size={20} className="text-red-400/60" />
        <p className="text-[0.75rem] text-white/30 text-center">
          Nao foi possivel carregar.
          <br />
          Tentando novamente...
        </p>
      </div>
    )
  }

  if (events.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-32 gap-2">
        <Activity size={20} className="text-white/20" />
        <p className="text-[0.75rem] text-white/30">Nenhuma atividade recente</p>
      </div>
    )
  }

  return (
    <div
      className="flex flex-col divide-y divide-white/[0.04] overflow-y-auto"
      role="list"
      aria-label="Activity feed"
    >
      {events.map((event) => {
        const id = event.id ?? event.timestamp + event.event_type
        return <FeedItem key={id} event={event} isNew={newIds.has(id)} />
      })}
    </div>
  )
}
