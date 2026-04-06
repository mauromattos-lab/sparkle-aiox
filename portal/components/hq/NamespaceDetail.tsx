'use client'

/**
 * NamespaceDetail — conteúdo do DetailPanel para um namespace.
 * AC7 (Story 3.3): header, breakdown 2x2, barra de progresso, últimas 5 ingestões.
 */

import React, { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import type { BrainNamespaceStat, BrainChunk } from '@/hooks/useHQData'
import CurationBadge from './CurationBadge'
import { formatRelative } from '@/lib/dateUtils'

interface NamespaceDetailProps {
  namespace: string
  stat: BrainNamespaceStat
}

export default function NamespaceDetail({ namespace, stat }: NamespaceDetailProps) {
  const { total, approved, pending, rejected, review } = stat
  const pendingTotal = pending + review
  const approvedPct = total > 0 ? (approved / total) * 100 : 0
  const pendingPct = total > 0 ? (pendingTotal / total) * 100 : 0

  const [recentChunks, setRecentChunks] = useState<BrainChunk[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    supabase
      .from('brain_chunks')
      .select('id, brain_owner, raw_content, canonical_content, curation_status, source_url, source_type, source_title, curation_note, created_at')
      .eq('brain_owner', namespace)
      .order('created_at', { ascending: false })
      .limit(5)
      .then(({ data }) => {
        if (!cancelled) {
          setRecentChunks((data ?? []) as BrainChunk[])
          setLoading(false)
        }
      })
    return () => { cancelled = true }
  }, [namespace])

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div>
        <h2 className="text-sm font-semibold text-white/80">{namespace}</h2>
        <p className="text-xs text-white/40 mt-0.5">{total} chunks</p>
      </div>

      {/* Breakdown 2x2 */}
      <div className="grid grid-cols-2 gap-2">
        <div className="bg-white/[0.04] rounded-lg p-2.5 text-center">
          <div className="text-lg font-bold text-white">{total}</div>
          <div className="text-[0.6875rem] text-white/40 uppercase tracking-wide">Total</div>
        </div>
        <div className="bg-white/[0.04] rounded-lg p-2.5 text-center">
          <div className="text-lg font-bold text-green-400">{approved}</div>
          <div className="text-[0.6875rem] text-white/40 uppercase tracking-wide">Aprovados</div>
        </div>
        <div className="bg-white/[0.04] rounded-lg p-2.5 text-center">
          <div className="text-lg font-bold text-yellow-400">{pendingTotal}</div>
          <div className="text-[0.6875rem] text-white/40 uppercase tracking-wide">Pendentes</div>
        </div>
        <div className="bg-white/[0.04] rounded-lg p-2.5 text-center">
          <div className="text-lg font-bold text-red-400">{rejected}</div>
          <div className="text-[0.6875rem] text-white/40 uppercase tracking-wide">Rejeitados</div>
        </div>
      </div>

      {/* Progress bar (larger) */}
      {total > 0 && (
        <div>
          <div className="flex justify-between text-[0.6875rem] text-white/40 mb-1">
            <span>Aprovados</span>
            <span>{Math.round(approvedPct)}%</span>
          </div>
          <div className="flex bg-white/10 rounded-full h-2 overflow-hidden" aria-hidden="true">
            <div className="bg-purple-500 h-full rounded-l-full" style={{ width: `${approvedPct}%` }} />
            <div className="bg-yellow-400 h-full" style={{ width: `${pendingPct}%` }} />
          </div>
        </div>
      )}

      {/* Últimas 5 ingestões */}
      <div>
        <h3 className="text-[0.6875rem] text-white/40 uppercase tracking-wide mb-2">
          Últimas 5 Ingestões
        </h3>
        {loading && (
          <div className="flex flex-col gap-2">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="hq-skeleton h-9 rounded" aria-hidden="true" />
            ))}
          </div>
        )}
        {!loading && recentChunks.length === 0 && (
          <p className="text-xs text-white/30">Nenhuma ingestão encontrada</p>
        )}
        {!loading && recentChunks.length > 0 && (
          <div className="flex flex-col gap-1.5">
            {recentChunks.map((chunk) => {
              const content = chunk.canonical_content ?? chunk.raw_content ?? ''
              return (
                <div
                  key={chunk.id}
                  className="bg-white/[0.03] rounded-lg px-2.5 py-2 flex flex-col gap-1"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[0.75rem] text-white/70 truncate flex-1">
                      {content.slice(0, 80)}{content.length > 80 ? '…' : ''}
                    </span>
                    <CurationBadge status={chunk.curation_status} />
                  </div>
                  <span className="text-[0.6875rem] text-white/30">
                    {formatRelative(chunk.created_at)}
                  </span>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
