'use client'

/**
 * Content Queue — Approval interface for pending content pieces.
 * CONTENT-1.7 — AC1-AC10
 *
 * Features:
 * - Fullscreen preview (video_url for videos, image_url for images)
 * - Inline caption editing
 * - Approve / Reject / Prev / Next navigation
 * - "Approve all" batch action
 * - Empty state + loading/error handling
 */

import React, { useState, useEffect, useCallback, useRef } from 'react'
import Link from 'next/link'
import {
  ChevronLeft,
  ChevronRight,
  Check,
  X,
  Volume2,
  VolumeX,
  Pencil,
  CheckCheck,
  Loader2,
  Film,
  Image as ImageIcon,
} from 'lucide-react'

// ── Types ────────────────────────────────────────────────────

interface ContentPiece {
  id: string
  image_url: string | null
  video_url: string | null
  caption: string | null
  voice_script: string | null
  status: string
  scheduled_at: string | null
  created_at: string
  client_id?: string | null
}

// ── Toast ────────────────────────────────────────────────────

function Toast({ message, type }: { message: string; type: 'error' | 'success' }) {
  return (
    <div
      className={`fixed bottom-4 left-1/2 -translate-x-1/2 z-50 px-4 py-2.5 rounded-lg text-sm font-medium shadow-xl
        ${type === 'error' ? 'bg-red-500/90 text-white' : 'bg-green-500/90 text-white'}`}
    >
      {message}
    </div>
  )
}

// ── Video Preview ────────────────────────────────────────────

function VideoPreview({ url }: { url: string }) {
  const [muted, setMuted] = useState(true)
  const videoRef = useRef<HTMLVideoElement>(null)

  return (
    <div className="relative w-full h-full flex items-center justify-center bg-black">
      <video
        ref={videoRef}
        src={url}
        autoPlay
        loop
        muted={muted}
        playsInline
        className="max-h-full max-w-full object-contain"
      />
      <button
        onClick={() => setMuted((m) => !m)}
        className="absolute bottom-4 right-4 bg-black/60 hover:bg-black/80 text-white rounded-full p-2.5 transition-colors"
        aria-label={muted ? 'Ativar som' : 'Silenciar'}
      >
        {muted ? <VolumeX size={18} /> : <Volume2 size={18} />}
      </button>
    </div>
  )
}

// ── Image Preview ────────────────────────────────────────────

function ImagePreview({ url }: { url: string }) {
  return (
    <div className="relative w-full h-full flex items-center justify-center bg-black">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={url}
        alt="Content preview"
        className="max-h-full max-w-full object-contain"
      />
    </div>
  )
}

// ── Caption Editor ───────────────────────────────────────────

function CaptionEditor({
  value,
  onSave,
  saving,
}: {
  value: string | null
  onSave: (caption: string) => Promise<void>
  saving: boolean
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value ?? '')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    setDraft(value ?? '')
    setEditing(false)
  }, [value])

  const handleEdit = () => {
    setEditing(true)
    setTimeout(() => textareaRef.current?.focus(), 50)
  }

  const handleSave = async () => {
    await onSave(draft)
    setEditing(false)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSave()
    }
    if (e.key === 'Escape') {
      setDraft(value ?? '')
      setEditing(false)
    }
  }

  return (
    <div className="px-4 py-3 bg-black/80 border-t border-white/10">
      {editing ? (
        <div className="flex items-start gap-2">
          <textarea
            ref={textareaRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={3}
            className="flex-1 bg-white/10 text-white text-sm rounded-lg px-3 py-2 resize-none focus:outline-none focus:ring-1 focus:ring-purple-500 placeholder-white/30"
            placeholder="Caption do conteúdo..."
          />
          <div className="flex flex-col gap-1">
            <button
              onClick={handleSave}
              disabled={saving}
              className="p-2 bg-purple-600 hover:bg-purple-500 text-white rounded-lg transition-colors disabled:opacity-60"
              aria-label="Salvar caption"
            >
              {saving ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
            </button>
            <button
              onClick={() => { setDraft(value ?? ''); setEditing(false) }}
              className="p-2 bg-white/10 hover:bg-white/20 text-white/60 rounded-lg transition-colors"
              aria-label="Cancelar edição"
            >
              <X size={14} />
            </button>
          </div>
        </div>
      ) : (
        <div className="flex items-start gap-2 group">
          <p className="flex-1 text-sm text-white/70 leading-relaxed line-clamp-3 min-h-[3rem]">
            {value || <span className="text-white/30 italic">Sem caption</span>}
          </p>
          <button
            onClick={handleEdit}
            className="p-1.5 text-white/30 hover:text-white/70 rounded-lg hover:bg-white/10 transition-colors opacity-0 group-hover:opacity-100 flex-shrink-0"
            aria-label="Editar caption"
          >
            <Pencil size={13} />
          </button>
        </div>
      )}
    </div>
  )
}

// ── Reject Modal ─────────────────────────────────────────────

function RejectModal({
  open,
  onSubmit,
  onClose,
  submitting,
}: {
  open: boolean
  onSubmit: (reason: string) => Promise<void>
  onClose: () => void
  submitting: boolean
}) {
  const [reason, setReason] = useState('')

  useEffect(() => {
    if (open) setReason('')
  }, [open])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm">
      <div className="bg-[#0f0f1a] border border-white/10 rounded-2xl p-6 w-full max-w-md mx-4 shadow-2xl">
        <h3 className="text-base font-semibold text-white mb-1">Rejeitar conteúdo</h3>
        <p className="text-xs text-white/40 mb-4">Explique o motivo para a Zenya melhorar as próximas gerações.</p>

        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Ex: A imagem ficou muito escura, o texto está cortado..."
          rows={4}
          autoFocus
          className="w-full bg-white/5 border border-white/10 text-white text-sm rounded-xl px-3 py-2.5 resize-none focus:outline-none focus:ring-1 focus:ring-red-500 placeholder-white/25"
        />

        <div className="flex gap-2 mt-4">
          <button
            onClick={onClose}
            className="flex-1 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 text-white/60 text-sm font-medium transition-colors"
          >
            Cancelar
          </button>
          <button
            onClick={() => onSubmit(reason)}
            disabled={!reason.trim() || submitting}
            className="flex-1 py-2.5 rounded-xl bg-red-600 hover:bg-red-500 text-white text-sm font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {submitting ? <Loader2 size={14} className="animate-spin" /> : <X size={14} />}
            Rejeitar
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────

export default function ContentQueuePage() {
  const [pieces, setPieces] = useState<ContentPiece[]>([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [isRejectModalOpen, setIsRejectModalOpen] = useState(false)
  const [rejectSubmitting, setRejectSubmitting] = useState(false)

  const [actionLoading, setActionLoading] = useState(false)
  const [captionSaving, setCaptionSaving] = useState(false)
  const [approveAllLoading, setApproveAllLoading] = useState(false)

  const [toast, setToast] = useState<{ message: string; type: 'error' | 'success' } | null>(null)

  const showToast = (message: string, type: 'error' | 'success' = 'success') => {
    setToast({ message, type })
    setTimeout(() => setToast(null), 3500)
  }

  // ── Load queue ────────────────────────────────────────────

  const loadQueue = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/hq/content/queue')
      if (!res.ok) throw new Error(`Erro ${res.status}`)
      const data = await res.json()
      // Runtime may return {pieces: [...]} or [...] directly
      const list: ContentPiece[] = Array.isArray(data) ? data : (data.pieces ?? data.items ?? [])
      setPieces(list)
      setCurrentIndex(0)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao carregar fila')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadQueue()
  }, [loadQueue])

  const current = pieces[currentIndex]

  // ── Approve ───────────────────────────────────────────────

  const handleApprove = useCallback(async (id: string) => {
    setActionLoading(true)
    try {
      const res = await fetch(`/api/hq/content/pieces/${id}/approve`, { method: 'POST' })
      if (!res.ok) throw new Error(`Erro ${res.status}`)
      setPieces((prev) => {
        const next = prev.filter((p) => p.id !== id)
        setCurrentIndex((i) => Math.min(i, Math.max(0, next.length - 1)))
        return next
      })
      showToast('Conteúdo aprovado!')
    } catch {
      showToast('Erro ao aprovar conteúdo', 'error')
    } finally {
      setActionLoading(false)
    }
  }, [])

  // ── Reject ────────────────────────────────────────────────

  const handleReject = useCallback(async (reason: string) => {
    if (!current) return
    setRejectSubmitting(true)
    try {
      const res = await fetch(`/api/hq/content/pieces/${current.id}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason }),
      })
      if (!res.ok) throw new Error(`Erro ${res.status}`)
      setIsRejectModalOpen(false)
      setPieces((prev) => {
        const next = prev.filter((p) => p.id !== current.id)
        setCurrentIndex((i) => Math.min(i, Math.max(0, next.length - 1)))
        return next
      })
      showToast('Conteúdo rejeitado.')
    } catch {
      showToast('Erro ao rejeitar conteúdo', 'error')
    } finally {
      setRejectSubmitting(false)
    }
  }, [current])

  // ── Edit caption ──────────────────────────────────────────

  const handleSaveCaption = useCallback(async (caption: string) => {
    if (!current) return
    setCaptionSaving(true)
    try {
      const res = await fetch(`/api/hq/content/pieces/${current.id}/caption`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ caption }),
      })
      if (!res.ok) throw new Error(`Erro ${res.status}`)
      setPieces((prev) =>
        prev.map((p) => (p.id === current.id ? { ...p, caption } : p))
      )
      showToast('Caption salva!')
    } catch {
      showToast('Erro ao salvar caption', 'error')
    } finally {
      setCaptionSaving(false)
    }
  }, [current])

  // ── Approve all ───────────────────────────────────────────

  const handleApproveAll = useCallback(async () => {
    setApproveAllLoading(true)
    let successCount = 0
    for (const piece of pieces) {
      try {
        const res = await fetch(`/api/hq/content/pieces/${piece.id}/approve`, { method: 'POST' })
        if (res.ok) successCount++
      } catch {
        // continue
      }
    }
    setPieces([])
    setCurrentIndex(0)
    showToast(`${successCount} peça${successCount !== 1 ? 's' : ''} aprovada${successCount !== 1 ? 's' : ''}!`)
    setApproveAllLoading(false)
  }, [pieces])

  // ── Render ────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <Loader2 size={28} className="text-purple-400 animate-spin" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-3">
        <p className="text-sm text-red-400">{error}</p>
        <button
          onClick={loadQueue}
          className="px-4 py-2 bg-white/10 hover:bg-white/20 text-white text-sm rounded-lg transition-colors"
        >
          Tentar novamente
        </button>
      </div>
    )
  }

  // AC9: Empty state
  if (pieces.length === 0) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-4 text-center">
        <div className="w-16 h-16 rounded-full bg-green-500/10 flex items-center justify-center">
          <CheckCheck size={28} className="text-green-400" />
        </div>
        <div>
          <p className="text-white/70 font-medium">Nenhum conteúdo aguardando aprovação</p>
          <p className="text-white/30 text-sm mt-1">Tudo certo por aqui!</p>
        </div>
        <Link
          href="/hq/content"
          className="px-4 py-2 bg-purple-600/20 hover:bg-purple-600/30 text-purple-300 text-sm rounded-lg transition-colors border border-purple-500/30"
        >
          Ir para Calendário
        </Link>
      </div>
    )
  }

  const hasVideo = Boolean(current?.video_url)
  const hasImage = Boolean(current?.image_url)

  return (
    <div className="flex flex-col h-full bg-black -m-4 overflow-hidden">
      {/* AC3: Header — counter + approve all */}
      <div className="flex items-center justify-between px-4 py-3 bg-black/90 border-b border-white/10 flex-shrink-0">
        <div className="flex items-center gap-3">
          <Link href="/hq/content" className="p-1.5 text-white/40 hover:text-white/70 rounded-lg hover:bg-white/10 transition-colors">
            <ChevronLeft size={18} />
          </Link>
          <div className="flex items-center gap-2 text-white/50 text-sm">
            {hasVideo ? (
              <Film size={14} className="text-purple-400" />
            ) : (
              <ImageIcon size={14} className="text-blue-400" />
            )}
            <span className="font-medium text-white/80">
              {currentIndex + 1} de {pieces.length} hoje
            </span>
          </div>
        </div>

        {/* AC8: Approve all */}
        <button
          onClick={handleApproveAll}
          disabled={approveAllLoading || actionLoading}
          className="flex items-center gap-2 px-3 py-1.5 bg-green-600/20 hover:bg-green-600/30 text-green-400 text-xs font-medium rounded-lg transition-colors border border-green-500/30 disabled:opacity-50"
        >
          {approveAllLoading ? (
            <Loader2 size={13} className="animate-spin" />
          ) : (
            <CheckCheck size={13} />
          )}
          Aprovar todos restantes
        </button>
      </div>

      {/* AC2: Preview fullscreen */}
      <div className="flex-1 relative min-h-0">
        {current ? (
          hasVideo ? (
            <VideoPreview url={current.video_url!} />
          ) : hasImage ? (
            <ImagePreview url={current.image_url!} />
          ) : (
            <div className="w-full h-full flex items-center justify-center bg-black/80">
              <p className="text-white/30 text-sm">Sem preview disponível</p>
            </div>
          )
        ) : null}
      </div>

      {/* AC4: Caption editor */}
      <CaptionEditor
        value={current?.caption ?? null}
        onSave={handleSaveCaption}
        saving={captionSaving}
      />

      {/* AC3, AC5, AC6: Action bar */}
      <div className="flex items-center justify-between px-4 py-3 bg-black/90 border-t border-white/10 flex-shrink-0 gap-3">
        {/* Navigation */}
        <button
          onClick={() => setCurrentIndex((i) => i - 1)}
          disabled={currentIndex === 0 || actionLoading}
          className="p-2.5 bg-white/5 hover:bg-white/10 text-white/50 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed rounded-xl transition-colors"
          aria-label="Peça anterior"
        >
          <ChevronLeft size={18} />
        </button>

        {/* Actions */}
        <div className="flex items-center gap-3 flex-1 justify-center">
          {/* Reject */}
          <button
            onClick={() => setIsRejectModalOpen(true)}
            disabled={actionLoading || approveAllLoading}
            className="flex items-center gap-2 px-5 py-2.5 bg-red-600/15 hover:bg-red-600/25 text-red-400 font-medium rounded-xl transition-colors border border-red-500/25 disabled:opacity-50 text-sm"
          >
            <X size={15} />
            Rejeitar
          </button>

          {/* Approve */}
          <button
            onClick={() => current && handleApprove(current.id)}
            disabled={actionLoading || approveAllLoading}
            className="flex items-center gap-2 px-6 py-2.5 bg-green-600 hover:bg-green-500 text-white font-semibold rounded-xl transition-colors disabled:opacity-50 text-sm shadow-lg shadow-green-900/30"
          >
            {actionLoading ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <Check size={15} />
            )}
            Aprovar
          </button>
        </div>

        {/* Next */}
        <button
          onClick={() => setCurrentIndex((i) => i + 1)}
          disabled={currentIndex >= pieces.length - 1 || actionLoading}
          className="p-2.5 bg-white/5 hover:bg-white/10 text-white/50 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed rounded-xl transition-colors"
          aria-label="Próxima peça"
        >
          <ChevronRight size={18} />
        </button>
      </div>

      {/* AC6: Reject Modal */}
      <RejectModal
        open={isRejectModalOpen}
        onSubmit={handleReject}
        onClose={() => setIsRejectModalOpen(false)}
        submitting={rejectSubmitting}
      />

      {/* AC10: Toast */}
      {toast && <Toast message={toast.message} type={toast.type} />}
    </div>
  )
}
