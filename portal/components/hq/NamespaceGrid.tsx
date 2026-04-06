'use client'

/**
 * NamespaceGrid — grid responsivo de NamespaceCards.
 * AC5 (Story 3.3): 3→2→1 colunas, ordenado por total desc, EmptyState se vazio.
 */

import React from 'react'
import { Brain } from 'lucide-react'
import type { BrainNamespaceStat, BrainChunk } from '@/hooks/useHQData'
import NamespaceCard from './NamespaceCard'
import EmptyState from './EmptyState'
import { useDetailPanel } from './DetailPanelContext'
import NamespaceDetail from './NamespaceDetail'

interface NamespaceGridProps {
  stats: BrainNamespaceStat[]
}

export default function NamespaceGrid({ stats }: NamespaceGridProps) {
  const { openPanel } = useDetailPanel()

  if (stats.length === 0) {
    return (
      <EmptyState
        icon={Brain}
        title="Brain vazio"
        description="Nenhum namespace encontrado"
      />
    )
  }

  // Already sorted by total desc from hook; sort defensively here too
  const sorted = [...stats].sort((a, b) => b.total - a.total)

  return (
    <div
      className="grid gap-3"
      style={{
        gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
      }}
      aria-label="Namespaces do Brain"
    >
      {sorted.map((stat) => (
        <NamespaceCard
          key={stat.namespace}
          stat={stat}
          onClick={() => openPanel(<NamespaceDetail namespace={stat.namespace} stat={stat} />)}
        />
      ))}
    </div>
  )
}
