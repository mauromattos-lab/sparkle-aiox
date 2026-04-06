'use client'

/**
 * /hq/brain — Brain View (Story 3.3)
 *
 * AC1:  useBrainStats() deriva KPIs do useOverview() (sem chamada extra)
 * AC2:  useBrainChunks() lê brain_chunks via Supabase (RPC + fallback)
 * AC3:  BrainStats com 4 KPI cards
 * AC4:  NamespaceCard com barra de progresso
 * AC5:  NamespaceGrid responsivo (3→2→1 colunas)
 * AC6:  IngestionsTable com últimas 20 ingestões (janela 7 dias)
 * AC7:  Click em NamespaceCard abre DetailPanel com NamespaceDetail
 * AC8:  Click em linha abre DetailPanel com ChunkDetail
 * AC9:  Filtros de status client-side
 * AC10: BrainSkeleton durante loading
 * AC11: EmptyState gracioso se brain_chunks vazio
 * AC12: Header com Brain icon + badge total
 */

import React from 'react'
import { Brain } from 'lucide-react'
import { useBrainStats, useBrainChunks } from '@/hooks/useHQData'
import BrainStats from '@/components/hq/BrainStats'
import NamespaceGrid from '@/components/hq/NamespaceGrid'
import IngestionsTable from '@/components/hq/IngestionsTable'
import { BrainSkeleton } from '@/components/hq/LoadingSkeleton'

export default function BrainPage() {
  const { stats, isLoading: statsLoading } = useBrainStats()
  const { namespaceStats, chunks, isLoading: chunksLoading } = useBrainChunks()

  const isLoading = statsLoading || chunksLoading

  return (
    <div className="hq-page-enter hq-density flex flex-col gap-4 h-full">
      {/* Page header — AC12 */}
      <div className="flex items-center gap-2">
        <Brain size={18} className="text-purple-400" strokeWidth={1.75} aria-hidden="true" />
        <h1 className="text-lg font-semibold text-white/80">Brain</h1>
        {!isLoading && stats.total > 0 && (
          <span className="bg-purple-500/20 text-purple-300 text-xs px-2 py-0.5 rounded-full">
            {stats.total} chunks
          </span>
        )}
        <p className="text-[0.6875rem] text-white/20 font-mono ml-auto">/hq/brain</p>
      </div>

      {/* Loading skeleton — AC10 */}
      {isLoading && <BrainSkeleton />}

      {/* Content — only when data is ready */}
      {!isLoading && (
        <>
          {/* KPI cards — AC3 */}
          <BrainStats stats={stats} />

          {/* Namespace grid — AC4, AC5, AC7 */}
          <NamespaceGrid stats={namespaceStats} />

          {/* Ingestions table — AC6, AC8, AC9 */}
          <IngestionsTable chunks={chunks} />
        </>
      )}
    </div>
  )
}
