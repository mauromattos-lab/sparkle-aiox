'use client'

import { useState, useRef, useEffect } from 'react'
import { Menu, LogOut, ChevronDown } from 'lucide-react'
import { useRouter } from 'next/navigation'

interface HeaderProps {
  onSidebarToggle: () => void
  sidebarCollapsed: boolean
}

function UserMenu() {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [loggingOut, setLoggingOut] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  // Close on click outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    if (open) document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open])

  async function handleLogout() {
    setLoggingOut(true)
    try {
      await fetch('/api/auth/admin-logout', { method: 'POST' })
    } finally {
      router.push('/login')
    }
  }

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 pl-2 border-l border-white/[0.06] ml-1 hover:opacity-80 transition-opacity focus:outline-none focus-visible:ring-2 focus-visible:ring-purple-500 rounded-lg px-1 py-0.5"
        aria-label="Menu do usuário"
        aria-expanded={open}
        aria-haspopup="menu"
      >
        <div className="w-7 h-7 rounded-full bg-gradient-to-br from-purple-500 to-purple-700 flex items-center justify-center flex-shrink-0">
          <span className="text-white text-[10px] font-semibold leading-none select-none">M</span>
        </div>
        <span className="text-[0.8125rem] text-white/60 font-medium hidden md:block">Mauro</span>
        <ChevronDown
          size={12}
          strokeWidth={2}
          className={`text-white/30 hidden md:block transition-transform duration-150 ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {/* Dropdown menu */}
      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full mt-2 w-44 rounded-xl bg-[#0d0d18] border border-white/[0.08] shadow-2xl shadow-black/50 overflow-hidden z-50 animate-slide-in"
        >
          <div className="px-3 py-2.5 border-b border-white/[0.06]">
            <p className="text-[11px] text-white/40 leading-none">Conectado como</p>
            <p className="text-[12px] text-white/70 font-medium mt-0.5 truncate">Mauro Mattos</p>
          </div>

          <button
            role="menuitem"
            onClick={handleLogout}
            disabled={loggingOut}
            className="flex items-center gap-2.5 w-full px-3 py-2.5 text-[12px] text-red-400 hover:bg-red-500/10 hover:text-red-300 transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <LogOut size={13} strokeWidth={2} />
            <span>{loggingOut ? 'Saindo...' : 'Sair'}</span>
          </button>
        </div>
      )}
    </div>
  )
}

export default function Header({ onSidebarToggle, sidebarCollapsed }: HeaderProps) {
  return (
    <header
      className="flex items-center h-14 px-4 gap-3 bg-[#020208] border-b border-white/[0.08] flex-shrink-0 z-10"
      style={{ height: 56 }}
      role="banner"
    >
      {/* Hamburger toggle — always visible */}
      <button
        onClick={onSidebarToggle}
        className="flex items-center justify-center w-8 h-8 rounded-lg text-white/40 hover:text-white/70 hover:bg-white/[0.06] transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-purple-500 flex-shrink-0"
        aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        aria-expanded={!sidebarCollapsed}
      >
        <Menu size={18} strokeWidth={1.75} />
      </button>

      {/* Logo + Title */}
      <div className="flex items-center gap-2 flex-shrink-0">
        {/* Sparkle logo mark */}
        <div className="w-6 h-6 rounded-md bg-gradient-to-br from-purple-600 to-cyan-500 flex items-center justify-center flex-shrink-0">
          <span className="text-white text-[10px] font-bold leading-none">S</span>
        </div>
        <span className="text-[0.8125rem] font-semibold text-white/80 tracking-tight">
          Portal HQ
        </span>
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* System health indicator */}
      <div
        className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/[0.04] border border-white/[0.06]"
        title="System health"
        aria-label="System health: OK"
      >
        <span
          className="w-1.5 h-1.5 rounded-full bg-[#22c55e] animate-pulse-glow flex-shrink-0"
          aria-hidden="true"
        />
        <span className="text-[0.6875rem] text-white/50 font-mono leading-none hidden sm:block">
          System OK
        </span>
      </div>

      {/* User dropdown with logout */}
      <UserMenu />
    </header>
  )
}
