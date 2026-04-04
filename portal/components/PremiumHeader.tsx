'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'

// ── Navigation config ───────────────────────────────────────────

const NAV_ITEMS = [
  { href: '/command', label: 'Command Center' },
  { href: '/system', label: 'Sistema' },
  { href: '/mission-control', label: 'Mission Control' },
]

// ── Clock component ─────────────────────────────────────────────

function CockpitClock() {
  const [time, setTime] = useState('')

  useEffect(() => {
    function tick() {
      const now = new Date()
      setTime(
        now.toLocaleTimeString('pt-BR', {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        })
      )
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [])

  if (!time) return null

  return (
    <span className="font-mono text-xs tracking-widest text-white/40">
      {time}
    </span>
  )
}

// ── Status indicator ────────────────────────────────────────────

function SystemStatusDot() {
  return (
    <div className="flex items-center gap-1.5">
      <span className="relative flex h-2 w-2">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
      </span>
      <span className="text-[10px] font-medium uppercase tracking-wider text-emerald-400/70">
        Online
      </span>
    </div>
  )
}

// ── Header ──────────────────────────────────────────────────────

export default function PremiumHeader() {
  const pathname = usePathname()
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    function onScroll() {
      setScrolled(window.scrollY > 8)
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <header
      className={`
        fixed top-0 left-0 right-0 z-50
        transition-all duration-300
        ${scrolled
          ? 'bg-[#020208]/90 backdrop-blur-xl border-b border-white/[0.06] shadow-[0_1px_20px_rgba(124,58,237,0.08)]'
          : 'bg-transparent border-b border-transparent'
        }
      `}
    >
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 md:px-6">
        {/* ── Brand ─────────────────────────────── */}
        <Link href="/command" className="group flex items-center gap-2.5">
          {/* Animated logo glyph */}
          <div className="relative flex h-8 w-8 items-center justify-center">
            <div className="absolute inset-0 rounded-lg bg-gradient-to-br from-accent to-cyan opacity-20 blur-sm group-hover:opacity-40 transition-opacity duration-500" />
            <div className="relative h-6 w-6 rounded-md header-logo-gradient flex items-center justify-center">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="text-white">
                <path d="M7 1L12.196 4.25V10.75L7 14L1.804 10.75V4.25L7 1Z" stroke="currentColor" strokeWidth="1.2" fill="none" />
                <circle cx="7" cy="7.5" r="2" fill="currentColor" opacity="0.8" />
              </svg>
            </div>
          </div>
          <div className="flex flex-col leading-none">
            <span className="text-sm font-semibold tracking-tight text-white/90 group-hover:text-white transition-colors">
              Sparkle <span className="text-gradient-accent">AIOX</span>
            </span>
          </div>
        </Link>

        {/* ── Nav (desktop) ─────────────────────── */}
        <nav className="hidden md:flex items-center gap-1">
          {NAV_ITEMS.map(({ href, label }) => {
            const active = pathname === href
            return (
              <Link
                key={href}
                href={href}
                className={`
                  relative px-3 py-1.5 text-xs font-medium rounded-md transition-all duration-200
                  ${active
                    ? 'text-white bg-white/[0.06]'
                    : 'text-white/50 hover:text-white/80 hover:bg-white/[0.03]'
                  }
                `}
              >
                {label}
                {active && (
                  <span className="absolute bottom-0 left-1/2 -translate-x-1/2 w-4 h-[2px] rounded-full bg-accent" />
                )}
              </Link>
            )
          })}
        </nav>

        {/* ── Right section ─────────────────────── */}
        <div className="flex items-center gap-4">
          <SystemStatusDot />
          <div className="hidden sm:block w-px h-4 bg-white/10" />
          <CockpitClock />
        </div>
      </div>
    </header>
  )
}
