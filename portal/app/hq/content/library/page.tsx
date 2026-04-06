'use client'

/**
 * Style Library — Curation interface for Zenya's visual references.
 * CONTENT-0.1 — AC5, AC6, AC7, AC8, AC9
 *
 * Flow:
 * 1. Load images from style_library (uploaded via Supabase Storage)
 * 2. Mauro reacts: ❤️ (like → Tier A), ✗ (discard → Tier C), → (neutral → Tier B)
 * 3. After ≥ 10 likes → "Confirmar Style Library" button appears
 * 4. Confirm → POST /api/hq/content/library/confirm
 */

import React, { useState, useEffect, useCallback, useRef } from 'react'
import { Heart, X, ArrowRight, CheckCircle, Upload, Loader2, RefreshCw } from 'lucide-react'
import { createClient } from '@supabase/supabase-js'

// ── Types ────────────────────────────────────────────────────

interface StyleLibraryItem {
  id: string
  storage_path: string
  public_url: string
  tier: 'A' | 'B' | 'C'
  mauro_score: number
  style_type: string | null
  tags: string[]
  use_count: number
  embedding_status: string
  created_at: string
}

interface Stats {
  tiers: { A: number; B: number; C: number }
  reactions: { liked: number; discarded: number; neutral: number }
  total: number
}

type TierFilter = 'all' | 'A' | 'B' | 'C'

// ── Constants ────────────────────────────────────────────────

const RUNTIME_URL = process.env.NEXT_PUBLIC_RUNTIME_URL || 'https://runtime.sparkleai.tech'
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || 'https://gqhdspayjtiijcqklbys.supabase.co'
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? ''
const STORAGE_BUCKET = 'zenya-style-library'

// ── Supabase client (for Storage upload) ─────────────────────

let supabaseClient: ReturnType<typeof createClient> | null = null
function getSupabase() {
  if (!SUPABASE_ANON_KEY) {
    throw new Error(
      'NEXT_PUBLIC_SUPABASE_ANON_KEY não configurada. Adicione ao .env.local antes de fazer upload.'
    )
  }
  if (!supabaseClient) {
    supabaseClient = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)
  }
  return supabaseClient
}

// ── API helpers ──────────────────────────────────────────────

async function apiGet(path: string) {
  const res = await fetch(`/api/hq/content/library${path}`)
  if (!res.ok) throw new Error(`API error ${res.status}`)
  return res.json()
}

async function apiPost(path: string, body?: unknown) {
  const res = await fetch(`/api/hq/content/library${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Erro desconhecido' }))
    throw new Error(err.detail || `API error ${res.status}`)
  }
  return res.json()
}

// ── Tier badge ───────────────────────────────────────────────

function TierBadge({ tier }: { tier: string }) {
  const colors: Record<string, string> = {
    A: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/40',
    B: 'bg-white/10 text-white/60 border-white/20',
    C: 'bg-red-500/10 text-red-400/60 border-red-500/20',
  }
  return (
    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${colors[tier] || colors.C}`}>
      {tier}
    </span>
  )
}

// ── Image card ───────────────────────────────────────────────

function ImageCard({
  item,
  onReact,
  reacting,
}: {
  item: StyleLibraryItem
  onReact: (id: string, reaction: 'like' | 'discard' | 'neutral') => void
  reacting: string | null
}) {
  const isReacting = reacting === item.id

  const borderClass =
    item.tier === 'A'
      ? 'border-yellow-400/60'
      : item.tier === 'C' && item.mauro_score === -1
      ? 'border-red-500/30'
      : 'border-white/10'

  return (
    <div className={`relative rounded-xl overflow-hidden border-2 ${borderClass} bg-white/5 group`}>
      {/* Image */}
      <div className="relative aspect-[9/16] overflow-hidden bg-black/40">
        <img
          src={item.public_url}
          alt=""
          className="w-full h-full object-cover"
          loading="lazy"
        />
        {/* Tier badge */}
        <div className="absolute top-2 left-2">
          <TierBadge tier={item.tier} />
        </div>
        {/* Use count */}
        {item.use_count > 0 && (
          <div className="absolute top-2 right-2 bg-black/60 text-white/70 text-[10px] px-1.5 py-0.5 rounded">
            {item.use_count}×
          </div>
        )}
      </div>

      {/* Reaction buttons */}
      <div className="flex items-center justify-between p-2 gap-1">
        <button
          onClick={() => onReact(item.id, 'like')}
          disabled={isReacting}
          className={`flex-1 flex items-center justify-center gap-1 py-1.5 rounded-lg text-xs font-medium transition-all
            ${item.mauro_score === 1
              ? 'bg-pink-500/30 text-pink-400 border border-pink-500/50'
              : 'bg-white/5 text-white/40 hover:bg-pink-500/20 hover:text-pink-400 border border-transparent'
            }`}
        >
          <Heart size={12} fill={item.mauro_score === 1 ? 'currentColor' : 'none'} />
        </button>

        <button
          onClick={() => onReact(item.id, 'neutral')}
          disabled={isReacting}
          className={`flex-1 flex items-center justify-center gap-1 py-1.5 rounded-lg text-xs font-medium transition-all
            ${item.mauro_score === 0
              ? 'bg-white/20 text-white border border-white/30'
              : 'bg-white/5 text-white/40 hover:bg-white/10 hover:text-white/70 border border-transparent'
            }`}
        >
          <ArrowRight size={12} />
        </button>

        <button
          onClick={() => onReact(item.id, 'discard')}
          disabled={isReacting}
          className={`flex-1 flex items-center justify-center gap-1 py-1.5 rounded-lg text-xs font-medium transition-all
            ${item.mauro_score === -1
              ? 'bg-red-500/20 text-red-400 border border-red-500/40'
              : 'bg-white/5 text-white/40 hover:bg-red-500/10 hover:text-red-400/70 border border-transparent'
            }`}
        >
          <X size={12} />
        </button>
      </div>

      {/* Loading overlay */}
      {isReacting && (
        <div className="absolute inset-0 bg-black/40 flex items-center justify-center rounded-xl">
          <Loader2 size={20} className="text-white animate-spin" />
        </div>
      )}
    </div>
  )
}

// ── Upload zone ──────────────────────────────────────────────

function UploadZone({ onUploaded }: { onUploaded: () => void }) {
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState('')
  const [uploadError, setUploadError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFiles = async (files: FileList) => {
    const imageFiles = Array.from(files).filter((f) => f.type.startsWith('image/'))
    if (!imageFiles.length) return

    setUploadError(null)
    setUploading(true)

    let supabase: ReturnType<typeof createClient>
    try {
      supabase = getSupabase()
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : 'Configuração do Supabase inválida')
      setUploading(false)
      return
    }

    const toRegister: { storage_path: string; public_url: string }[] = []
    const failed: string[] = []
    let done = 0

    for (const file of imageFiles) {
      try {
        const path = `zenya/${Date.now()}_${file.name.replace(/\s/g, '_')}`
        const { error } = await supabase.storage.from(STORAGE_BUCKET).upload(path, file, {
          upsert: false,
        })
        if (error) throw error

        const { data: urlData } = supabase.storage.from(STORAGE_BUCKET).getPublicUrl(path)
        toRegister.push({ storage_path: path, public_url: urlData.publicUrl })
        done++
        setProgress(`${done}/${imageFiles.length}`)
      } catch (e) {
        console.error('Upload error:', file.name, e)
        failed.push(file.name)
      }
    }

    // Register batch no runtime
    if (toRegister.length > 0) {
      await apiPost('/register-batch', toRegister).catch((e) => {
        console.error('register-batch error:', e)
        setUploadError('Imagens enviadas ao Storage mas falha ao registrar no sistema. Recarregue a página.')
      })
    }

    if (failed.length > 0) {
      setUploadError(`${failed.length} arquivo(s) não enviado(s): ${failed.slice(0, 3).join(', ')}${failed.length > 3 ? '…' : ''}`)
    }

    setUploading(false)
    setProgress('')
    onUploaded()
  }

  return (
    <div
      className="border-2 border-dashed border-white/20 rounded-xl p-6 text-center hover:border-white/40 transition-colors cursor-pointer"
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => {
        e.preventDefault()
        handleFiles(e.dataTransfer.files)
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        multiple
        className="hidden"
        onChange={(e) => e.target.files && handleFiles(e.target.files)}
      />
      {uploading ? (
        <div className="flex items-center justify-center gap-2 text-white/60">
          <Loader2 size={16} className="animate-spin" />
          <span className="text-sm">Enviando... {progress}</span>
        </div>
      ) : uploadError ? (
        <div className="flex flex-col items-center gap-2 text-red-400">
          <X size={20} />
          <span className="text-sm text-center">{uploadError}</span>
          <span className="text-xs text-white/40">Clique para tentar novamente</span>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-2 text-white/40">
          <Upload size={20} />
          <span className="text-sm">Arraste imagens ou clique para enviar</span>
          <span className="text-xs">Selecione múltiplos arquivos de uma vez</span>
        </div>
      )}
    </div>
  )
}

// ── Main page ────────────────────────────────────────────────

export default function StyleLibraryPage() {
  const [items, setItems] = useState<StyleLibraryItem[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [tierFilter, setTierFilter] = useState<TierFilter>('all')
  const [loading, setLoading] = useState(true)
  const [reacting, setReacting] = useState<string | null>(null)
  const [confirming, setConfirming] = useState(false)
  const [confirmed, setConfirmed] = useState(false)
  const [confirmResult, setConfirmResult] = useState<{ tier_a: number; tier_b: number; tier_c: number } | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const path = tierFilter === 'all' ? '' : `?tier=${tierFilter}`
      const data = await apiGet(path)
      setItems(data.items || [])
      setStats(data.stats || null)
    } catch (e) {
      setError('Erro ao carregar a Style Library')
    } finally {
      setLoading(false)
    }
  }, [tierFilter])

  useEffect(() => {
    load()
  }, [load])

  const handleReact = useCallback(async (id: string, reaction: 'like' | 'discard' | 'neutral') => {
    setReacting(id)
    try {
      await apiPost(`/${id}/react`, { reaction })
      // Atualizar item localmente sem reload completo
      setItems((prev) =>
        prev.map((item) => {
          if (item.id !== id) return item
          const score = reaction === 'like' ? 1 : reaction === 'discard' ? -1 : 0
          const tier = score === 1 ? 'A' : score === -1 ? 'C' : 'B'
          return { ...item, mauro_score: score, tier: tier as 'A' | 'B' | 'C' }
        })
      )
      // Atualizar stats localmente
      setStats((prev) => {
        if (!prev) return prev
        // Simples recálculo das reações
        return prev
      })
    } catch (e) {
      console.error('React error:', e)
    } finally {
      setReacting(null)
    }
  }, [])

  const handleConfirm = async () => {
    setConfirming(true)
    try {
      const result = await apiPost('/confirm?creator_id=zenya')
      setConfirmed(true)
      setConfirmResult(result)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Erro ao confirmar'
      setError(msg)
    } finally {
      setConfirming(false)
    }
  }

  const likedCount = items.filter((i) => i.mauro_score === 1).length
  const discardedCount = items.filter((i) => i.mauro_score === -1).length
  const neutralCount = items.filter((i) => i.mauro_score === 0).length
  const canConfirm = likedCount >= 10 && !confirmed

  const filtered = tierFilter === 'all' ? items : items.filter((i) => i.tier === tierFilter)

  return (
    <div className="flex flex-col gap-6 pb-8">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Style Library</h1>
          <p className="text-sm text-white/50 mt-0.5">Curadoria visual da Zenya — referências para geração de conteúdo</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={load}
            className="p-2 rounded-lg bg-white/5 hover:bg-white/10 text-white/50 hover:text-white transition-colors"
          >
            <RefreshCw size={14} />
          </button>
          {canConfirm && (
            <button
              onClick={handleConfirm}
              disabled={confirming}
              className="flex items-center gap-2 px-4 py-2 bg-yellow-500 hover:bg-yellow-400 text-black text-sm font-semibold rounded-lg transition-colors disabled:opacity-60"
            >
              {confirming ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle size={14} />}
              Confirmar Style Library
            </button>
          )}
        </div>
      </div>

      {/* Confirmation success */}
      {confirmed && confirmResult && (
        <div className="flex items-center gap-3 p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-xl">
          <CheckCircle size={18} className="text-yellow-400 shrink-0" />
          <div>
            <p className="text-sm font-medium text-yellow-400">Style Library confirmada!</p>
            <p className="text-xs text-white/60 mt-0.5">
              Tier A: {confirmResult.tier_a} canônicas · Tier B: {confirmResult.tier_b} variações · Tier C: {confirmResult.tier_c} descartadas
            </p>
          </div>
        </div>
      )}

      {/* Stats bar */}
      <div className="flex items-center gap-4 text-sm">
        <span className="text-pink-400 font-medium">❤️ {likedCount} curtidas</span>
        <span className="text-white/30">·</span>
        <span className="text-red-400/70">✗ {discardedCount} descartados</span>
        <span className="text-white/30">·</span>
        <span className="text-white/50">→ {neutralCount} neutros</span>
        <span className="text-white/30">·</span>
        <span className="text-white/40">{stats?.total || items.length} total</span>
      </div>

      {/* Tier filter */}
      <div className="flex gap-2">
        {(['all', 'A', 'B', 'C'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTierFilter(t)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              tierFilter === t
                ? 'bg-white/20 text-white'
                : 'bg-white/5 text-white/40 hover:bg-white/10 hover:text-white/70'
            }`}
          >
            {t === 'all' ? `Todas (${items.length})` : `Tier ${t} (${items.filter((i) => i.tier === t).length})`}
          </button>
        ))}
      </div>

      {/* Upload zone */}
      <UploadZone onUploaded={load} />

      {/* Error */}
      {error && (
        <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Confirm hint */}
      {likedCount > 0 && likedCount < 10 && !confirmed && (
        <p className="text-xs text-white/40 text-center">
          Curta mais {10 - likedCount} imagem{10 - likedCount !== 1 ? 's' : ''} para confirmar a Style Library
        </p>
      )}

      {/* Grid */}
      {loading ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          {Array.from({ length: 20 }).map((_, i) => (
            <div key={i} className="aspect-[9/16] rounded-xl bg-white/5 animate-pulse" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-white/30">
          <p className="text-sm">Nenhuma imagem encontrada.</p>
          <p className="text-xs mt-1">Envie imagens usando o campo acima.</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          {filtered.map((item) => (
            <ImageCard
              key={item.id}
              item={item}
              onReact={handleReact}
              reacting={reacting}
            />
          ))}
        </div>
      )}
    </div>
  )
}
