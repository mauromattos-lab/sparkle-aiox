'use client'

/**
 * ClientsFilters — search + sort controls for Clients view.
 * AC8: search by name (input with Search icon) + sort dropdown.
 * AC9: real-time filter with 300ms debounce.
 * AC10: default sort: health (red first), then MRR desc.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Search } from 'lucide-react'

export type SortOption = 'health' | 'mrr' | 'name'

interface ClientsFiltersProps {
  searchQuery: string
  onSearchChange: (query: string) => void
  sortBy: SortOption
  onSortChange: (sort: SortOption) => void
}

export default function ClientsFilters({
  searchQuery,
  onSearchChange,
  sortBy,
  onSortChange,
}: ClientsFiltersProps) {
  const [localQuery, setLocalQuery] = useState(searchQuery)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const val = e.target.value
      setLocalQuery(val)

      if (debounceRef.current) clearTimeout(debounceRef.current)
      debounceRef.current = setTimeout(() => {
        onSearchChange(val)
      }, 300)
    },
    [onSearchChange],
  )

  // Sync external changes
  useEffect(() => {
    setLocalQuery(searchQuery)
  }, [searchQuery])

  // Cleanup
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [])

  return (
    <div className="flex items-center gap-3 flex-wrap">
      {/* Search */}
      <div className="relative flex-1 min-w-[200px] max-w-[320px]">
        <Search
          size={14}
          className="absolute left-2.5 top-1/2 -translate-y-1/2 text-white/30 pointer-events-none"
          strokeWidth={1.75}
          aria-hidden="true"
        />
        <input
          type="text"
          value={localQuery}
          onChange={handleInputChange}
          placeholder="Buscar por nome..."
          className={[
            'w-full pl-8 pr-3 py-1.5 rounded-md',
            'bg-white/[0.04] border border-white/10',
            'text-[0.8125rem] text-white/70 placeholder:text-white/25',
            'outline-none focus:border-white/20 transition-colors duration-150',
          ].join(' ')}
          aria-label="Buscar cliente por nome"
        />
      </div>

      {/* Sort */}
      <select
        value={sortBy}
        onChange={(e) => onSortChange(e.target.value as SortOption)}
        className={[
          'px-3 py-1.5 rounded-md',
          'bg-white/[0.04] border border-white/10',
          'text-[0.8125rem] text-white/70',
          'outline-none focus:border-white/20 transition-colors duration-150',
          'cursor-pointer appearance-none',
        ].join(' ')}
        aria-label="Ordenar clientes"
        style={{ backgroundImage: 'none' }}
      >
        <option value="health" className="bg-[#0a0a1a] text-white">Health (pior primeiro)</option>
        <option value="mrr" className="bg-[#0a0a1a] text-white">MRR (maior primeiro)</option>
        <option value="name" className="bg-[#0a0a1a] text-white">Nome A-Z</option>
      </select>
    </div>
  )
}
