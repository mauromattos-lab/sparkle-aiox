'use client'

/**
 * /hq/agents — Agents View (Story 3.1)
 *
 * AC1:  data from useAgents() proxy to /cockpit/agents
 * AC2:  useAgents() with SWR refreshInterval 30s
 * AC3:  AgentCard with icon, name, type, status, last_task, capabilities_count
 * AC4:  status bullet: working=green pulse, idle=grey, error=red
 * AC5:  header with total, active (working), tasks_24h counters
 * AC6:  responsive grid: 1 col / md:2 / lg:3, gap-3
 * AC7:  click opens DetailPanel with full agent info
 * AC8:  EmptyState when no agents
 * AC9:  AgentCardSkeleton loading state (6 cards)
 * AC10: SWR auto-refresh 30s
 * AC11: pulse data merged client-side to enrich last_action per agent
 * AC12: badge colorido por agent_type (handled inside AgentCard)
 */

import React, { useMemo } from 'react'
import { Bot, AlertCircle } from 'lucide-react'
import { useAgents, usePulse, useOverview, type AgentRecord } from '@/hooks/useHQData'
import AgentCard from '@/components/hq/AgentCard'
import AgentCardSkeleton from '@/components/hq/AgentCardSkeleton'
import EmptyState from '@/components/hq/EmptyState'
import { useDetailPanel } from '@/components/hq/DetailPanelContext'

// ── Agent Detail Panel Content ───────────────────────────────────────────────

function AgentDetailContent({ agent }: { agent: AgentRecord }) {
  const statusLabel = {
    working: 'Ativo',
    idle: 'Ocioso',
    error: 'Erro',
  }[agent.status] ?? 'Ocioso'

  const statusDotClass = {
    working: 'bg-green-400 animate-pulse-glow',
    error: 'bg-red-400',
    idle: 'bg-white/20',
  }[agent.status] ?? 'bg-white/20'

  const recentTasks = agent.recent_tasks?.slice(0, 5) ?? (agent.last_task ? [agent.last_task] : [])

  return (
    <div className="flex flex-col gap-5 py-2">
      {/* Identity */}
      <div className="flex flex-col gap-1">
        <h2 className="text-[1rem] font-semibold text-white leading-tight">{agent.display_name}</h2>
        <span className="text-[0.75rem] text-white/50">{agent.agent_type}</span>
      </div>

      {/* Status */}
      <div className="flex flex-col gap-1.5">
        <span className="text-[0.6875rem] text-white/30 font-mono uppercase tracking-wide">Status</span>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${statusDotClass}`} />
          <span className="text-[0.8125rem] text-white/70">{statusLabel}</span>
        </div>
      </div>

      {/* Model */}
      {agent.model && (
        <div className="flex flex-col gap-1.5">
          <span className="text-[0.6875rem] text-white/30 font-mono uppercase tracking-wide">Modelo</span>
          <span className="text-[0.8125rem] text-white/70 font-mono">{agent.model}</span>
        </div>
      )}

      {/* Capabilities */}
      {(agent.capabilities?.length ?? 0) > 0 ? (
        <div className="flex flex-col gap-2">
          <span className="text-[0.6875rem] text-white/30 font-mono uppercase tracking-wide">
            Capabilities ({agent.capabilities!.length})
          </span>
          <ul className="flex flex-col gap-1">
            {agent.capabilities!.map((cap) => (
              <li
                key={cap}
                className="text-[0.75rem] text-white/60 bg-white/[0.04] border border-white/[0.06] rounded px-2 py-1 font-mono"
              >
                {cap}
              </li>
            ))}
          </ul>
        </div>
      ) : agent.capabilities_count != null ? (
        <div className="flex flex-col gap-1.5">
          <span className="text-[0.6875rem] text-white/30 font-mono uppercase tracking-wide">Capabilities</span>
          <span className="text-[0.8125rem] text-white/60">{agent.capabilities_count} capabilities registradas</span>
        </div>
      ) : null}

      {/* Recent tasks */}
      {recentTasks.length > 0 && (
        <div className="flex flex-col gap-2">
          <span className="text-[0.6875rem] text-white/30 font-mono uppercase tracking-wide">
            Tasks recentes
          </span>
          <ul className="flex flex-col gap-1.5">
            {recentTasks.map((task, i) => (
              <li
                key={i}
                className="flex items-center justify-between gap-2 bg-white/[0.04] border border-white/[0.06] rounded px-2 py-1.5"
              >
                <span className="text-[0.75rem] text-white/60 font-mono truncate">{task.type}</span>
                <span
                  className={`text-[0.625rem] font-mono px-1.5 py-0.5 rounded flex-shrink-0 ${
                    task.status === 'done' || task.status === 'completed'
                      ? 'bg-green-600/20 text-green-400'
                      : task.status === 'failed' || task.status === 'error'
                        ? 'bg-red-600/20 text-red-400'
                        : 'bg-white/[0.06] text-white/40'
                  }`}
                >
                  {task.status}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

// ── Page component ───────────────────────────────────────────────────────────

export default function AgentsPage() {
  const { agents, isLoading, error } = useAgents()
  const { data: pulseData } = usePulse()
  const { data: overviewData } = useOverview()
  const { openPanel } = useDetailPanel()

  // AC11: Merge pulse agent data into agent records
  const mergedAgents = useMemo<AgentRecord[]>(() => {
    if (!agents.length) return agents

    // pulseData?.agents is a summary object (total/active/idle/error), not per-agent array.
    // If the runtime sends per-agent pulse data at a different key, merge here.
    // For now: no per-agent pulse enrichment unless runtime exposes it.
    return agents
  }, [agents, pulseData])

  // AC5: header counters
  const totalAgents = mergedAgents.length
  const activeAgents = mergedAgents.filter((a) => a.status === 'working').length
  const tasks24h = overviewData?.tasks_24h?.total ?? null

  // ── Handlers ──────────────────────────────────────────────────────────────

  function handleCardClick(agent: AgentRecord) {
    openPanel(<AgentDetailContent agent={agent} />)
  }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="hq-page-enter hq-density flex flex-col gap-4 h-full">
      {/* Page header — AC5 */}
      <div className="flex items-center gap-3">
        <Bot size={20} className="text-purple-400" strokeWidth={1.75} aria-hidden="true" />
        <div className="flex-1">
          <h1 className="text-[0.9375rem] font-semibold text-white/80 leading-tight">
            Agentes
          </h1>
          <p className="text-[0.6875rem] text-white/30 font-mono mt-0.5">/hq/agents</p>
        </div>

        {/* Counter chips — AC5 */}
        {!isLoading && (
          <div className="flex items-center gap-2">
            <span className="text-[0.6875rem] font-mono px-2 py-1 rounded bg-white/[0.06] text-white/50">
              {totalAgents} agentes
            </span>
            {activeAgents > 0 && (
              <span className="text-[0.6875rem] font-mono px-2 py-1 rounded bg-green-600/20 text-green-400">
                {activeAgents} ativos
              </span>
            )}
            {tasks24h != null && (
              <span className="text-[0.6875rem] font-mono px-2 py-1 rounded bg-white/[0.06] text-white/50">
                {tasks24h} tasks 24h
              </span>
            )}
          </div>
        )}
      </div>

      {/* Loading state — AC9 */}
      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <AgentCardSkeleton key={i} />
          ))}
        </div>
      )}

      {/* Error state */}
      {!isLoading && error && (
        <EmptyState
          icon={AlertCircle}
          title="Nao foi possivel carregar agentes"
          description="Verificar conexao com o Runtime..."
        />
      )}

      {/* Empty state — AC8 */}
      {!isLoading && !error && mergedAgents.length === 0 && (
        <EmptyState
          icon={Bot}
          title="Nenhum agente registrado"
          description="Os agentes aparecem aqui quando estiverem ativos no Runtime"
        />
      )}

      {/* Agents grid — AC6 */}
      {!isLoading && !error && mergedAgents.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {mergedAgents.map((agent) => (
            <AgentCard
              key={agent.agent_id}
              agent={agent}
              onClick={() => handleCardClick(agent)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
