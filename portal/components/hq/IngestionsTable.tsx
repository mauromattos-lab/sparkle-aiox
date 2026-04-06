'use client'

/**
 * IngestionsTable — tabela de últimas ingestões do Brain.
 * AC6 (Story 3.3): últimos 7 dias / 20 registros, com filtro de status client-side.
 * AC8: click abre DetailPanel com chunk completo.
 * AC9: tabs de filtro Todos / Pending / Approved / Rejected.
 * AC11: empty state gracioso.
 */

import React, { useState } from 'react'
import { Inbox } from 'lucide-react'
import type { BrainChunk } from '@/hooks/useHQData'
import { useDetailPanel } from './DetailPanelContext'
import CurationBadge, { type CurationStatus } from './CurationBadge'
import ChunkDetail from './ChunkDetail'
import EmptyState from './EmptyState'
import { formatRelative } from '@/lib/dateUtils'

type FilterTab = 'all' | 'pending' | 'approved' | 'rejected'

interface IngestionsTableProps {
  chunks: BrainChunk[]
}

const TABS: { key: FilterTab; label: string }[] = [
  { key: 'all',      label: 'Todos' },
  { key: 'pending',  label: 'Pending' },
  { key: 'approved', label: 'Approved' },
  { key: 'rejected', label: 'Rejected' },
]

function filterChunks(chunks: BrainChunk[], tab: FilterTab): BrainChunk[] {
  if (tab === 'all') return chunks
  if (tab === 'pending') return chunks.filter((c) => c.curation_status === 'pending' || c.curation_status === 'review')
  return chunks.filter((c) => c.curation_status === tab)
}

export default function IngestionsTable({ chunks }: IngestionsTableProps) {
  const [activeTab, setActiveTab] = useState<FilterTab>('all')
  const { openPanel } = useDetailPanel()

  const filtered = filterChunks(chunks, activeTab)

  return (
    <div className="flex flex-col gap-3">
      {/* Section header */}
      <h2 className="text-[0.8125rem] font-semibold text-white/70">Últimas Ingestões</h2>

      {/* Status filter tabs — AC9 */}
      <div className="flex gap-0 border-b border-white/[0.08]">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={[
              'px-3 py-1.5 text-[0.75rem] font-medium transition-colors duration-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-purple-500',
              activeTab === tab.key
                ? 'border-b-2 border-purple-500 text-white'
                : 'text-white/40 hover:text-white/70 border-b-2 border-transparent',
            ].join(' ')}
            aria-selected={activeTab === tab.key}
            role="tab"
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Empty state — AC11 */}
      {filtered.length === 0 && (
        <div className="py-8">
          <EmptyState
            icon={Inbox}
            title="Nenhuma ingestão encontrada"
            description="Sem registros para o filtro selecionado"
          />
        </div>
      )}

      {/* Rows — AC6, AC8 */}
      {filtered.length > 0 && (
        <div className="flex flex-col divide-y divide-white/[0.04]" role="table" aria-label="Ingestões recentes">
          {filtered.map((chunk) => {
            const content = chunk.canonical_content ?? chunk.raw_content ?? ''
            const preview = content.slice(0, 50) + (content.length > 50 ? '…' : '')
            return (
              <div
                key={chunk.id}
                role="row"
                tabIndex={0}
                onClick={() => openPanel(<ChunkDetail chunk={chunk} />)}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') openPanel(<ChunkDetail chunk={chunk} />) }}
                className="flex items-center gap-3 py-2 px-1 hover:bg-white/[0.03] cursor-pointer transition-colors duration-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-purple-500 rounded"
              >
                {/* Namespace badge */}
                <span className="bg-purple-500/20 text-purple-300 text-[0.7rem] px-2 py-0.5 rounded-full font-mono shrink-0 max-w-[120px] truncate">
                  {chunk.brain_owner ?? 'unknown'}
                </span>

                {/* Content preview */}
                <span className="flex-1 text-white/70 text-[0.8125rem] truncate min-w-0">
                  {preview}
                </span>

                {/* Status badge */}
                <CurationBadge status={(chunk.curation_status ?? 'pending') as CurationStatus} />

                {/* Relative date */}
                <span className="text-white/40 text-[0.75rem] shrink-0">
                  {formatRelative(chunk.created_at)}
                </span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
