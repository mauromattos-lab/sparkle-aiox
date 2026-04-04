'use client'

import { useState, useEffect, useCallback } from 'react'

// ── Types ──────────────────────────────────────────────────

interface ContentItem {
  id: string
  client_id: string | null
  persona: string | null
  format: string | null
  topic: string | null
  content: string
  hashtags: string[] | string | null
  status: string
  source_type: string | null
  created_at: string
}

// ── Runtime URL ────────────────────────────────────────────

const RUNTIME_URL = process.env.NEXT_PUBLIC_RUNTIME_URL || 'https://runtime.sparkleai.tech'

// ── Icons ──────────────────────────────────────────────────

function IconContent() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <line x1="10" y1="9" x2="8" y2="9" />
    </svg>
  )
}

function IconCopy() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect width="14" height="14" x="8" y="8" rx="2" ry="2" />
      <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
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

function IconX() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  )
}

function IconChevron({ open }: { open: boolean }) {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      className={`transition-transform duration-200 ${open ? 'rotate-90' : ''}`}>
      <polyline points="9 18 15 12 9 6" />
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

function statusColor(status: string): string {
  switch (status) {
    case 'approved':  return 'bg-[#00ff87]/20 text-[#00ff87]'
    case 'published': return 'bg-[#0ea5e9]/20 text-[#0ea5e9]'
    case 'rejected':  return 'bg-[#ef4444]/20 text-[#ef4444]'
    case 'draft':
    default:          return 'bg-white/10 text-white/50'
  }
}

function formatBadgeColor(format: string | null): string {
  switch (format) {
    case 'carrossel': return 'bg-purple-500/20 text-purple-400'
    case 'reels':     return 'bg-pink-500/20 text-pink-400'
    case 'stories':   return 'bg-orange-500/20 text-orange-400'
    case 'post':      return 'bg-[#0ea5e9]/20 text-[#0ea5e9]'
    case 'caption':   return 'bg-[#eab308]/20 text-[#eab308]'
    default:          return 'bg-white/10 text-white/40'
  }
}

function parseHashtags(hashtags: string[] | string | null): string[] {
  if (!hashtags) return []
  if (Array.isArray(hashtags)) return hashtags
  try {
    const parsed = JSON.parse(hashtags)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return hashtags.split(/[\s,]+/).filter(Boolean)
  }
}

// ── Content Card ────────────────────────────────────────────

function ContentCard({
  item,
  onApprove,
  onReject,
}: {
  item: ContentItem
  onApprove: (id: string) => void
  onReject: (id: string) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const [copied, setCopied] = useState(false)

  const preview = item.content?.length > 150
    ? item.content.slice(0, 150) + '...'
    : item.content || ''

  const hashtags = parseHashtags(item.hashtags)

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await navigator.clipboard.writeText(item.content || '')
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // clipboard not available
    }
  }

  return (
    <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] overflow-hidden transition-all duration-200">
      {/* Header row — clickable to expand */}
      <div
        className="flex items-start gap-2 px-3 py-2.5 cursor-pointer hover:bg-white/[0.02] transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="text-white/20 mt-0.5 flex-shrink-0">
          <IconChevron open={expanded} />
        </span>

        <div className="flex-1 min-w-0">
          {/* Badges row */}
          <div className="flex items-center gap-1.5 mb-1 flex-wrap">
            {item.persona && (
              <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-[#eab308]/20 text-[#eab308] uppercase">
                {item.persona}
              </span>
            )}
            {item.format && (
              <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded uppercase ${formatBadgeColor(item.format)}`}>
                {item.format}
              </span>
            )}
            <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded ${statusColor(item.status)}`}>
              {item.status}
            </span>
          </div>

          {/* Topic */}
          {item.topic && (
            <p className="text-xs text-white/60 font-mono truncate mb-0.5">
              {item.topic}
            </p>
          )}

          {/* Preview */}
          <p className="text-[11px] text-white/35 line-clamp-2">
            {preview}
          </p>
        </div>

        <span className="text-[10px] text-white/15 font-mono flex-shrink-0 mt-1">
          {timeAgo(item.created_at)}
        </span>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div className="border-t border-white/[0.04] px-3 py-3">
          {/* Full content */}
          <div className="rounded bg-white/[0.03] px-3 py-2 mb-2">
            <pre className="text-xs text-white/60 whitespace-pre-wrap font-mono leading-relaxed">
              {item.content}
            </pre>
          </div>

          {/* Hashtags */}
          {hashtags.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-2">
              {hashtags.map((tag, i) => (
                <span key={i} className="text-[10px] font-mono text-[#0ea5e9]/60">
                  {tag.startsWith('#') ? tag : `#${tag}`}
                </span>
              ))}
            </div>
          )}

          {/* Action buttons */}
          <div className="flex items-center gap-2 pt-1">
            {item.status === 'draft' && (
              <>
                <button
                  onClick={(e) => { e.stopPropagation(); onApprove(item.id) }}
                  className="flex items-center gap-1 text-[10px] font-mono px-2 py-1 rounded
                    bg-[#00ff87]/10 text-[#00ff87]/80 hover:bg-[#00ff87]/20 transition-colors"
                >
                  <IconCheck /> Approve
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); onReject(item.id) }}
                  className="flex items-center gap-1 text-[10px] font-mono px-2 py-1 rounded
                    bg-[#ef4444]/10 text-[#ef4444]/80 hover:bg-[#ef4444]/20 transition-colors"
                >
                  <IconX /> Reject
                </button>
              </>
            )}
            <button
              onClick={handleCopy}
              className="flex items-center gap-1 text-[10px] font-mono px-2 py-1 rounded
                bg-white/5 text-white/40 hover:bg-white/10 hover:text-white/60 transition-colors ml-auto"
            >
              {copied ? (
                <><IconCheck /> Copiado</>
              ) : (
                <><IconCopy /> Copiar</>
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Main Component ──────────────────────────────────────────

export default function ContentManager() {
  const [items, setItems] = useState<ContentItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<string>('all')

  const fetchContent = useCallback(async () => {
    try {
      const params = new URLSearchParams({ limit: '20' })
      if (filter !== 'all') params.set('status', filter)

      const resp = await fetch(`${RUNTIME_URL}/content/list?${params}`)
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const json = await resp.json()
      setItems(json.items || [])
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao conectar')
    } finally {
      setLoading(false)
    }
  }, [filter])

  useEffect(() => {
    fetchContent()
    const interval = setInterval(fetchContent, 15_000)
    return () => clearInterval(interval)
  }, [fetchContent])

  const handleApprove = async (id: string) => {
    try {
      const resp = await fetch(`${RUNTIME_URL}/content/${id}/approve`, { method: 'POST' })
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      setItems(prev => prev.map(it => it.id === id ? { ...it, status: 'approved' } : it))
    } catch {
      // silently fail — next poll will refresh
    }
  }

  const handleReject = async (id: string) => {
    try {
      const resp = await fetch(`${RUNTIME_URL}/content/${id}/reject`, { method: 'POST' })
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      setItems(prev => prev.map(it => it.id === id ? { ...it, status: 'rejected' } : it))
    } catch {
      // silently fail — next poll will refresh
    }
  }

  const filterOptions = ['all', 'draft', 'approved', 'published', 'rejected'] as const

  return (
    <div className="flex flex-col gap-3">
      {/* Section header */}
      <div className="flex items-center gap-2">
        <span className="text-purple-400"><IconContent /></span>
        <h2 className="text-[10px] text-white/30 font-mono uppercase tracking-widest">
          Content Manager
        </h2>
        {items.length > 0 && (
          <span className="text-[10px] text-white/15 font-mono ml-auto">
            {items.length} items
          </span>
        )}
      </div>

      {/* Filter tabs */}
      <div className="flex items-center gap-1">
        {filterOptions.map(opt => (
          <button
            key={opt}
            onClick={() => setFilter(opt)}
            className={[
              'text-[9px] font-mono px-2 py-1 rounded transition-colors uppercase tracking-wider',
              filter === opt
                ? 'bg-white/10 text-white/70'
                : 'bg-transparent text-white/25 hover:text-white/40',
            ].join(' ')}
          >
            {opt}
          </button>
        ))}
      </div>

      {/* Error */}
      {error && (
        <div className="rounded border border-[#ef4444]/30 bg-[#ef4444]/5 px-3 py-2 text-xs text-[#ef4444]/80 font-mono">
          Content: {error}
        </div>
      )}

      {/* Loading */}
      {loading && items.length === 0 && (
        <div className="rounded-lg border border-white/[0.04] bg-white/[0.01] px-3 py-6 text-center">
          <p className="text-xs text-white/25 font-mono animate-pulse">
            Carregando conteudos...
          </p>
        </div>
      )}

      {/* Empty state */}
      {!loading && items.length === 0 && !error && (
        <div className="rounded-lg border border-white/[0.04] bg-white/[0.01] px-3 py-6 text-center">
          <p className="text-xs text-white/25 font-mono">
            Nenhum conteudo gerado ainda
          </p>
          <p className="text-[10px] text-white/15 font-mono mt-1">
            Use Friday ou o Runtime para gerar conteudo
          </p>
        </div>
      )}

      {/* Content list */}
      {items.length > 0 && (
        <div className="flex flex-col gap-1.5">
          {items.map(item => (
            <ContentCard
              key={item.id}
              item={item}
              onApprove={handleApprove}
              onReject={handleReject}
            />
          ))}
        </div>
      )}
    </div>
  )
}
