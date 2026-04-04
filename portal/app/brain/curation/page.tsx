'use client'

import { useEffect, useState, useCallback } from 'react'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface BrainChunk {
  id: string
  content_preview: string
  source_title: string | null
  source_type: string | null
  source_url: string | null
  domain: string
  pipeline_type: string | null
  created_at: string | null
  confidence_score: number | null
  curation_status: string
  curation_note: string | null
  curated_at: string | null
  brain_owner: string | null
}

interface CurationStats {
  pending: number
  approved: number
  rejected: number
  total: number
  approval_rate: number
}

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const RUNTIME_URL = process.env.NEXT_PUBLIC_RUNTIME_URL || 'https://runtime.sparkleai.tech'

// ---------------------------------------------------------------------------
// Icons (inline SVG, no emoji — portal pattern)
// ---------------------------------------------------------------------------

function IconCheck() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  )
}

function IconX() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  )
}

function IconBrain() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9.5 2a3 3 0 0 0-3 3v.5A3.5 3.5 0 0 0 3 9c0 1.5 1 2.8 2.4 3.3a3 3 0 0 0 3.6 3.6A3 3 0 0 0 12 18a3 3 0 0 0 3-2.1 3 3 0 0 0 3.6-3.6A3.5 3.5 0 0 0 21 9a3.5 3.5 0 0 0-3.5-3.5V5a3 3 0 0 0-3-3 3 3 0 0 0-2.5 1.3A3 3 0 0 0 9.5 2z" />
      <path d="M12 2v16" />
    </svg>
  )
}

function IconFilter() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
    </svg>
  )
}

function IconLoader() {
  return (
    <svg className="animate-spin w-5 h-5 text-purple-400" viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
    </svg>
  )
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'agora'
  if (mins < 60) return `${mins}min`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h`
  const days = Math.floor(hours / 24)
  return `${days}d`
}

function domainColor(domain: string): string {
  const colors: Record<string, string> = {
    marketing: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    vendas: 'bg-green-500/20 text-green-400 border-green-500/30',
    copywriting: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    branding: 'bg-pink-500/20 text-pink-400 border-pink-500/30',
    tecnologia: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
    negocios: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
    produto: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
    atendimento: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    lideranca: 'bg-red-500/20 text-red-400 border-red-500/30',
    financeiro: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    operacoes: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
    conteudo: 'bg-violet-500/20 text-violet-400 border-violet-500/30',
    trafego_pago: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30',
  }
  return colors[domain] || 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30'
}

// ---------------------------------------------------------------------------
// Stats Bar
// ---------------------------------------------------------------------------

function StatsBar({ stats, loading }: { stats: CurationStats | null; loading: boolean }) {
  if (loading || !stats) {
    return (
      <div className="glass rounded-xl p-4 mb-6 flex items-center justify-center">
        <IconLoader />
      </div>
    )
  }

  return (
    <div className="glass rounded-xl p-4 mb-6">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="flex flex-col items-center">
          <span className="text-2xl font-bold text-yellow-400">{stats.pending}</span>
          <span className="text-xs text-white/40 mt-1">Pendentes</span>
        </div>
        <div className="flex flex-col items-center">
          <span className="text-2xl font-bold text-emerald-400">{stats.approved}</span>
          <span className="text-xs text-white/40 mt-1">Aprovados</span>
        </div>
        <div className="flex flex-col items-center">
          <span className="text-2xl font-bold text-red-400">{stats.rejected}</span>
          <span className="text-xs text-white/40 mt-1">Rejeitados</span>
        </div>
        <div className="flex flex-col items-center">
          <span className="text-2xl font-bold text-purple-400">{stats.approval_rate}%</span>
          <span className="text-xs text-white/40 mt-1">Taxa de Aprovacao</span>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Chunk Card
// ---------------------------------------------------------------------------

function ChunkCard({
  chunk,
  onApprove,
  onReject,
  isActioning,
}: {
  chunk: BrainChunk
  onApprove: (id: string) => void
  onReject: (id: string, reason: string) => void
  isActioning: boolean
}) {
  const [showRejectInput, setShowRejectInput] = useState(false)
  const [rejectReason, setRejectReason] = useState('')
  const [expanded, setExpanded] = useState(false)

  const isPending = chunk.curation_status === 'pending'

  return (
    <div className="glass rounded-xl p-4 transition-all duration-200 hover:border-white/12 group">
      {/* Header row */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex flex-wrap items-center gap-2 min-w-0">
          {/* Domain pill */}
          <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full border ${domainColor(chunk.domain)}`}>
            {chunk.domain}
          </span>
          {/* Source type */}
          {chunk.source_type && (
            <span className="text-[10px] text-white/30 bg-white/5 px-2 py-0.5 rounded-full">
              {chunk.source_type}
            </span>
          )}
          {/* Confidence */}
          {chunk.confidence_score != null && (
            <span className="text-[10px] text-white/30">
              conf: {(chunk.confidence_score * 100).toFixed(0)}%
            </span>
          )}
        </div>
        {/* Timestamp */}
        <span className="text-[10px] text-white/25 whitespace-nowrap flex-shrink-0">
          {timeAgo(chunk.created_at)}
        </span>
      </div>

      {/* Source title */}
      {chunk.source_title && (
        <p className="text-xs font-medium text-white/60 mb-2 truncate" title={chunk.source_title}>
          {chunk.source_title}
        </p>
      )}

      {/* Content preview */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="text-left w-full"
      >
        <p className={`text-sm text-white/80 leading-relaxed ${expanded ? '' : 'line-clamp-3'}`}>
          {chunk.content_preview}
        </p>
        {chunk.content_preview.length >= 180 && !expanded && (
          <span className="text-[10px] text-purple-400 mt-1 inline-block">ver mais</span>
        )}
      </button>

      {/* Curation note (for already reviewed) */}
      {chunk.curation_note && (
        <div className="mt-2 px-3 py-2 rounded-lg bg-white/3 border border-white/5">
          <span className="text-[10px] text-white/40">Nota: </span>
          <span className="text-xs text-white/60">{chunk.curation_note}</span>
        </div>
      )}

      {/* Action buttons (only for pending) */}
      {isPending && (
        <div className="mt-4 flex items-center gap-2">
          <button
            onClick={() => onApprove(chunk.id)}
            disabled={isActioning}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
                       bg-emerald-500/15 border border-emerald-500/30 text-emerald-400
                       hover:bg-emerald-500/25 hover:border-emerald-500/50
                       disabled:opacity-40 disabled:cursor-not-allowed
                       transition-all duration-200"
          >
            <IconCheck />
            Aprovar
          </button>

          {!showRejectInput ? (
            <button
              onClick={() => setShowRejectInput(true)}
              disabled={isActioning}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
                         bg-red-500/10 border border-red-500/20 text-red-400
                         hover:bg-red-500/20 hover:border-red-500/40
                         disabled:opacity-40 disabled:cursor-not-allowed
                         transition-all duration-200"
            >
              <IconX />
              Rejeitar
            </button>
          ) : (
            <div className="flex items-center gap-2 flex-1">
              <input
                type="text"
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="Motivo (opcional)..."
                className="flex-1 px-3 py-1.5 rounded-lg text-xs bg-zinc-900 border border-red-500/30
                           text-white/80 placeholder:text-white/20 outline-none
                           focus:border-red-500/50 transition-colors"
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    onReject(chunk.id, rejectReason)
                    setShowRejectInput(false)
                    setRejectReason('')
                  }
                  if (e.key === 'Escape') {
                    setShowRejectInput(false)
                    setRejectReason('')
                  }
                }}
              />
              <button
                onClick={() => {
                  onReject(chunk.id, rejectReason)
                  setShowRejectInput(false)
                  setRejectReason('')
                }}
                disabled={isActioning}
                className="px-3 py-1.5 rounded-lg text-xs font-medium
                           bg-red-500/20 border border-red-500/30 text-red-400
                           hover:bg-red-500/30 transition-all duration-200"
              >
                Confirmar
              </button>
              <button
                onClick={() => {
                  setShowRejectInput(false)
                  setRejectReason('')
                }}
                className="px-2 py-1.5 rounded-lg text-xs text-white/30 hover:text-white/60 transition-colors"
              >
                Cancelar
              </button>
            </div>
          )}
        </div>
      )}

      {/* Status badge for reviewed chunks */}
      {!isPending && (
        <div className="mt-3 flex items-center gap-2">
          <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full border ${
            chunk.curation_status === 'approved'
              ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400'
              : 'bg-red-500/10 border-red-500/20 text-red-400'
          }`}>
            {chunk.curation_status === 'approved' ? 'Aprovado' : 'Rejeitado'}
          </span>
          {chunk.curated_at && (
            <span className="text-[10px] text-white/25">{timeAgo(chunk.curated_at)}</span>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function BrainCurationPage() {
  const [chunks, setChunks] = useState<BrainChunk[]>([])
  const [stats, setStats] = useState<CurationStats | null>(null)
  const [filter, setFilter] = useState<'pending' | 'approved' | 'rejected'>('pending')
  const [loading, setLoading] = useState(true)
  const [statsLoading, setStatsLoading] = useState(true)
  const [actioningId, setActioningId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Fetch stats
  const loadStats = useCallback(async () => {
    try {
      setStatsLoading(true)
      const res = await fetch(`${RUNTIME_URL}/brain/curation/stats`)
      const data = await res.json()
      if (data.status === 'ok') {
        setStats(data)
      }
    } catch {
      // Stats are non-critical
    } finally {
      setStatsLoading(false)
    }
  }, [])

  // Fetch chunks
  const loadChunks = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const res = await fetch(`${RUNTIME_URL}/brain/curation/queue?status=${filter}&limit=30`)
      const data = await res.json()
      if (data.status === 'ok') {
        setChunks(data.chunks)
      } else {
        setError(data.error || 'Erro ao carregar chunks')
      }
    } catch (err) {
      setError('Falha de conexao com o Runtime')
    } finally {
      setLoading(false)
    }
  }, [filter])

  useEffect(() => {
    loadStats()
    loadChunks()
  }, [loadStats, loadChunks])

  // Approve
  const handleApprove = async (chunkId: string) => {
    setActioningId(chunkId)
    try {
      const res = await fetch(`${RUNTIME_URL}/brain/curation/${chunkId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      })
      const data = await res.json()
      if (data.status === 'ok') {
        // Remove from current list (if viewing pending)
        setChunks(prev => prev.filter(c => c.id !== chunkId))
        loadStats()
      }
    } catch {
      // Silently fail — chunk stays in list
    } finally {
      setActioningId(null)
    }
  }

  // Reject
  const handleReject = async (chunkId: string, reason: string) => {
    setActioningId(chunkId)
    try {
      const res = await fetch(`${RUNTIME_URL}/brain/curation/${chunkId}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: reason || undefined }),
      })
      const data = await res.json()
      if (data.status === 'ok') {
        setChunks(prev => prev.filter(c => c.id !== chunkId))
        loadStats()
      }
    } catch {
      // Silently fail
    } finally {
      setActioningId(null)
    }
  }

  return (
    <main className="min-h-screen bg-zinc-950 px-4 py-6 sm:px-6">
      {/* Ambient glow */}
      <div aria-hidden="true" className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute top-[-10%] left-[40%] w-[600px] h-[400px] rounded-full bg-accent/6 blur-[140px]" />
        <div className="absolute bottom-[10%] right-[10%] w-[400px] h-[400px] rounded-full bg-cyan/4 blur-[120px]" />
      </div>

      {/* Header */}
      <div className="relative z-10 mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-purple-500/15 border border-purple-500/30 flex items-center justify-center text-purple-400">
            <IconBrain />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white tracking-tight">Brain Curation</h1>
            <p className="text-sm text-white/40 mt-0.5">Qualidade acima de volume</p>
          </div>
        </div>

        {/* Back to Mission Control */}
        <a
          href="/mission-control"
          className="text-xs text-white/30 hover:text-white/60 transition-colors px-3 py-1.5 rounded-lg border border-white/5 hover:border-white/10"
        >
          Mission Control
        </a>
      </div>

      {/* Stats */}
      <div className="relative z-10">
        <StatsBar stats={stats} loading={statsLoading} />
      </div>

      {/* Filter tabs */}
      <div className="relative z-10 flex gap-2 mb-6">
        {([
          { key: 'pending' as const, label: 'Pendentes', count: stats?.pending },
          { key: 'approved' as const, label: 'Aprovados', count: stats?.approved },
          { key: 'rejected' as const, label: 'Rejeitados', count: stats?.rejected },
        ]).map(({ key, label, count }) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 ${
              filter === key
                ? 'bg-purple-500/20 border border-purple-500/40 text-white shadow-[0_0_12px_rgba(124,58,237,0.2)]'
                : 'bg-white/4 border border-white/8 text-white/40 hover:text-white/60 hover:border-white/12'
            }`}
          >
            <IconFilter />
            {label}
            {count != null && (
              <span className={`text-[10px] ml-1 ${filter === key ? 'text-purple-300' : 'text-white/25'}`}>
                {count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Loading */}
      {loading && (
        <div className="relative z-10 flex items-center justify-center py-20">
          <div className="flex flex-col items-center gap-3">
            <IconLoader />
            <span className="text-white/30 text-sm">Carregando chunks...</span>
          </div>
        </div>
      )}

      {/* Error */}
      {error && !loading && (
        <div className="relative z-10 rounded-lg border border-red-500/30 bg-red-950/20 p-4 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && chunks.length === 0 && (
        <div className="relative z-10 flex flex-col items-center justify-center py-20 gap-3">
          <div className="w-12 h-12 rounded-full bg-zinc-800/60 border border-zinc-700/50 flex items-center justify-center text-white/25">
            <IconBrain />
          </div>
          <p className="text-white/40 text-sm font-medium">
            {filter === 'pending'
              ? 'Nenhum chunk pendente de revisao'
              : filter === 'approved'
                ? 'Nenhum chunk aprovado ainda'
                : 'Nenhum chunk rejeitado'
            }
          </p>
          {filter === 'pending' && (
            <p className="text-white/25 text-xs">O Brain esta limpo. Bom trabalho.</p>
          )}
        </div>
      )}

      {/* Chunks list */}
      {!loading && chunks.length > 0 && (
        <div className="relative z-10 grid grid-cols-1 lg:grid-cols-2 gap-3">
          {chunks.map(chunk => (
            <ChunkCard
              key={chunk.id}
              chunk={chunk}
              onApprove={handleApprove}
              onReject={handleReject}
              isActioning={actioningId === chunk.id}
            />
          ))}
        </div>
      )}

      {/* Chunk count */}
      {!loading && chunks.length > 0 && (
        <div className="relative z-10 mt-6 text-center">
          <span className="text-xs text-white/20">
            Mostrando {chunks.length} chunk{chunks.length !== 1 ? 's' : ''}
          </span>
        </div>
      )}
    </main>
  )
}
