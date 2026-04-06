'use client'

/**
 * SprintItemsSection — agent_work_items grouped by status.
 * Story 3.2 — AC8, IV4
 *
 * Groups: Em andamento (in_progress) | Pendentes (todo) | Bloqueados (blocked) | Concluidos (done)
 * Concluidos: max 10 items, sorted by updated_at desc.
 */

import React from 'react'
import { Layers } from 'lucide-react'
import type { AgentWorkItem } from '@/hooks/useHQData'
import { relativeTime } from '@/components/hq/WorkflowList'

// ── Group config ──────────────────────────────────────────────────────────────

interface GroupConfig {
  key: AgentWorkItem['status']
  label: string
  headerClass: string
  dotClass: string
}

const GROUPS: GroupConfig[] = [
  {
    key: 'in_progress',
    label: 'Em andamento',
    headerClass: 'text-yellow-400',
    dotClass: 'bg-yellow-400',
  },
  {
    key: 'todo',
    label: 'Pendentes',
    headerClass: 'text-white/60',
    dotClass: 'bg-white/30',
  },
  {
    key: 'blocked',
    label: 'Bloqueados',
    headerClass: 'text-red-400',
    dotClass: 'bg-red-400',
  },
  {
    key: 'done',
    label: 'Concluidos',
    headerClass: 'text-green-400',
    dotClass: 'bg-green-400',
  },
]

// ── Item card ─────────────────────────────────────────────────────────────────

function SprintItemCard({ item }: { item: AgentWorkItem }) {
  return (
    <div className="flex flex-col gap-1 bg-white/[0.03] border border-white/[0.06] rounded p-2.5">
      <div className="flex items-start justify-between gap-2">
        <span className="text-[0.8125rem] text-white/70 font-medium font-mono leading-snug">
          {item.sprint_item}
        </span>
        <span className="text-[0.6875rem] text-white/30 font-mono shrink-0 whitespace-nowrap">
          {relativeTime(item.updated_at ?? item.created_at)}
        </span>
      </div>
      {item.handoff_to && (
        <span className="text-[0.6875rem] text-purple-400/70">→ {item.handoff_to}</span>
      )}
      {item.notes && (
        <span className="text-[0.6875rem] text-white/35 leading-relaxed line-clamp-2">
          {item.notes}
        </span>
      )}
    </div>
  )
}

// ── SprintItemsSection ────────────────────────────────────────────────────────

interface SprintItemsSectionProps {
  items: AgentWorkItem[]
}

export default function SprintItemsSection({ items }: SprintItemsSectionProps) {
  const grouped = React.useMemo(() => {
    const map: Record<AgentWorkItem['status'], AgentWorkItem[]> = {
      in_progress: [],
      todo: [],
      blocked: [],
      done: [],
    }
    for (const item of items) {
      const status = item.status as AgentWorkItem['status']
      if (map[status]) {
        map[status].push(item)
      }
    }
    // Sort done by updated_at desc, limit to 10
    map.done = map.done
      .sort((a, b) => {
        const aTime = new Date(a.updated_at ?? a.created_at).getTime()
        const bTime = new Date(b.updated_at ?? b.created_at).getTime()
        return bTime - aTime
      })
      .slice(0, 10)
    return map
  }, [items])

  const totalDone = items.filter((i) => i.status === 'done').length
  const showingDoneNote = totalDone > 10

  return (
    <div className="flex flex-col gap-3">
      {/* Section header */}
      <div className="flex items-center gap-2">
        <Layers size={16} className="text-purple-400" strokeWidth={1.75} />
        <h2 className="text-[0.875rem] font-semibold text-white/70">Sprint Items</h2>
        <span className="text-[0.6875rem] text-white/30 font-mono">{items.length} total</span>
      </div>

      {/* 4-column grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
        {GROUPS.map((group) => {
          const groupItems = grouped[group.key]
          return (
            <div
              key={group.key}
              className="bg-white/[0.04] backdrop-blur-xl border border-white/[0.08] rounded-lg overflow-hidden"
            >
              {/* Group header */}
              <div className="flex items-center gap-2 px-3 py-2 border-b border-white/[0.06] bg-white/[0.02]">
                <span className={`w-2 h-2 rounded-full shrink-0 ${group.dotClass}`} />
                <span className={`text-[0.75rem] font-semibold ${group.headerClass}`}>
                  {group.label}
                </span>
                <span className="text-[0.6875rem] text-white/30 font-mono ml-auto">
                  {groupItems.length}
                </span>
              </div>

              {/* Items */}
              <div className="flex flex-col gap-1.5 p-2">
                {groupItems.length === 0 ? (
                  <p className="text-[0.6875rem] text-white/20 text-center py-3">
                    Nenhum item
                  </p>
                ) : (
                  <>
                    {groupItems.map((item) => (
                      <SprintItemCard key={item.id} item={item} />
                    ))}
                    {group.key === 'done' && showingDoneNote && (
                      <p className="text-[0.625rem] text-white/25 text-center pt-1">
                        Mostrando 10 mais recentes
                      </p>
                    )}
                  </>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
