'use client'

import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'

interface DetailPanelState {
  isOpen: boolean
  content: React.ReactNode | null
}

interface DetailPanelContextValue {
  isOpen: boolean
  content: React.ReactNode | null
  openPanel: (content: React.ReactNode) => void
  closePanel: () => void
  togglePanel: () => void
}

const DetailPanelContext = createContext<DetailPanelContextValue | null>(null)

export function DetailPanelProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<DetailPanelState>({
    isOpen: false,
    content: null,
  })

  const openPanel = useCallback((content: React.ReactNode) => {
    setState({ isOpen: true, content })
  }, [])

  const closePanel = useCallback(() => {
    setState((prev) => ({ ...prev, isOpen: false }))
  }, [])

  const togglePanel = useCallback(() => {
    setState((prev) => ({ ...prev, isOpen: !prev.isOpen }))
  }, [])

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && state.isOpen) {
        closePanel()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [state.isOpen, closePanel])

  return (
    <DetailPanelContext.Provider value={{ ...state, openPanel, closePanel, togglePanel }}>
      {children}
    </DetailPanelContext.Provider>
  )
}

export function useDetailPanel(): DetailPanelContextValue {
  const ctx = useContext(DetailPanelContext)
  if (!ctx) {
    throw new Error('useDetailPanel must be used within DetailPanelProvider')
  }
  return ctx
}
