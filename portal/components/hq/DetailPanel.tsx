'use client'

import { X } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { useDetailPanel } from './DetailPanelContext'

/**
 * DetailPanel — slide-in from right, 380px wide.
 * - Push mode (main content shrinks) on screens >= 1440px
 * - Overlay mode (with backdrop) on screens < 1440px
 * Controlled by DetailPanelContext.
 */
export default function DetailPanel() {
  const { isOpen, content, closePanel } = useDetailPanel()
  const panelRef = useRef<HTMLDivElement>(null)

  // Close on click-outside (overlay mode)
  const handleBackdropClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) {
      closePanel()
    }
  }

  // Trap focus inside panel when open
  useEffect(() => {
    if (isOpen && panelRef.current) {
      panelRef.current.focus()
    }
  }, [isOpen])

  return (
    <>
      {/* ── Overlay backdrop (visible on < 1440px) ── */}
      {isOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/40 backdrop-blur-[2px] xl:hidden"
          onClick={closePanel}
          aria-hidden="true"
        />
      )}

      {/* ── Panel ── */}
      <div
        ref={panelRef}
        tabIndex={-1}
        role="complementary"
        aria-label="Detail panel"
        className={[
          // Base styles
          'flex flex-col bg-[#020208] border-l border-white/[0.08] z-40 focus:outline-none',
          // Animation
          isOpen ? 'hq-panel-slide-in' : '',
          // Positioning: fixed overlay on < 1440px, static push on >= 1440px
          // We use the `xl` (1440px) breakpoint for push vs overlay
          isOpen
            ? 'fixed top-0 right-0 bottom-0 xl:static xl:flex-shrink-0'
            : 'hidden xl:flex xl:flex-shrink-0 xl:w-0 xl:overflow-hidden',
        ].join(' ')}
        style={{
          width: isOpen ? 380 : 0,
          height: isOpen ? '100%' : undefined,
          transition: 'width 0.2s ease-out',
        }}
      >
        {/* Panel header */}
        <div className="flex items-center justify-between px-4 h-14 border-b border-white/[0.06] flex-shrink-0">
          <span className="text-[0.8125rem] font-medium text-white/60">Detalhes</span>
          <button
            onClick={closePanel}
            className="flex items-center justify-center w-7 h-7 rounded-lg text-white/40 hover:text-white/70 hover:bg-white/[0.06] transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-purple-500"
            aria-label="Fechar painel"
          >
            <X size={16} strokeWidth={1.75} />
          </button>
        </div>

        {/* Panel content */}
        <div className="flex-1 overflow-y-auto p-4">
          {content ?? (
            <div className="flex items-center justify-center h-32 text-white/20 text-sm">
              Nenhum item selecionado
            </div>
          )}
        </div>
      </div>
    </>
  )
}
