'use client'

import { useState, useEffect, FormEvent } from 'react'
import { useRouter } from 'next/navigation'

type ActiveTab = 'cliente' | 'admin'

// ── Animated background particles ───────────────────────────────

function AmbientGlow() {
  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 overflow-hidden">
      {/* Primary accent orb */}
      <div
        className="absolute w-[600px] h-[600px] rounded-full blur-[160px] opacity-[0.07]"
        style={{
          top: '-15%',
          left: '20%',
          background: 'radial-gradient(circle, #7c3aed 0%, transparent 70%)',
          animation: 'float_orb_1 12s ease-in-out infinite',
        }}
      />
      {/* Cyan orb */}
      <div
        className="absolute w-[500px] h-[500px] rounded-full blur-[140px] opacity-[0.05]"
        style={{
          bottom: '-10%',
          right: '10%',
          background: 'radial-gradient(circle, #00e5ff 0%, transparent 70%)',
          animation: 'float_orb_2 15s ease-in-out infinite',
        }}
      />
      {/* Subtle grid overlay */}
      <div className="absolute inset-0 bg-grid opacity-30" />
    </div>
  )
}

// ── Logo component ──────────────────────────────────────────────

function SparkleLogoMark() {
  return (
    <div className="relative flex h-12 w-12 items-center justify-center">
      <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-accent to-cyan opacity-20 blur-md animate-pulse-glow" />
      <div
        className="relative h-10 w-10 rounded-xl flex items-center justify-center"
        style={{
          background: 'linear-gradient(135deg, #7c3aed 0%, #06b6d4 100%)',
          backgroundSize: '200% 200%',
          animation: 'gradient_shift 6s ease infinite',
        }}
      >
        <svg width="20" height="20" viewBox="0 0 14 14" fill="none" className="text-white">
          <path
            d="M7 1L12.196 4.25V10.75L7 14L1.804 10.75V4.25L7 1Z"
            stroke="currentColor"
            strokeWidth="1.2"
            fill="none"
          />
          <circle cx="7" cy="7.5" r="2" fill="currentColor" opacity="0.8" />
        </svg>
      </div>
    </div>
  )
}

// ── Heartbeat indicator (reused from PremiumFooter pattern) ─────

function LoginHeartbeat() {
  return (
    <div className="flex items-center gap-[3px]">
      {[0, 1, 2, 3, 4].map((i) => (
        <span
          key={i}
          className="inline-block w-[2px] rounded-full bg-accent/50"
          style={{
            height: `${4 + Math.sin((i / 4) * Math.PI) * 6}px`,
            animationDelay: `${i * 0.12}s`,
            animation: 'pulse_glow 2s ease-in-out infinite',
          }}
        />
      ))}
    </div>
  )
}

// ── Main login page ─────────────────────────────────────────────

export default function LoginPage() {
  const router = useRouter()
  const [tab, setTab] = useState<ActiveTab>('cliente')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  function switchTab(next: ActiveTab) {
    if (next === tab) return
    setTab(next)
    setError('')
    setEmail('')
    setPassword('')
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)

    const isAdmin = tab === 'admin'
    const endpoint = isAdmin ? '/api/auth/admin-login' : '/api/auth/login'
    const redirectTo = isAdmin ? '/hq' : '/dashboard'

    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), password }),
      })

      const data = await res.json()

      if (!res.ok) {
        setError(data.error || 'Erro ao fazer login.')
        setLoading(false)
        return
      }

      router.push(redirectTo)
    } catch {
      setError('Falha na conexao. Verifique sua internet e tente novamente.')
      setLoading(false)
    }
  }

  return (
    <>
      <AmbientGlow />

      {/* Custom keyframes for this page */}
      <style jsx global>{`
        @keyframes float_orb_1 {
          0%, 100% { transform: translate(0, 0) scale(1); }
          33% { transform: translate(30px, -20px) scale(1.05); }
          66% { transform: translate(-20px, 15px) scale(0.95); }
        }
        @keyframes float_orb_2 {
          0%, 100% { transform: translate(0, 0) scale(1); }
          50% { transform: translate(-40px, -30px) scale(1.08); }
        }
        @keyframes shimmer {
          0% { background-position: -200% center; }
          100% { background-position: 200% center; }
        }
      `}</style>

      <div className="relative flex flex-1 items-center justify-center px-4 py-12">
        <div
          className={`w-full max-w-[420px] transition-all duration-700 ${
            mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'
          }`}
        >
          {/* ── Branding ────────────────────────────── */}
          <div className="flex flex-col items-center mb-8">
            <SparkleLogoMark />
            <div className="mt-4 flex items-center gap-2">
              <span className="text-lg font-semibold text-white/90 tracking-tight">
                Sparkle
              </span>
              <span className="text-lg font-semibold text-gradient-accent tracking-tight">
                AIOX
              </span>
            </div>
            <p className="mt-1 text-[13px] text-white/30 tracking-wide uppercase font-medium">
              Sua IA, Seu Jeito
            </p>
          </div>

          {/* ── Login card ──────────────────────────── */}
          <div className="relative rounded-2xl overflow-hidden">
            {/* Gradient border effect */}
            <div
              className="absolute inset-0 rounded-2xl p-px"
              style={{
                background:
                  'linear-gradient(135deg, rgba(124,58,237,0.3) 0%, rgba(0,229,255,0.15) 50%, rgba(124,58,237,0.1) 100%)',
              }}
            >
              <div className="w-full h-full rounded-2xl bg-[#020208]" />
            </div>

            {/* Card content */}
            <div className="relative glass rounded-2xl p-8 space-y-6">
              {/* Value proposition */}
              <div className="text-center">
                <h1 className="text-xl font-semibold text-white mb-1.5">
                  {tab === 'admin' ? 'Acesso Administrativo' : 'Acesse seu cockpit de IA'}
                </h1>
                <p className="text-sm text-white/40 leading-relaxed">
                  {tab === 'admin'
                    ? 'Painel de gestao interna da Sparkle AIOX.'
                    : 'Acompanhe resultados, insights e o poder da sua inteligencia artificial em tempo real.'}
                </p>
              </div>

              {/* Tab switcher */}
              <div className="flex rounded-xl bg-white/[0.04] border border-white/[0.06] p-1">
                {(['cliente', 'admin'] as const).map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => switchTab(t)}
                    className={`
                      flex-1 py-2 rounded-lg text-xs font-semibold uppercase tracking-wider
                      transition-all duration-200
                      ${tab === t
                        ? 'bg-accent/20 text-accent border border-accent/30'
                        : 'text-white/35 hover:text-white/55 border border-transparent'}
                    `}
                  >
                    {t === 'cliente' ? 'Cliente' : 'Admin'}
                  </button>
                ))}
              </div>

              {/* Error message */}
              {error && (
                <div className="flex items-start gap-2.5 px-4 py-3 rounded-xl text-sm bg-red-500/10 border border-red-500/20 text-red-400 animate-slide-in">
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    className="shrink-0 mt-0.5"
                  >
                    <circle cx="12" cy="12" r="10" />
                    <line x1="12" y1="8" x2="12" y2="12" />
                    <line x1="12" y1="16" x2="12.01" y2="16" />
                  </svg>
                  <span>{error}</span>
                </div>
              )}

              {/* Form */}
              <form onSubmit={handleSubmit} className="space-y-4">
                {/* Email */}
                <div className="space-y-1.5">
                  <label
                    htmlFor="email"
                    className="block text-xs font-medium text-white/50 uppercase tracking-wider"
                  >
                    Email
                  </label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
                      <svg
                        width="16"
                        height="16"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        className="text-white/25"
                      >
                        <rect x="2" y="4" width="20" height="16" rx="2" />
                        <path d="M22 4L12 13L2 4" />
                      </svg>
                    </div>
                    <input
                      id="email"
                      type="email"
                      required
                      autoComplete="email"
                      autoFocus
                      placeholder="seu@email.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      disabled={loading}
                      className="
                        w-full pl-10 pr-4 py-3 rounded-xl
                        bg-white/[0.03] border border-white/[0.08]
                        text-white text-sm placeholder:text-white/20
                        outline-none
                        transition-all duration-200
                        focus:border-accent/40 focus:bg-white/[0.05] focus:ring-1 focus:ring-accent/20
                        disabled:opacity-50 disabled:cursor-not-allowed
                      "
                    />
                  </div>
                </div>

                {/* Password */}
                <div className="space-y-1.5">
                  <label
                    htmlFor="password"
                    className="block text-xs font-medium text-white/50 uppercase tracking-wider"
                  >
                    Senha
                  </label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
                      <svg
                        width="16"
                        height="16"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        className="text-white/25"
                      >
                        <rect x="3" y="11" width="18" height="11" rx="2" />
                        <path d="M7 11V7a5 5 0 0110 0v4" />
                      </svg>
                    </div>
                    <input
                      id="password"
                      type={showPassword ? 'text' : 'password'}
                      required
                      autoComplete="current-password"
                      placeholder="Sua senha"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      disabled={loading}
                      className="
                        w-full pl-10 pr-11 py-3 rounded-xl
                        bg-white/[0.03] border border-white/[0.08]
                        text-white text-sm placeholder:text-white/20
                        outline-none
                        transition-all duration-200
                        focus:border-accent/40 focus:bg-white/[0.05] focus:ring-1 focus:ring-accent/20
                        disabled:opacity-50 disabled:cursor-not-allowed
                      "
                    />
                    <button
                      type="button"
                      tabIndex={-1}
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-white/25 hover:text-white/50 transition-colors"
                    >
                      {showPassword ? (
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                          <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94" />
                          <path d="M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19" />
                          <line x1="1" y1="1" x2="23" y2="23" />
                        </svg>
                      ) : (
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                          <circle cx="12" cy="12" r="3" />
                        </svg>
                      )}
                    </button>
                  </div>
                </div>

                {/* Forgot password link */}
                <div className="flex justify-end">
                  <a
                    href="https://wa.me/5512982201239?text=Ol%C3%A1%2C%20preciso%20recuperar%20minha%20senha%20do%20portal%20Sparkle."
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-accent/60 hover:text-accent transition-colors duration-200"
                  >
                    Esqueceu a senha?
                  </a>
                </div>

                {/* Submit button */}
                <button
                  type="submit"
                  disabled={loading || !email || !password}
                  className="
                    relative w-full py-3 px-6 rounded-xl font-semibold text-sm text-white
                    overflow-hidden
                    transition-all duration-300
                    disabled:opacity-40 disabled:cursor-not-allowed
                    active:scale-[0.98]
                    group
                  "
                  style={{
                    background: loading
                      ? 'rgba(124, 58, 237, 0.3)'
                      : 'linear-gradient(135deg, #7c3aed 0%, #6d28d9 50%, #4c1d95 100%)',
                  }}
                >
                  {/* Hover shimmer effect */}
                  <div
                    className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500"
                    style={{
                      background:
                        'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.08) 50%, transparent 100%)',
                      backgroundSize: '200% 100%',
                      animation: 'shimmer 2s linear infinite',
                    }}
                  />

                  {/* Button content */}
                  <span className="relative flex items-center justify-center gap-2">
                    {loading ? (
                      <>
                        <svg
                          className="animate-spin h-4 w-4"
                          viewBox="0 0 24 24"
                          fill="none"
                        >
                          <circle
                            cx="12"
                            cy="12"
                            r="10"
                            stroke="currentColor"
                            strokeWidth="3"
                            className="opacity-20"
                          />
                          <path
                            d="M12 2a10 10 0 019.95 9"
                            stroke="currentColor"
                            strokeWidth="3"
                            strokeLinecap="round"
                          />
                        </svg>
                        <span>Autenticando...</span>
                      </>
                    ) : (
                      <>
                        <span>{tab === 'admin' ? 'Entrar' : 'Entrar no Cockpit'}</span>
                        <svg
                          width="16"
                          height="16"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          className="transition-transform duration-200 group-hover:translate-x-0.5"
                        >
                          <path d="M5 12h14M12 5l7 7-7 7" />
                        </svg>
                      </>
                    )}
                  </span>

                  {/* Glow effect */}
                  {!loading && (
                    <div className="absolute inset-0 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity duration-300 glow-accent" />
                  )}
                </button>
              </form>

              {/* Divider + WhatsApp — only on cliente tab */}
              {tab === 'cliente' && (
                <>
                  <div className="flex items-center gap-3">
                    <div className="flex-1 h-px bg-white/[0.06]" />
                    <span className="text-[10px] text-white/20 uppercase tracking-wider font-medium">
                      ou
                    </span>
                    <div className="flex-1 h-px bg-white/[0.06]" />
                  </div>

                  <a
                    href="https://wa.me/5512982201239?text=Ol%C3%A1%2C%20preciso%20do%20link%20de%20acesso%20ao%20portal%20Sparkle."
                    target="_blank"
                    rel="noopener noreferrer"
                    className="
                      flex items-center justify-center gap-2 w-full py-2.5 px-4 rounded-xl
                      text-sm text-white/50 font-medium
                      bg-white/[0.03] border border-white/[0.06]
                      hover:bg-white/[0.06] hover:text-white/70 hover:border-white/[0.1]
                      transition-all duration-200
                    "
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" className="opacity-60">
                      <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
                    </svg>
                    Acessar via WhatsApp
                  </a>
                </>
              )}
            </div>
          </div>

          {/* ── Footer ──────────────────────────────── */}
          <div className="mt-8 flex flex-col items-center gap-3">
            <div className="flex items-center gap-2">
              <LoginHeartbeat />
              <span className="text-[10px] text-white/20 uppercase tracking-wider font-medium">
                Sistema ativo
              </span>
            </div>
            <p className="text-[11px] text-white/15">
              Powered by Sparkle AIOX
            </p>
          </div>
        </div>
      </div>
    </>
  )
}
