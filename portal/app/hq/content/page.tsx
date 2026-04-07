'use client'

/**
 * Content Dashboard — Calendar + Brief Form + Production Queue.
 * CONTENT-1.9 — AC1-AC8
 *
 * Features:
 * - Weekly calendar with pieces grouped by date and status
 * - Brief creation form (theme, mood, style, target_date)
 * - Production queue with pipeline progress visualization
 * - Piece detail panel on click (pipeline_log timeline)
 * - Badge linking to /content/queue when pieces pending_approval
 */

import React, { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import {
  ChevronLeft,
  ChevronRight,
  Clock,
  Loader2,
  CheckCircle,
  AlertCircle,
  Sparkles,
  X,
  Play,
  Image as ImageIcon,
  Mic,
  Layers,
  CheckCheck,
  Upload,
  Eye,
} from 'lucide-react'

// ── Types ────────────────────────────────────────────────────

type ContentStatus =
  | 'briefed'
  | 'image_generating'
  | 'image_done'
  | 'image_failed'
  | 'video_generating'
  | 'video_done'
  | 'video_failed'
  | 'assembly_pending'
  | 'assembly_done'
  | 'pending_approval'
  | 'approved'
  | 'published'
  | 'rejected'

interface ContentPiece {
  id: string
  status: ContentStatus
  image_url: string | null
  video_url: string | null
  caption: string | null
  scheduled_at: string | null
  created_at: string
  theme?: string | null
  mood?: string | null
  pipeline_log?: PipelineEntry[]
}

interface PipelineEntry {
  status: string
  ts: string
  note?: string
}

interface Brief {
  theme: string
  mood: string
  style: string
  target_date: string
}

// ── Constants ────────────────────────────────────────────────

const STATUS_CONFIG: Record<string, { color: string; label: string; icon: React.ElementType }> = {
  briefed:           { color: '#6b7280', label: 'Briefado',      icon: Layers },
  image_generating:  { color: '#3b82f6', label: 'Gerando imagem', icon: ImageIcon },
  image_done:        { color: '#60a5fa', label: 'Imagem pronta', icon: ImageIcon },
  image_failed:      { color: '#ef4444', label: 'Falha imagem',  icon: AlertCircle },
  video_generating:  { color: '#a855f7', label: 'Gerando vídeo', icon: Play },
  video_done:        { color: '#c084fc', label: 'Vídeo pronto',  icon: Play },
  video_failed:      { color: '#ef4444', label: 'Falha vídeo',   icon: AlertCircle },
  assembly_pending:  { color: '#f97316', label: 'Montagem',      icon: Layers },
  assembly_done:     { color: '#fb923c', label: 'Montado',       icon: Layers },
  pending_approval:  { color: '#eab308', label: 'Aguardando ok', icon: Clock },
  approved:          { color: '#22c55e', label: 'Aprovado',      icon: CheckCircle },
  published:         { color: '#4ade80', label: 'Publicado',     icon: Upload },
  rejected:          { color: '#ef4444', label: 'Rejeitado',     icon: X },
}

const IN_PRODUCTION_STATUSES: ContentStatus[] = [
  'briefed',
  'image_generating',
  'image_done',
  'video_generating',
  'video_done',
  'assembly_pending',
  'assembly_done',
]

const MOOD_OPTIONS = [
  { value: 'inspirador', label: 'Inspirador' },
  { value: 'educativo',  label: 'Educativo' },
  { value: 'alegre',     label: 'Alegre' },
  { value: 'reflexivo',  label: 'Reflexivo' },
  { value: 'emocional',  label: 'Emocional' },
]

const STYLE_OPTIONS = [
  { value: 'cinematic',          label: 'Cinematic' },
  { value: 'influencer_natural', label: 'Influencer Natural' },
]

// ── Helpers ───────────────────────────────────────────────────

function formatDate(d: Date) {
  return d.toISOString().split('T')[0]
}

function getWeekDays(anchorDate: Date): Date[] {
  const day = anchorDate.getDay() // 0=sun
  const monday = new Date(anchorDate)
  monday.setDate(anchorDate.getDate() - ((day + 6) % 7))
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(monday)
    d.setDate(monday.getDate() + i)
    return d
  })
}

function dayLabel(d: Date) {
  return d.toLocaleDateString('pt-BR', { weekday: 'short', day: '2-digit', month: '2-digit' })
}

function pieceDate(p: ContentPiece) {
  return (p.scheduled_at ?? p.created_at).split('T')[0]
}

// ── Status chip ───────────────────────────────────────────────

function StatusChip({ status, count }: { status: string; count: number }) {
  const cfg = STATUS_CONFIG[status] ?? { color: '#6b7280', label: status }
  return (
    <span
      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium"
      style={{ background: `${cfg.color}25`, color: cfg.color, border: `1px solid ${cfg.color}40` }}
    >
      {count} {cfg.label}
    </span>
  )
}

// ── Weekly Calendar ───────────────────────────────────────────

function WeeklyCalendar({
  pieces,
  weekDays,
  onPieceClick,
}: {
  pieces: ContentPiece[]
  weekDays: Date[]
  onPieceClick: (piece: ContentPiece) => void
}) {
  return (
    <div className="grid grid-cols-7 gap-1 min-h-[140px]">
      {weekDays.map((day) => {
        const key = formatDate(day)
        const dayPieces = pieces.filter((p) => pieceDate(p) === key)

        // Group by status
        const byStatus: Record<string, number> = {}
        dayPieces.forEach((p) => {
          byStatus[p.status] = (byStatus[p.status] ?? 0) + 1
        })

        const isToday = key === formatDate(new Date())

        return (
          <div
            key={key}
            className={`flex flex-col gap-1 p-2 rounded-xl border ${
              isToday
                ? 'border-purple-500/40 bg-purple-500/5'
                : 'border-white/[0.06] bg-white/[0.02]'
            } min-h-[120px]`}
          >
            <p className={`text-[10px] font-medium mb-1 ${isToday ? 'text-purple-300' : 'text-white/40'}`}>
              {dayLabel(day)}
            </p>

            {dayPieces.length === 0 ? (
              <p className="text-[10px] text-white/20 italic">—</p>
            ) : (
              <>
                {Object.entries(byStatus).map(([st, cnt]) => (
                  <StatusChip key={st} status={st} count={cnt} />
                ))}
                {dayPieces.slice(0, 2).map((p) => (
                  <button
                    key={p.id}
                    onClick={() => onPieceClick(p)}
                    className="text-left mt-1 text-[10px] text-white/40 hover:text-white/70 truncate transition-colors"
                  >
                    {p.theme ?? p.caption?.slice(0, 30) ?? `#${p.id.slice(0, 6)}`}
                  </button>
                ))}
                {dayPieces.length > 2 && (
                  <p className="text-[10px] text-white/20">+{dayPieces.length - 2} mais</p>
                )}
              </>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ── Brief Form ────────────────────────────────────────────────

function BriefForm({
  onSubmit,
  pipelineFull,
}: {
  onSubmit: (brief: Brief) => Promise<void>
  pipelineFull: boolean
}) {
  const [theme, setTheme] = useState('')
  const [mood, setMood] = useState('inspirador')
  const [style, setStyle] = useState('cinematic')
  const [targetDate, setTargetDate] = useState(formatDate(new Date()))
  const [submitting, setSubmitting] = useState(false)
  const [success, setSuccess] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!theme.trim() || pipelineFull) return
    setSubmitting(true)
    try {
      await onSubmit({ theme: theme.trim(), mood, style, target_date: targetDate })
      setTheme('')
      setSuccess(true)
      setTimeout(() => setSuccess(false), 2500)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="bg-white/[0.03] border border-white/[0.08] rounded-2xl p-4">
      <div className="flex items-center gap-2 mb-4">
        <Sparkles size={16} className="text-purple-400" />
        <h3 className="text-sm font-semibold text-white/80">Criar Brief</h3>
      </div>

      {/* AC6: Pipeline full warning */}
      {pipelineFull && (
        <div className="flex items-center gap-2 p-3 bg-orange-500/10 border border-orange-500/25 rounded-xl mb-4 text-xs text-orange-300">
          <AlertCircle size={13} />
          Pipeline cheio — aguarde uma peça concluir antes de criar nova
        </div>
      )}

      {success && (
        <div className="flex items-center gap-2 p-3 bg-green-500/10 border border-green-500/25 rounded-xl mb-4 text-xs text-green-300">
          <CheckCircle size={13} />
          Brief criado! A Zenya vai começar em breve.
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <div>
          <label className="text-xs text-white/40 mb-1.5 block">Tema *</label>
          <input
            type="text"
            value={theme}
            onChange={(e) => setTheme(e.target.value)}
            placeholder="Ex: Receita de bolo de chocolate..."
            disabled={pipelineFull}
            className="w-full bg-white/5 border border-white/10 text-white text-sm rounded-xl px-3 py-2.5 focus:outline-none focus:ring-1 focus:ring-purple-500 placeholder-white/25 disabled:opacity-50"
          />
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-xs text-white/40 mb-1.5 block">Mood</label>
            <select
              value={mood}
              onChange={(e) => setMood(e.target.value)}
              disabled={pipelineFull}
              className="w-full bg-white/5 border border-white/10 text-white text-sm rounded-xl px-3 py-2.5 focus:outline-none focus:ring-1 focus:ring-purple-500 disabled:opacity-50"
            >
              {MOOD_OPTIONS.map((o) => (
                <option key={o.value} value={o.value} className="bg-[#0f0f1a]">{o.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-xs text-white/40 mb-1.5 block">Estilo</label>
            <select
              value={style}
              onChange={(e) => setStyle(e.target.value)}
              disabled={pipelineFull}
              className="w-full bg-white/5 border border-white/10 text-white text-sm rounded-xl px-3 py-2.5 focus:outline-none focus:ring-1 focus:ring-purple-500 disabled:opacity-50"
            >
              {STYLE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value} className="bg-[#0f0f1a]">{o.label}</option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className="text-xs text-white/40 mb-1.5 block">Data alvo</label>
          <input
            type="date"
            value={targetDate}
            onChange={(e) => setTargetDate(e.target.value)}
            disabled={pipelineFull}
            className="w-full bg-white/5 border border-white/10 text-white text-sm rounded-xl px-3 py-2.5 focus:outline-none focus:ring-1 focus:ring-purple-500 disabled:opacity-50"
          />
        </div>

        <button
          type="submit"
          disabled={!theme.trim() || pipelineFull || submitting}
          className="flex items-center justify-center gap-2 py-2.5 bg-purple-600 hover:bg-purple-500 text-white text-sm font-semibold rounded-xl transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {submitting ? (
            <Loader2 size={15} className="animate-spin" />
          ) : (
            <Sparkles size={15} />
          )}
          Criar Brief
        </button>
      </form>
    </div>
  )
}

// ── Production Queue ──────────────────────────────────────────

function ProductionQueue({ pieces }: { pieces: ContentPiece[] }) {
  const PIPELINE_STEPS: ContentStatus[] = [
    'briefed',
    'image_generating',
    'image_done',
    'video_generating',
    'video_done',
    'assembly_pending',
    'assembly_done',
  ]

  function stepIndex(status: ContentStatus) {
    const i = PIPELINE_STEPS.indexOf(status)
    return i === -1 ? 0 : i
  }

  return (
    <div className="bg-white/[0.03] border border-white/[0.08] rounded-2xl p-4">
      <div className="flex items-center gap-2 mb-4">
        <Layers size={16} className="text-orange-400" />
        <h3 className="text-sm font-semibold text-white/80">Em produção</h3>
        <span className="text-xs text-white/30 font-mono ml-auto">{pieces.length}/5</span>
      </div>

      {pieces.length === 0 ? (
        <p className="text-xs text-white/30 italic text-center py-4">
          Nenhuma peça em produção agora.
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          {pieces.map((p) => {
            const cfg = STATUS_CONFIG[p.status] ?? STATUS_CONFIG.briefed
            const Icon = cfg.icon
            const step = stepIndex(p.status as ContentStatus)
            const pct = Math.round((step / (PIPELINE_STEPS.length - 1)) * 100)

            return (
              <div key={p.id} className="bg-white/[0.03] rounded-xl p-3 border border-white/[0.06]">
                <div className="flex items-center gap-2 mb-2">
                  <Icon size={13} style={{ color: cfg.color }} />
                  <p className="text-xs text-white/70 flex-1 truncate">
                    {p.theme ?? p.caption?.slice(0, 40) ?? `Peça ${p.id.slice(0, 6)}`}
                  </p>
                  <span className="text-[10px] font-medium" style={{ color: cfg.color }}>
                    {cfg.label}
                  </span>
                </div>
                {/* Progress bar */}
                <div className="w-full h-1 bg-white/10 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{ width: `${pct}%`, background: cfg.color }}
                  />
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ── Piece Detail Panel ────────────────────────────────────────

function PieceDetailPanel({
  piece,
  onClose,
}: {
  piece: ContentPiece
  onClose: () => void
}) {
  const cfg = STATUS_CONFIG[piece.status] ?? { color: '#6b7280', label: piece.status }

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="bg-[#0f0f1a] border border-white/10 rounded-2xl w-full max-w-lg max-h-[80vh] overflow-y-auto shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-white/[0.08]">
          <div>
            <p className="text-sm font-semibold text-white/80">
              {piece.theme ?? `Peça ${piece.id.slice(0, 8)}`}
            </p>
            <span
              className="text-[11px] font-medium"
              style={{ color: cfg.color }}
            >
              {cfg.label}
            </span>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-white/40 hover:text-white/70 rounded-lg hover:bg-white/10 transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Assets */}
        <div className="p-4 border-b border-white/[0.08]">
          <p className="text-xs text-white/30 mb-3 uppercase tracking-wider">Assets</p>
          <div className="flex flex-wrap gap-2">
            {piece.image_url && (
              <a
                href={piece.image_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-500/10 text-blue-400 rounded-lg text-xs border border-blue-500/25 hover:bg-blue-500/20 transition-colors"
              >
                <ImageIcon size={12} /> Imagem
              </a>
            )}
            {piece.video_url && (
              <a
                href={piece.video_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 px-3 py-1.5 bg-purple-500/10 text-purple-400 rounded-lg text-xs border border-purple-500/25 hover:bg-purple-500/20 transition-colors"
              >
                <Play size={12} /> Vídeo
              </a>
            )}
            {!piece.image_url && !piece.video_url && (
              <span className="text-xs text-white/30 italic">Nenhum asset gerado ainda</span>
            )}
          </div>
        </div>

        {/* Caption */}
        {piece.caption && (
          <div className="p-4 border-b border-white/[0.08]">
            <p className="text-xs text-white/30 mb-2 uppercase tracking-wider">Caption</p>
            <p className="text-xs text-white/60 leading-relaxed whitespace-pre-wrap">{piece.caption}</p>
          </div>
        )}

        {/* Pipeline log timeline */}
        {piece.pipeline_log && piece.pipeline_log.length > 0 && (
          <div className="p-4">
            <p className="text-xs text-white/30 mb-3 uppercase tracking-wider">Timeline</p>
            <div className="flex flex-col gap-2">
              {piece.pipeline_log.map((entry, i) => {
                const entryCfg = STATUS_CONFIG[entry.status] ?? { color: '#6b7280', label: entry.status }
                return (
                  <div key={i} className="flex items-start gap-2.5">
                    <div
                      className="w-2 h-2 rounded-full mt-1 flex-shrink-0"
                      style={{ background: entryCfg.color }}
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-white/60" style={{ color: entryCfg.color }}>
                        {entryCfg.label}
                      </p>
                      {entry.note && (
                        <p className="text-[11px] text-white/35 mt-0.5">{entry.note}</p>
                      )}
                      <p className="text-[10px] text-white/25 font-mono mt-0.5">
                        {new Date(entry.ts).toLocaleString('pt-BR')}
                      </p>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────

export default function ContentDashboard() {
  const [pieces, setPieces] = useState<ContentPiece[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [weekAnchor, setWeekAnchor] = useState(new Date())
  const [selectedPiece, setSelectedPiece] = useState<ContentPiece | null>(null)
  const [submittingBrief, setSubmittingBrief] = useState(false)

  const weekDays = getWeekDays(weekAnchor)

  const loadPieces = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/hq/content/pieces')
      if (!res.ok) throw new Error(`Erro ${res.status}`)
      const data = await res.json()
      const list: ContentPiece[] = Array.isArray(data) ? data : (data.pieces ?? data.items ?? [])
      setPieces(list)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao carregar peças')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadPieces()
  }, [loadPieces])

  const pendingCount = pieces.filter((p) => p.status === 'pending_approval').length
  const inProduction = pieces.filter((p) => IN_PRODUCTION_STATUSES.includes(p.status as ContentStatus))
  const pipelineFull = inProduction.length >= 5

  const handleCreateBrief = async (brief: Brief) => {
    setSubmittingBrief(true)
    try {
      const res = await fetch('/api/hq/content/briefs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(brief),
      })
      if (!res.ok) throw new Error(`Erro ${res.status}`)
      const newPiece = await res.json()
      setPieces((prev) => [...prev, newPiece])
    } finally {
      setSubmittingBrief(false)
    }
  }

  const handleWeekPrev = () => {
    const d = new Date(weekAnchor)
    d.setDate(d.getDate() - 7)
    setWeekAnchor(d)
  }

  const handleWeekNext = () => {
    const d = new Date(weekAnchor)
    d.setDate(d.getDate() + 7)
    setWeekAnchor(d)
  }

  return (
    <div className="flex flex-col gap-5 pb-8">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-3">
          <Sparkles size={20} className="text-purple-400" strokeWidth={1.75} />
          <div>
            <h1 className="text-[0.9375rem] font-semibold text-white/80 leading-tight">
              Produção de Conteúdo
            </h1>
            <p className="text-xs text-white/35 mt-0.5">
              {loading ? '...' : `${pieces.length} peças no sistema`}
            </p>
          </div>
        </div>

        {/* AC8: Badge → /content/queue */}
        {pendingCount > 0 && (
          <Link
            href="/hq/content/queue"
            className="flex items-center gap-2 px-3 py-1.5 bg-yellow-500/15 hover:bg-yellow-500/25 text-yellow-400 text-xs font-semibold rounded-xl transition-colors border border-yellow-500/30"
          >
            <Eye size={13} />
            {pendingCount} aguardando aprovação
          </Link>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/25 rounded-xl text-sm text-red-400">
          <AlertCircle size={14} />
          {error}
          <button onClick={loadPieces} className="ml-auto text-xs underline">
            Tentar novamente
          </button>
        </div>
      )}

      {/* AC1, AC2: Weekly Calendar */}
      <div className="bg-white/[0.03] border border-white/[0.08] rounded-2xl p-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Clock size={15} className="text-white/40" />
            <h2 className="text-sm font-semibold text-white/70">Calendário Semanal</h2>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={handleWeekPrev}
              className="p-1.5 text-white/40 hover:text-white/70 rounded-lg hover:bg-white/10 transition-colors"
              aria-label="Semana anterior"
            >
              <ChevronLeft size={16} />
            </button>
            <span className="text-xs text-white/40 px-2 font-mono">
              {weekDays[0].toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })}
              {' – '}
              {weekDays[6].toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })}
            </span>
            <button
              onClick={handleWeekNext}
              className="p-1.5 text-white/40 hover:text-white/70 rounded-lg hover:bg-white/10 transition-colors"
              aria-label="Próxima semana"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>

        {loading ? (
          <div className="grid grid-cols-7 gap-1">
            {Array.from({ length: 7 }).map((_, i) => (
              <div key={i} className="h-28 rounded-xl bg-white/5 animate-pulse" />
            ))}
          </div>
        ) : (
          <WeeklyCalendar
            pieces={pieces}
            weekDays={weekDays}
            onPieceClick={setSelectedPiece}
          />
        )}
      </div>

      {/* AC3-AC6: Brief Form + Production Queue */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <BriefForm onSubmit={handleCreateBrief} pipelineFull={pipelineFull} />
        <ProductionQueue pieces={inProduction} />
      </div>

      {/* AC7: Piece detail panel */}
      {selectedPiece && (
        <PieceDetailPanel
          piece={selectedPiece}
          onClose={() => setSelectedPiece(null)}
        />
      )}
    </div>
  )
}
