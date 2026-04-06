'use client'

/**
 * DecisionsPending — Story 1.4
 *
 * Aggregates 3 data sources into a unified prioritized decision list:
 *   RED:    Clients with health_status === "red" (from useClients)
 *   YELLOW: Follow-ups vencidos (from usePipeline — follow_up_date in past)
 *   BLUE:   Sprint items bloqueados (from usePulse — agent_work_items blocked)
 *
 * Sorted: red first, yellow second, blue third.
 * Click opens DetailPanel with relevant context.
 */

import React, { useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertTriangle,
  Clock,
  GitBranch,
  CheckCircle,
  AlertCircle,
  LucideIcon,
} from 'lucide-react'
import { useClients, usePipeline, usePulse } from '@/hooks/useHQData'
import { useAgentWorkItems, type AgentView } from '@/hooks/useAgentWorkItems'
import { useDetailPanel } from '@/components/hq/DetailPanelContext'

// ── Types ────────────────────────────────────────────────────────────────────

type Severity = 'red' | 'yellow' | 'blue'

interface DecisionItem {
  id: string
  severity: Severity
  title: string
  description: string
  type: string
  detailContent: React.ReactNode
}

// ── Severity config ──────────────────────────────────────────────────────────

const SEVERITY_META: Record<Severity, { icon: LucideIcon; color: string; label: string; priority: number }> = {
  red:    { icon: AlertTriangle, color: 'text-red-400',    label: 'Critico',   priority: 0 },
  yellow: { icon: Clock,         color: 'text-yellow-400', label: 'Follow-up', priority: 1 },
  blue:   { icon: GitBranch,     color: 'text-blue-400',   label: 'Bloqueado', priority: 2 },
}

const BADGE_COLORS: Record<Severity, string> = {
  red:    'bg-red-500/20 text-red-400',
  yellow: 'bg-yellow-500/20 text-yellow-400',
  blue:   'bg-blue-500/20 text-blue-400',
}

// ── Detail panels ────────────────────────────────────────────────────────────

function ClientDetail({ name, health, mrr, lastInteraction, notes }: {
  name: string; health: string; mrr?: number; lastInteraction?: string; notes?: string
}) {
  return (
    <div className="flex flex-col gap-3 p-4">
      <div className="flex items-center gap-2">
        <AlertTriangle size={16} className="text-red-400" strokeWidth={1.75} />
        <span className="text-[0.9375rem] font-semibold text-white/80">Cliente em risco</span>
      </div>
      <div className="flex flex-col gap-2 text-[0.8125rem]">
        <div><span className="text-white/40">Nome:</span> <span className="text-white/70">{name}</span></div>
        <div><span className="text-white/40">Status:</span> <span className="text-red-400 font-mono">{health}</span></div>
        {mrr != null && (
          <div><span className="text-white/40">MRR:</span> <span className="text-white/70">R$ {mrr}</span></div>
        )}
        {lastInteraction && (
          <div><span className="text-white/40">Ultima interacao:</span> <span className="text-white/50 font-mono text-[0.6875rem]">{lastInteraction}</span></div>
        )}
        {notes && (
          <div className="mt-1 text-white/50 text-[0.75rem] leading-relaxed">{notes}</div>
        )}
      </div>
    </div>
  )
}

function FollowUpDetail({ name, stage, followUpDate, notes, phone }: {
  name: string; stage?: string; followUpDate?: string; notes?: string; phone?: string
}) {
  return (
    <div className="flex flex-col gap-3 p-4">
      <div className="flex items-center gap-2">
        <Clock size={16} className="text-yellow-400" strokeWidth={1.75} />
        <span className="text-[0.9375rem] font-semibold text-white/80">Follow-up vencido</span>
      </div>
      <div className="flex flex-col gap-2 text-[0.8125rem]">
        <div><span className="text-white/40">Lead:</span> <span className="text-white/70">{name}</span></div>
        {stage && (
          <div><span className="text-white/40">Etapa:</span> <span className="text-white/70">{stage}</span></div>
        )}
        {followUpDate && (
          <div><span className="text-white/40">Vencimento:</span> <span className="text-yellow-400 font-mono text-[0.6875rem]">{followUpDate}</span></div>
        )}
        {phone && (
          <div><span className="text-white/40">Telefone:</span> <span className="text-white/50 font-mono text-[0.6875rem]">{phone}</span></div>
        )}
        {notes && (
          <div className="mt-1 text-white/50 text-[0.75rem] leading-relaxed">{notes}</div>
        )}
      </div>
    </div>
  )
}

function BlockedItemDetail({ agentId, status, item }: {
  agentId: string; status: string; item: AgentView['currentItem']
}) {
  return (
    <div className="flex flex-col gap-3 p-4">
      <div className="flex items-center gap-2">
        <GitBranch size={16} className="text-blue-400" strokeWidth={1.75} />
        <span className="text-[0.9375rem] font-semibold text-white/80">Sprint item bloqueado</span>
      </div>
      <div className="flex flex-col gap-2 text-[0.8125rem]">
        <div><span className="text-white/40">Agente:</span> <span className="text-white/70">{agentId}</span></div>
        <div><span className="text-white/40">Status:</span> <span className="text-blue-400 font-mono">{status}</span></div>
        {item?.output_type && (
          <div><span className="text-white/40">Tipo:</span> <span className="text-white/70">{item.output_type}</span></div>
        )}
        {item?.notes && (
          <div className="mt-1 text-white/50 text-[0.75rem] leading-relaxed">{item.notes}</div>
        )}
        {item?.created_at && (
          <div><span className="text-white/40">Criado em:</span> <span className="text-white/50 font-mono text-[0.6875rem]">{new Date(item.created_at).toLocaleString('pt-BR')}</span></div>
        )}
      </div>
    </div>
  )
}

// ── Main component ───────────────────────────────────────────────────────────

export default function DecisionsPending() {
  const { data: clientsData, isLoading: clientsLoading } = useClients()
  const { data: pipelineData, isLoading: pipelineLoading } = usePipeline()
  const { agents, isLoading: agentsLoading } = useAgentWorkItems()
  const { openPanel } = useDetailPanel()

  const isLoading = clientsLoading || pipelineLoading || agentsLoading

  // Build unified list
  const items = useMemo<DecisionItem[]>(() => {
    const result: DecisionItem[] = []
    const now = Date.now()

    // RED: clients with health_status === "red"
    const clients = Array.isArray(clientsData?.clients)
      ? clientsData!.clients
      : Array.isArray(clientsData)
      ? (clientsData as unknown as Array<{ id: string; name: string; health_status: string; mrr?: number; last_interaction?: string; notes?: string }>)
      : []

    for (const c of clients) {
      if (c.health_status === 'red') {
        result.push({
          id: `client-${c.id}`,
          severity: 'red',
          title: c.name ?? 'Cliente sem nome',
          description: 'Cliente em estado critico',
          type: 'Cliente',
          detailContent: (
            <ClientDetail
              name={c.name}
              health={c.health_status}
              mrr={c.mrr as number | undefined}
              lastInteraction={c.last_interaction as string | undefined}
              notes={c.notes as string | undefined}
            />
          ),
        })
      }
    }

    // YELLOW: pipeline leads with follow_up_date in the past
    const leads = Array.isArray(pipelineData?.leads)
      ? pipelineData!.leads
      : Array.isArray(pipelineData)
      ? (pipelineData as unknown as Array<{ id: string; name: string; stage?: string; follow_up_date?: string; notes?: string; phone?: string }>)
      : []

    for (const lead of leads) {
      if (lead.follow_up_date) {
        const followUpTime = new Date(lead.follow_up_date).getTime()
        if (followUpTime < now) {
          result.push({
            id: `pipeline-${lead.id}`,
            severity: 'yellow',
            title: lead.name ?? 'Lead sem nome',
            description: `Follow-up vencido: ${lead.follow_up_date}`,
            type: 'Pipeline',
            detailContent: (
              <FollowUpDetail
                name={lead.name}
                stage={lead.stage}
                followUpDate={lead.follow_up_date}
                notes={lead.notes}
                phone={lead.phone}
              />
            ),
          })
        }
      }
    }

    // BLUE: blocked agent work items
    for (const agent of agents) {
      if (agent.status === 'blocked') {
        result.push({
          id: `agent-${agent.agentId}-${agent.currentItem?.id ?? 'no-item'}`,
          severity: 'blue',
          title: `${agent.agentId} bloqueado`,
          description: agent.currentItem?.notes ?? agent.currentItem?.output_type ?? 'Aguardando acao',
          type: 'Sprint',
          detailContent: (
            <BlockedItemDetail
              agentId={agent.agentId}
              status={agent.currentItem?.status ?? 'blocked'}
              item={agent.currentItem}
            />
          ),
        })
      }
    }

    // Sort: red first, yellow second, blue third
    result.sort((a, b) => SEVERITY_META[a.severity].priority - SEVERITY_META[b.severity].priority)

    return result
  }, [clientsData, pipelineData, agents])

  // Track new items for slide-in animation
  const prevIdsRef = useRef<Set<string>>(new Set())
  const [newIds, setNewIds] = useState<Set<string>>(new Set())

  useEffect(() => {
    if (items.length === 0) return

    const currentIds = new Set(items.map((i) => i.id))
    const fresh = new Set<string>()

    currentIds.forEach((id) => {
      if (!prevIdsRef.current.has(id)) fresh.add(id)
    })

    if (fresh.size > 0) {
      setNewIds(fresh)
      const t = setTimeout(() => setNewIds(new Set()), 2500)
      prevIdsRef.current = currentIds
      return () => clearTimeout(t)
    }

    prevIdsRef.current = currentIds
  }, [items])

  // Count by severity for badge
  const counts = useMemo(() => {
    const c = { red: 0, yellow: 0, blue: 0 }
    for (const item of items) c[item.severity]++
    return c
  }, [items])

  const total = items.length

  return (
    <section className="flex flex-col gap-3 h-full" aria-label="Decisoes Pendentes">
      {/* Section header */}
      <div className="flex items-center gap-2">
        <AlertCircle size={14} className="text-white/30" strokeWidth={1.75} aria-hidden="true" />
        <span className="text-[0.6875rem] text-white/30 uppercase tracking-wide font-medium">
          Decisoes Pendentes
        </span>

        {/* Badge */}
        {!isLoading && total > 0 && (
          <span className="ml-auto flex items-center gap-1.5">
            {counts.red > 0 && (
              <span className={`text-[0.625rem] font-mono px-1.5 py-0.5 rounded-full ${BADGE_COLORS.red}`}>
                {counts.red}
              </span>
            )}
            {counts.yellow > 0 && (
              <span className={`text-[0.625rem] font-mono px-1.5 py-0.5 rounded-full ${BADGE_COLORS.yellow}`}>
                {counts.yellow}
              </span>
            )}
            {counts.blue > 0 && (
              <span className={`text-[0.625rem] font-mono px-1.5 py-0.5 rounded-full ${BADGE_COLORS.blue}`}>
                {counts.blue}
              </span>
            )}
            <span className="text-[0.625rem] text-white/30 font-mono">
              {total} pendente{total !== 1 ? 's' : ''}
            </span>
          </span>
        )}
      </div>

      {/* Content area */}
      <div className="glass rounded-xl flex-1 overflow-hidden p-2 max-h-[360px] xl:max-h-none xl:overflow-y-auto">
        {isLoading ? (
          <DecisionsSkeleton />
        ) : total === 0 ? (
          <EmptyState />
        ) : (
          <div
            className="flex flex-col divide-y divide-white/[0.04]"
            role="list"
            aria-label="Lista de decisoes pendentes"
          >
            {items.map((item) => (
              <DecisionRow
                key={item.id}
                item={item}
                isNew={newIds.has(item.id)}
                onClick={() => openPanel(item.detailContent)}
              />
            ))}
          </div>
        )}
      </div>
    </section>
  )
}

// ── Decision row ─────────────────────────────────────────────────────────────

function DecisionRow({ item, isNew, onClick }: {
  item: DecisionItem; isNew: boolean; onClick: () => void
}) {
  const meta = SEVERITY_META[item.severity]
  const Icon = meta.icon

  return (
    <div
      className={[
        'flex gap-2 items-start px-2 py-2 rounded-md cursor-pointer min-h-[48px]',
        'transition-colors duration-150 hover:bg-white/[0.08]',
        isNew ? 'animate-[slideIn_0.3s_ease-out] bg-purple-500/[0.08] animate-[highlightFade_2s_ease-out_0.3s_forwards]' : '',
      ]
        .filter(Boolean)
        .join(' ')}
      role="listitem"
      onClick={onClick}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onClick() }}
      tabIndex={0}
    >
      <Icon
        size={13}
        className={`${meta.color} shrink-0 mt-1`}
        strokeWidth={1.75}
        aria-hidden="true"
      />
      <div className="flex flex-col gap-0.5 flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-[0.8125rem] text-white/70 leading-snug truncate">
            {item.title}
          </span>
          <span className={`text-[0.5625rem] font-mono px-1 py-0.5 rounded ${BADGE_COLORS[item.severity]} shrink-0`}>
            {item.type}
          </span>
        </div>
        <span className="text-[0.6875rem] text-white/40 leading-snug line-clamp-1">
          {item.description}
        </span>
      </div>
    </div>
  )
}

// ── Empty state ──────────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-32 gap-2">
      <CheckCircle size={24} className="text-green-400/60" strokeWidth={1.5} />
      <p className="text-[0.8125rem] text-white/40">Nenhuma decisao pendente</p>
      <p className="text-[0.6875rem] text-white/20">Tudo sob controle.</p>
    </div>
  )
}

// ── Loading skeleton ─────────────────────────────────────────────────────────

function DecisionsSkeleton() {
  return (
    <div className="flex flex-col gap-2 p-1">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="flex gap-2 items-start px-2 py-2 animate-pulse">
          <div className="w-[13px] h-[13px] rounded-full bg-white/[0.06] mt-1 shrink-0" />
          <div className="flex flex-col gap-1.5 flex-1">
            <div className="h-3 bg-white/[0.06] rounded w-2/3" />
            <div className="h-2.5 bg-white/[0.04] rounded w-1/2" />
          </div>
        </div>
      ))}
    </div>
  )
}
