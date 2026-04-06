'use client'

import { useEffect, useState } from 'react'
import Sidebar from './Sidebar'
import Header from './Header'

const STORAGE_KEY = 'hq-sidebar-collapsed'

interface SidebarControllerProps {
  children: React.ReactNode
}

/**
 * SidebarController manages sidebar collapsed state:
 * - Auto-collapses on viewport < 1200px
 * - Persists manual state to localStorage
 * - Provides Header with toggle callback
 */
export default function SidebarController({ children }: SidebarControllerProps) {
  // Start with null to avoid SSR mismatch
  const [collapsed, setCollapsed] = useState<boolean | null>(null)

  // Initialize from localStorage + viewport on mount
  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY)
    const isNarrow = window.innerWidth < 1200

    if (stored !== null) {
      // Stored preference exists — use it, but force-collapse on narrow screens
      setCollapsed(stored === 'true' || isNarrow)
    } else {
      // No preference — auto-collapse on narrow
      setCollapsed(isNarrow)
    }
  }, [])

  // Listen to viewport resize — auto-collapse on narrow
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 1200) {
        setCollapsed(true)
      }
    }

    window.addEventListener('resize', handleResize, { passive: true })
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  const handleToggle = () => {
    setCollapsed((prev) => {
      const next = !prev
      localStorage.setItem(STORAGE_KEY, String(next))
      return next
    })
  }

  // Avoid flash of wrong layout — render only after mount
  if (collapsed === null) {
    return (
      <div className="flex h-screen bg-[#020208] overflow-hidden">
        <div className="w-16 h-full bg-[#020208] border-r border-white/[0.08] flex-shrink-0" />
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="h-14 border-b border-white/[0.08] flex-shrink-0" />
          <main className="flex-1 overflow-auto">{children}</main>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-screen bg-[#020208] overflow-hidden">
      <Sidebar collapsed={collapsed} onToggle={handleToggle} />
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        <Header onSidebarToggle={handleToggle} sidebarCollapsed={collapsed} />
        {children}
      </div>
    </div>
  )
}
