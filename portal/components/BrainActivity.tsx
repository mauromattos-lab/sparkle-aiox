'use client'

import { useState, useEffect, useCallback } from 'react'

// ── Types ──────────────────────────────────────────────────

interface ProcessingItem {
  id: string
  title: string
  source_ref: string
  source_type: string
  status: string
  created_at: string
  updated_at: string
}

interface RecentIngestion {
  id: string
  title: string
  source_ref: string
  source_type: string
  chunks_inserted: number
  insights_extracted: number
  completed_at: string
  created_at: string
}

interface Insight {
  id: string
  domain: string
  insight_type: string
  content: string
  created_at: string
}

interface Synthesis {
  id: string
  domain: string
  version: number
  source_count: number
  synthesis_preview: string
  created_at: string
  updated_at: string
}

interface BrainActivityData {
  processing: ProcessingItem[]
  recent: RecentIngestion[]
  insights: {
    total: number
    recent: Insight[]
    by_domain: Record<string, number>
  }
  syntheses: Synthesis[]
  stats: {
    chunks_total: number
    insights_total: number
    domains_with_synthesis: number
  }
}

// ── Runtime URL ────────────────────────────────────────────

const RUNTIME_URL = process.env.NEXT_PUBLIC_RUNTIME_URL || 'https://runtime.sparkleai.tech'

// ── Icons ──────────────────────────────────────────────────

function IconBrain() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9.5 2a3.5 3.5 0 0 0-3.2 4.8A3.5 3.5 0 0 0 4 10a3.49 3.49 0 0 0 1.65 2.97A3.5 3.5 0 0 0 7 17.5a3.5 3.5 0 0 0 2.5 1V22h5v-3.5a3.5 3.5 0 0 0 2.5-1 3.5 3.5 0 0 0 1.35-4.53A3.49 3.49 0 0 0 20 10a3.5 3.5 0 0 0-2.3-3.2A3.5 3.5 0 0 0 14.5 2" />
      <path d="M12 2v20" />
    </svg>
  )
}

function IconLoader() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      className="animate-spin">
      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
    </svg>
  )
}

function IconCheck() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  )
}

function IconLightbulb() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5" />
      <path d="M9 18h6" />
      <path d="M10 22h4" />
    </svg>
  )
}

function IconDatabase() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <ellipse cx="12" cy="5" rx="9" ry="3" />
      <path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5" />
      <path d="M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3" />
    </svg>
  )
}

// ── Helpers ─────────────────────────────────────────────────

function timeAgo(isoDate: string): string {
  if (!isoDate) return ''
  const diff = Date.now() - new Date(isoDate).getTime()
  const seconds = Math.floor(diff / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}min`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h`
  const days = Math.floor(hours / 24)
  return `${days}d`
}

function sourceLabel(sourceType: string): string {
  const labels: Record<string, string> = {
    youtube: 'YT',
    pdf_text: 'PDF',
    url: 'URL',
    transcript: 'TRS',
    conversation: 'CONV',
    document: 'DOC',
  }
  return labels[sourceType] || sourceType.toUpperCase().slice(0, 4)
}

// ── Sub-Components ─────────────────────────────────────────

function ProcessingQueue({ items }: { items: ProcessingItem[] }) {
  return (
    <div>
      <div className="flex items-center gap-1.5 mb-2">
        <span className="text-[#0ea5e9]"><IconLoader /></span>
        <h3 className="text-[10px] text-white/30 font-mono uppercase tracking-widest">
          Processing Queue
        </h3>
        {items.length > 0 && (
          <span className="ml-auto text-[10px] font-mono text-[#0ea5e9]">
            {items.length} ativo{items.length !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {items.length === 0 ? (
        <div className="rounded-lg border border-white/[0.04] bg-white/[0.01] px-3 py-4 text-center">
          <p className="text-xs text-white/25 font-mono">
            Brain ocioso -- pronto para receber conteudo
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-1.5">
          {items.map(item => (
            <div
              key={item.id}
              className="rounded-lg border border-[#0ea5e9]/20 bg-[#0ea5e9]/[0.03] px-3 py-2 flex items-center gap-3"
            >
              <span className="h-2 w-2 rounded-full bg-[#0ea5e9] animate-pulse flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-xs text-white/70 font-mono truncate">
                  {item.title || item.source_ref || 'Processando...'}
                </p>
                <p className="text-[10px] text-white/30 font-mono">
                  {sourceLabel(item.source_type)} -- {item.status}
                </p>
              </div>
              <span className="text-[10px] text-white/20 font-mono flex-shrink-0">
                {timeAgo(item.created_at)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function RecentIngestions({ items }: { items: RecentIngestion[] }) {
  if (items.length === 0) return null

  return (
    <div>
      <div className="flex items-center gap-1.5 mb-2">
        <span className="text-[#00ff87]"><IconCheck /></span>
        <h3 className="text-[10px] text-white/30 font-mono uppercase tracking-widest">
          Recent Ingestions
        </h3>
      </div>

      <div className="rounded-lg border border-white/[0.04] bg-white/[0.01] overflow-hidden">
        {items.map((item, idx) => (
          <div
            key={item.id}
            className={[
              'flex items-center gap-3 px-3 py-2',
              idx < items.length - 1 ? 'border-b border-white/[0.03]' : '',
            ].join(' ')}
          >
            <span className="text-[10px] font-mono text-white/20 w-8 text-center flex-shrink-0">
              {sourceLabel(item.source_type)}
            </span>
            <div className="flex-1 min-w-0">
              <p className="text-xs text-white/60 font-mono truncate">
                {item.title || item.source_ref || '---'}
              </p>
            </div>
            <div className="flex items-center gap-3 flex-shrink-0">
              <span className="text-[10px] text-white/30 font-mono">
                {item.chunks_inserted}ch
              </span>
              <span className="text-[10px] text-[#eab308]/60 font-mono">
                {item.insights_extracted}ins
              </span>
              <span className="text-[10px] text-white/15 font-mono">
                {timeAgo(item.completed_at || item.created_at)}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function BrainKnowledge({ syntheses, insights }: { syntheses: Synthesis[]; insights: BrainActivityData['insights'] }) {
  return (
    <div>
      <div className="flex items-center gap-1.5 mb-2">
        <span className="text-[#eab308]"><IconLightbulb /></span>
        <h3 className="text-[10px] text-white/30 font-mono uppercase tracking-widest">
          Brain Knowledge
        </h3>
      </div>

      {syntheses.length === 0 ? (
        <div className="rounded-lg border border-white/[0.04] bg-white/[0.01] px-3 py-4 text-center">
          <p className="text-xs text-white/25 font-mono">
            Nenhuma sintese ainda -- alimente 5+ conteudos do mesmo tema
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {syntheses.map(syn => (
            <div
              key={syn.id}
              className="rounded-lg border border-[#eab308]/15 bg-[#eab308]/[0.02] px-3 py-2.5"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-mono font-semibold text-white/80">
                  {syn.domain}
                </span>
                <span className="text-[10px] text-white/20 font-mono">
                  v{syn.version}
                </span>
              </div>
              <div className="flex items-center gap-2 text-[10px] text-white/30 font-mono">
                <span>{syn.source_count} sources</span>
                <span className="text-white/10">|</span>
                <span>{insights.by_domain[syn.domain] || 0} insights</span>
              </div>
              <p className="text-[10px] text-white/20 mt-1.5 line-clamp-2">
                {syn.synthesis_preview || '---'}
              </p>
              <span className="text-[10px] text-white/10 font-mono mt-1 block">
                {timeAgo(syn.updated_at || syn.created_at)}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Recent insights list */}
      {insights.recent.length > 0 && (
        <div className="mt-3">
          <p className="text-[10px] text-white/20 font-mono uppercase tracking-widest mb-1.5">
            Latest Insights
          </p>
          <div className="rounded-lg border border-white/[0.04] bg-white/[0.01] overflow-hidden">
            {insights.recent.slice(0, 5).map((ins, idx) => (
              <div
                key={ins.id}
                className={[
                  'px-3 py-1.5 flex items-start gap-2',
                  idx < Math.min(insights.recent.length, 5) - 1 ? 'border-b border-white/[0.03]' : '',
                ].join(' ')}
              >
                <span className="text-[10px] text-[#eab308]/50 font-mono flex-shrink-0 mt-0.5 w-14">
                  {ins.domain}
                </span>
                <p className="text-[10px] text-white/40 flex-1 line-clamp-1">
                  {ins.content}
                </p>
                <span className="text-[10px] text-white/15 font-mono flex-shrink-0">
                  {timeAgo(ins.created_at)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function StatsBar({ stats }: { stats: BrainActivityData['stats'] }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-white/[0.04] bg-white/[0.01] px-4 py-2">
      <div className="flex items-center gap-1.5">
        <span className="text-white/25"><IconDatabase /></span>
        <span className="text-[10px] text-white/30 font-mono uppercase tracking-widest">
          Stats
        </span>
      </div>
      <div className="flex items-center gap-4 text-[10px] font-mono">
        <span className="text-white/40">
          <span className="text-white/60">{stats.chunks_total.toLocaleString()}</span> chunks
        </span>
        <span className="text-white/10">|</span>
        <span className="text-white/40">
          <span className="text-[#eab308]/70">{stats.insights_total.toLocaleString()}</span> insights
        </span>
        <span className="text-white/10">|</span>
        <span className="text-white/40">
          <span className="text-[#00ff87]/60">{stats.domains_with_synthesis}</span> dominios sintetizados
        </span>
      </div>
    </div>
  )
}

// ── Main Component ──────────────────────────────────────────

export default function BrainActivity() {
  const [data, setData] = useState<BrainActivityData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchActivity = useCallback(async () => {
    try {
      const resp = await fetch(`${RUNTIME_URL}/brain/activity`)
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const json = await resp.json()
      if (json.status === 'error') {
        setError(json.error)
        return
      }
      setData(json)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao conectar')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchActivity()
    const interval = setInterval(fetchActivity, 10_000)
    return () => clearInterval(interval)
  }, [fetchActivity])

  return (
    <div className="flex flex-col gap-3">
      {/* Section header */}
      <div className="flex items-center gap-2">
        <span className="text-[#eab308]"><IconBrain /></span>
        <h2 className="text-[10px] text-white/30 font-mono uppercase tracking-widest">
          Brain Activity
        </h2>
        {data && data.processing.length > 0 && (
          <span className="h-1.5 w-1.5 rounded-full bg-[#0ea5e9] animate-pulse" />
        )}
        {loading && !data && (
          <span className="text-[10px] text-white/20 font-mono animate-pulse ml-auto">
            Carregando...
          </span>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="rounded border border-[#ef4444]/30 bg-[#ef4444]/5 px-3 py-2 text-xs text-[#ef4444]/80 font-mono">
          Brain: {error}
        </div>
      )}

      {/* Content */}
      {data && (
        <>
          <ProcessingQueue items={data.processing} />
          <RecentIngestions items={data.recent} />
          <BrainKnowledge syntheses={data.syntheses} insights={data.insights} />
          <StatsBar stats={data.stats} />
        </>
      )}
    </div>
  )
}
