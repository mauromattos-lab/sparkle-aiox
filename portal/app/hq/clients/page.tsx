'use client'

/**
 * /hq/clients — Clients View (Story 2.2)
 *
 * AC1:  renders real data from useClients()
 * AC2:  MRRSummary at top
 * AC3:  ClientsGrid with responsive CSS grid
 * AC8:  ClientsFilters with search + sort
 * AC9:  debounced search
 * AC10: default sort: health (red first), then MRR desc
 * AC11: page title with Users icon + active count
 * AC12: ClientsSkeleton loading state
 * AC13: error state with AlertCircle
 * AC14: empty state (no clients)
 * AC16: auto-refresh 30s via SWR
 * AC19: sidebar nav shows active state (handled by Sidebar component via pathname)
 */

import React, { useMemo, useState } from 'react'
import { Users, AlertCircle } from 'lucide-react'
import { useClients, type ClientRecord } from '@/hooks/useHQData'
import MRRSummary from '@/components/hq/MRRSummary'
import ClientsGrid from '@/components/hq/ClientsGrid'
import ClientsFilters, { type SortOption } from '@/components/hq/ClientsFilters'
import EmptyState from '@/components/hq/EmptyState'
import { ClientsSkeleton } from '@/components/hq/LoadingSkeleton'

// ── Health sort weight ──────────────────────────────────────────────────────

const HEALTH_WEIGHT: Record<string, number> = {
  red: 0,
  yellow: 1,
  green: 2,
}

function sortClients(clients: ClientRecord[], sortBy: SortOption): ClientRecord[] {
  return [...clients].sort((a, b) => {
    switch (sortBy) {
      case 'health': {
        const hDiff = (HEALTH_WEIGHT[a.health_status] ?? 2) - (HEALTH_WEIGHT[b.health_status] ?? 2)
        if (hDiff !== 0) return hDiff
        // Within same health, sort by MRR desc
        return (b.mrr ?? 0) - (a.mrr ?? 0)
      }
      case 'mrr':
        return (b.mrr ?? 0) - (a.mrr ?? 0)
      case 'name':
        return (a.name ?? '').localeCompare(b.name ?? '', 'pt-BR')
      default:
        return 0
    }
  })
}

// ── Page component ──────────────────────────────────────────────────────────

export default function ClientsPage() {
  const { data, isLoading, error } = useClients()
  const [searchQuery, setSearchQuery] = useState('')
  const [sortBy, setSortBy] = useState<SortOption>('health')

  // Normalize clients array (handle both { clients: [...] } and direct array)
  const allClients = useMemo<ClientRecord[]>(() => {
    if (!data) return []
    if (Array.isArray(data.clients)) return data.clients
    if (Array.isArray(data)) return data as unknown as ClientRecord[]
    return []
  }, [data])

  // Filter by search query (case-insensitive substring match on name)
  const filteredClients = useMemo(() => {
    if (!searchQuery.trim()) return allClients
    const q = searchQuery.toLowerCase().trim()
    return allClients.filter(
      (c) =>
        c.name?.toLowerCase().includes(q) ||
        c.empresa?.toLowerCase().includes(q),
    )
  }, [allClients, searchQuery])

  // Sort
  const sortedClients = useMemo(
    () => sortClients(filteredClients, sortBy),
    [filteredClients, sortBy],
  )

  // ── Render ──────────────────────────────────────────────────────────────

  return (
    <div className="hq-page-enter hq-density flex flex-col gap-4 h-full">
      {/* Page header — AC11 */}
      <div className="flex items-center gap-3">
        <Users size={20} className="text-purple-400" strokeWidth={1.75} aria-hidden="true" />
        <div>
          <h1 className="text-[0.9375rem] font-semibold text-white/80 leading-tight">
            Clientes
            {!isLoading && allClients.length > 0 && (
              <span className="text-white/30 font-normal ml-2 text-[0.8125rem]">
                {allClients.length}
              </span>
            )}
          </h1>
          <p className="text-[0.6875rem] text-white/30 font-mono mt-0.5">/hq/clients</p>
        </div>
      </div>

      {/* Loading state — AC12 */}
      {isLoading && (
        <>
          {/* MRR Summary skeleton */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="bg-white/[0.04] backdrop-blur-xl border border-white/10 rounded-lg p-3 h-[60px] animate-pulse" />
            ))}
          </div>
          <ClientsSkeleton count={6} />
        </>
      )}

      {/* Error state — AC13 */}
      {!isLoading && error && (
        <EmptyState
          icon={AlertCircle}
          title="Nao foi possivel carregar clientes"
          description="Tentando novamente..."
        />
      )}

      {/* Empty state — AC14 */}
      {!isLoading && !error && allClients.length === 0 && (
        <EmptyState
          icon={Users}
          title="Nenhum cliente cadastrado"
        />
      )}

      {/* Main content */}
      {!isLoading && !error && allClients.length > 0 && (
        <>
          {/* MRR Summary — AC2 */}
          <MRRSummary clients={allClients} />

          {/* Filters — AC8, AC9, AC10 */}
          <ClientsFilters
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
            sortBy={sortBy}
            onSortChange={setSortBy}
          />

          {/* Grid — AC3, AC4, AC5, AC6, AC7, AC15, AC17, AC18 */}
          {sortedClients.length > 0 ? (
            <ClientsGrid clients={sortedClients} />
          ) : (
            <div className="flex flex-col items-center justify-center py-12 gap-2">
              <Users size={32} className="text-white/15" strokeWidth={1} aria-hidden="true" />
              <p className="text-[0.8125rem] text-white/40">
                Nenhum cliente encontrado para &ldquo;{searchQuery}&rdquo;
              </p>
            </div>
          )}
        </>
      )}
    </div>
  )
}
