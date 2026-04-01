'use client'

import { useState } from 'react'
import { useAgentWorkItems } from '@/hooks/useAgentWorkItems'
import AgentCard from '@/components/AgentCard'

// ---------------------------------------------------------------------------
// Definicao de fases — fixas, refletem o arco de implementacao do sistema
// ---------------------------------------------------------------------------

type PhaseStatus = 'completa' | 'ativa' | 'em_progresso' | 'futura'

interface Phase {
  id: string
  nome: string
  descricao: string
  status: PhaseStatus
  itens?: string[]
}

const PHASES: Phase[] = [
  {
    id: 'FASE_INFRA',
    nome: 'Infraestrutura',
    descricao: 'VPS + Coolify + Supabase operacionais',
    status: 'completa',
    itens: [
      'VPS Hostinger KVM2 provisionado',
      'Coolify instalado',
      'Supabase schema principal (6 tabelas + views)',
      'n8n workflows clientes ativos',
    ],
  },
  {
    id: 'FASE_RUNTIME',
    nome: 'Sparkle Runtime',
    descricao: 'Runtime FastAPI smoke test aprovado',
    status: 'completa',
    itens: [
      'Sparkle Runtime FastAPI porta 8001',
      'brain_ingest + brain_query handlers',
      'APScheduler (daily/weekly briefing, gap report)',
      '/zenya/learn Observer Pattern',
      'Loja Integrada handler (aguarda API key Julia)',
    ],
  },
  {
    id: 'FASE_ZENYA',
    nome: 'Zenya Multi-Cliente',
    descricao: 'Primeiro cliente go-live com Zenya ativa',
    status: 'ativa',
  },
  {
    id: 'FASE_BRAIN',
    nome: 'Brain + Friday',
    descricao: 'Friday autonoma com Brain separado',
    status: 'em_progresso',
  },
  {
    id: 'FASE_CANAIS',
    nome: 'Expansao de Canais',
    descricao: 'Instagram DM piloto funcional',
    status: 'futura',
  },
  {
    id: 'FASE_IP',
    nome: 'Personagens como IP',
    descricao: 'Lore pipeline automatizado',
    status: 'futura',
  },
]

// ---------------------------------------------------------------------------
// Icones SVG inline — sem emoji (padrao do portal)
// ---------------------------------------------------------------------------

function IconCheck() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
      stroke="rgba(52,211,153,0.7)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  )
}

function IconLock() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
      stroke="rgba(255,255,255,0.3)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  )
}

function IconRadar() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
      stroke="rgba(255,255,255,0.25)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M6.3 6.3a8 8 0 0 0 0 11.4" />
      <path d="M17.7 6.3a8 8 0 0 1 0 11.4" />
    </svg>
  )
}

function IconChevron({ open }: { open: boolean }) {
  return (
    <svg
      width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      className={`transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
    >
      <polyline points="6 9 12 15 18 9" />
    </svg>
  )
}

// ---------------------------------------------------------------------------
// PhasePill — variante por status
// ---------------------------------------------------------------------------

function PhasePill({ phase }: { phase: Phase }) {
  const isCompleta = phase.status === 'completa'
  const isAtiva = phase.status === 'ativa' || phase.status === 'em_progresso'
  const isFutura = phase.status === 'futura'

  if (isCompleta) {
    return (
      <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-emerald-500/10 border border-emerald-500/20 text-emerald-400/70 whitespace-nowrap cursor-default">
        <IconCheck />
        {phase.nome}
      </div>
    )
  }

  if (isAtiva) {
    return (
      <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-purple-600/15 border border-purple-500/40 text-white shadow-[0_0_12px_rgba(124,58,237,0.3)] whitespace-nowrap cursor-default">
        <span className="h-1.5 w-1.5 rounded-full bg-purple-400 animate-pulse" />
        {phase.nome}
      </div>
    )
  }

  // futura
  return (
    <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-zinc-800/50 border border-zinc-700/50 text-white/30 whitespace-nowrap cursor-default">
      <IconLock />
      {phase.nome}
    </div>
  )
}

// ---------------------------------------------------------------------------
// AccordionFase — fases completas colapsadas
// ---------------------------------------------------------------------------

function AccordionFase({ phase }: { phase: Phase }) {
  const [open, setOpen] = useState(false)

  return (
    <div className="border border-white/5 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center justify-between px-4 py-3 bg-zinc-900/50 text-sm text-white/40 hover:text-white/60 transition-colors"
      >
        <span>{phase.nome}</span>
        <span className="flex items-center gap-2 text-xs">
          {phase.itens?.length ?? 0} itens concluidos
          <IconChevron open={open} />
        </span>
      </button>

      {open && phase.itens && (
        <div className="px-4 py-3 flex flex-col gap-2 bg-zinc-900/30">
          {phase.itens.map(item => (
            <div key={item} className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400/60 flex-shrink-0" />
              <span className="text-xs text-white/40">{item}</span>
              <span className="ml-auto text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400/70">
                Concluido
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Pagina principal
// ---------------------------------------------------------------------------

export default function MissionControlPage() {
  const { agents, isConnected, isLoading, error } = useAgentWorkItems()

  const fasesCompletas = PHASES.filter(p => p.status === 'completa')
  const faseAtiva = PHASES.find(p => p.status === 'ativa' || p.status === 'em_progresso')

  return (
    <main className="min-h-screen bg-zinc-950 px-4 py-6 sm:px-6">

      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight">Mission Control</h1>
          <p className="text-sm text-white/40 mt-0.5">Estado dos agentes em tempo real</p>
        </div>

        {/* Realtime Indicator */}
        <div className="flex items-center gap-1.5">
          <span
            className={[
              'h-2 w-2 rounded-full transition-colors duration-500',
              isConnected ? 'bg-emerald-400 animate-pulse' : 'bg-zinc-500',
            ].join(' ')}
          />
          <span className="text-xs text-white/40">
            {isConnected ? 'Realtime' : 'Polling'}
          </span>
        </div>
      </div>

      {/* Phase Timeline */}
      <div className="flex gap-2 mb-6 overflow-x-auto pb-1" style={{ scrollbarWidth: 'none' }}>
        {PHASES.map(phase => (
          <PhasePill key={phase.id} phase={phase} />
        ))}
      </div>

      {/* Fase Ativa — titulo em evidencia */}
      {faseAtiva && (
        <div className="mb-4">
          <div className="flex items-center gap-2 mb-1">
            <span className="h-1 w-4 rounded-full bg-purple-500/60" />
            <h2 className="text-sm font-semibold text-white/70 uppercase tracking-widest">
              Fase Atual — {faseAtiva.nome}
            </h2>
          </div>
          <p className="text-xs text-white/30 ml-6">{faseAtiva.descricao}</p>
        </div>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="flex items-center justify-center py-20">
          <div className="text-white/30 text-sm animate-pulse">Carregando agentes...</div>
        </div>
      )}

      {/* Error */}
      {error && !isLoading && (
        <div className="rounded-lg border border-red-500/30 bg-red-950/20 p-4 text-sm text-red-400">
          Erro ao carregar: {error}
        </div>
      )}

      {/* Estado vazio */}
      {!isLoading && !error && agents.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 gap-3">
          <div className="w-12 h-12 rounded-full bg-zinc-800/60 border border-zinc-700/50 flex items-center justify-center">
            <IconRadar />
          </div>
          <p className="text-white/40 text-sm font-medium">Todos os agentes em standby</p>
          <p className="text-white/25 text-xs">Nenhum item registrado nas ultimas 24h</p>
        </div>
      )}

      {/* Grid de AgentCards */}
      {!isLoading && agents.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {agents.map(agent => (
            <AgentCard key={agent.agentId} agent={agent} />
          ))}
        </div>
      )}

      {/* Legenda */}
      {!isLoading && agents.length > 0 && (
        <div className="mt-6 flex flex-wrap gap-3 justify-center">
          {(
            [
              ['bg-purple-400', 'Executando'],
              ['bg-yellow-400', 'Aguardando'],
              ['bg-emerald-400', 'Concluido'],
              ['bg-red-500', 'Erro'],
              ['bg-zinc-500', 'Standby'],
            ] as const
          ).map(([color, label]) => (
            <div key={label} className="flex items-center gap-1.5">
              <span className={`h-2 w-2 rounded-full ${color}`} />
              <span className="text-xs text-white/35">{label}</span>
            </div>
          ))}
        </div>
      )}

      {/* Fases Completas — Accordion */}
      {fasesCompletas.length > 0 && (
        <div className="mt-8 flex flex-col gap-2">
          <h3 className="text-xs text-white/30 uppercase tracking-widest mb-2">Fases Concluidas</h3>
          {fasesCompletas.map(phase => (
            <AccordionFase key={phase.id} phase={phase} />
          ))}
        </div>
      )}

    </main>
  )
}
