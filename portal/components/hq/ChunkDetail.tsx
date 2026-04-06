'use client'

/**
 * ChunkDetail — conteúdo do DetailPanel para um brain chunk individual.
 * AC8 (Story 3.3): namespace badge, conteúdo truncado 500c com "ver mais",
 * CurationBadge, source, created_at absoluto + relativo.
 */

import React, { useState } from 'react'
import type { BrainChunk } from '@/hooks/useHQData'
import CurationBadge, { type CurationStatus } from './CurationBadge'
import { formatAbsolute, formatRelative } from '@/lib/dateUtils'

interface ChunkDetailProps {
  chunk: BrainChunk
}

const TRUNCATE_AT = 500

export default function ChunkDetail({ chunk }: ChunkDetailProps) {
  const [expanded, setExpanded] = useState(false)
  const fullContent = chunk.canonical_content ?? chunk.raw_content ?? ''
  const isLong = fullContent.length > TRUNCATE_AT
  const displayContent = isLong && !expanded ? fullContent.slice(0, TRUNCATE_AT) + '…' : fullContent

  return (
    <div className="flex flex-col gap-4">
      {/* Namespace badge */}
      <div>
        <span className="bg-purple-500/20 text-purple-300 text-[0.7rem] px-2 py-0.5 rounded-full font-mono">
          {chunk.brain_owner ?? 'unknown'}
        </span>
      </div>

      {/* Status */}
      <div className="flex items-center gap-2">
        <span className="text-[0.6875rem] text-white/40 uppercase tracking-wide">Status</span>
        <CurationBadge
          status={(chunk.curation_status ?? 'pending') as CurationStatus}
          size="md"
        />
      </div>

      {/* Content */}
      <div>
        <h3 className="text-[0.6875rem] text-white/40 uppercase tracking-wide mb-1.5">Conteúdo</h3>
        <p className="text-[0.8125rem] text-white/70 leading-relaxed whitespace-pre-wrap break-words">
          {displayContent}
        </p>
        {isLong && (
          <button
            onClick={() => setExpanded((v) => !v)}
            className="mt-1.5 text-[0.75rem] text-purple-400 hover:text-purple-300 transition-colors duration-100 focus:outline-none focus-visible:underline"
          >
            {expanded ? 'ver menos' : 'ver mais'}
          </button>
        )}
      </div>

      {/* Source */}
      {(chunk.source_url || chunk.source_type || chunk.source_title) && (
        <div>
          <h3 className="text-[0.6875rem] text-white/40 uppercase tracking-wide mb-1">Fonte</h3>
          {chunk.source_title && (
            <p className="text-sm text-white/60">{chunk.source_title}</p>
          )}
          {chunk.source_type && (
            <p className="text-[0.75rem] text-white/40">{chunk.source_type}</p>
          )}
          {chunk.source_url && (
            <p className="text-[0.75rem] text-white/40 break-all">{chunk.source_url}</p>
          )}
        </div>
      )}

      {/* Curation note */}
      {chunk.curation_note && (
        <div>
          <h3 className="text-[0.6875rem] text-white/40 uppercase tracking-wide mb-1">Nota de Curadoria</h3>
          <p className="text-[0.8125rem] text-white/60 italic">{chunk.curation_note}</p>
        </div>
      )}

      {/* Timestamps */}
      <div>
        <h3 className="text-[0.6875rem] text-white/40 uppercase tracking-wide mb-1">Criado em</h3>
        <p className="text-sm text-white/60">{formatAbsolute(chunk.created_at)}</p>
        <p className="text-xs text-white/40">{formatRelative(chunk.created_at)}</p>
      </div>
    </div>
  )
}
