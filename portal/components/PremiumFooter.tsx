'use client'

import { useEffect, useState } from 'react'

// ── Heartbeat indicator ─────────────────────────────────────────

function HeartbeatPulse() {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] uppercase tracking-wider text-white/30 font-medium">
        Pulso
      </span>
      <div className="flex items-center gap-[3px]">
        {[0, 1, 2, 3, 4].map((i) => (
          <span
            key={i}
            className="inline-block w-[3px] rounded-full bg-accent/60"
            style={{
              height: `${6 + Math.sin((i / 4) * Math.PI) * 8}px`,
              animationDelay: `${i * 0.12}s`,
              animation: 'pulse_glow 2s ease-in-out infinite',
            }}
          />
        ))}
      </div>
    </div>
  )
}

// ── Footer ──────────────────────────────────────────────────────

export default function PremiumFooter() {
  const [version, setVersion] = useState('0.1.0')

  useEffect(() => {
    // Could fetch from API in the future
    setVersion('0.1.0')
  }, [])

  return (
    <footer className="relative mt-auto border-t border-white/[0.04]">
      {/* Gradient border top */}
      <div
        className="absolute top-0 left-0 right-0 h-px"
        style={{
          background:
            'linear-gradient(90deg, transparent 0%, rgba(124,58,237,0.3) 30%, rgba(0,229,255,0.2) 70%, transparent 100%)',
        }}
      />

      <div className="mx-auto flex h-12 max-w-7xl items-center justify-between px-4 md:px-6">
        {/* Left: brand + version */}
        <div className="flex items-center gap-3">
          <span className="text-[11px] text-white/25 font-medium">
            Powered by{' '}
            <span className="text-white/40">Sparkle AIOX</span>
          </span>
          <span className="text-[10px] font-mono text-accent/40 px-1.5 py-0.5 rounded border border-accent/10 bg-accent/5">
            v{version}
          </span>
        </div>

        {/* Center: heartbeat */}
        <div className="hidden md:flex">
          <HeartbeatPulse />
        </div>

        {/* Right: links */}
        <div className="flex items-center gap-4">
          <a
            href="https://docs.sparkleai.tech"
            target="_blank"
            rel="noopener noreferrer"
            className="text-[11px] text-white/25 hover:text-white/50 transition-colors duration-200"
          >
            Docs
          </a>
          <a
            href="https://sparkleai.tech"
            target="_blank"
            rel="noopener noreferrer"
            className="text-[11px] text-white/25 hover:text-white/50 transition-colors duration-200"
          >
            sparkleai.tech
          </a>
        </div>
      </div>
    </footer>
  )
}
