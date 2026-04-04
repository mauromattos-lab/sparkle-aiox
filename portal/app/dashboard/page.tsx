'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import type { Client } from '@/lib/supabase'
import { useClientIdentity, planLabel } from '@/hooks/useClientIdentity'
import DashboardZenya from '@/components/DashboardZenya'
import DashboardTrafego from '@/components/DashboardTrafego'
import ValueNarrative from '@/components/ValueNarrative'
import GamificationPanel from '@/components/GamificationPanel'

export default function DashboardPage() {
  const router = useRouter()
  const [client, setClient] = useState<Client | null>(null)
  const [mounted, setMounted] = useState(false)
  const clientIdentity = useClientIdentity()

  useEffect(() => {
    setMounted(true)
    // Carregar dados do cliente via API route autenticada (cookie HTTP-only)
    fetch('/api/auth/me')
      .then((res) => {
        if (!res.ok) {
          router.replace('/?msg=sessao-expirada')
          return null
        }
        return res.json()
      })
      .then((data) => {
        if (data?.client) {
          setClient(data.client)
        }
      })
      .catch(() => {
        router.replace('/?msg=erro-autenticacao')
      })
  }, [router])

  async function handleLogout() {
    await fetch('/api/auth/logout', { method: 'POST' })
    router.replace('/')
  }

  if (!mounted || !client) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <svg className="animate-spin w-8 h-8 text-accent" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
          </svg>
          <span className="text-slate-500 text-sm">Verificando seu acesso...</span>
        </div>
      </div>
    )
  }

  const hasZenya = Boolean(client.has_zenya)
  const hasTrafego = Boolean(client.has_trafego)

  return (
    <div className="min-h-screen">
      {/* Ambient glow */}
      <div aria-hidden="true" className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute top-[-10%] left-[40%] w-[600px] h-[400px] rounded-full bg-accent/6 blur-[140px]" />
        <div className="absolute bottom-[10%] right-[10%] w-[400px] h-[400px] rounded-full bg-cyan/4 blur-[120px]" />
      </div>

      {/* Header */}
      <header className="relative z-10 border-b border-white/6 bg-background/80 backdrop-blur-md sticky top-0">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          {/* Logo + Business Identity */}
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-accent to-accent-light flex items-center justify-center glow-accent">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" fill="white" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <span className="text-sm font-semibold text-white tracking-tight">Sparkle AI</span>
            {clientIdentity.plan && (
              <span className="hidden sm:inline text-[10px] font-mono px-2 py-0.5 rounded-full border bg-accent/15 text-accent-light border-accent/25">
                {planLabel(clientIdentity.plan)}
              </span>
            )}
            {clientIdentity.identity?.zenya && (
              <div className="hidden md:flex items-center gap-1 px-1.5 py-0.5 rounded bg-[#0ea5e9]/10 border border-[#0ea5e9]/15">
                <span className="w-3 h-3 rounded-full bg-[#0ea5e9]/30 flex items-center justify-center">
                  <svg width="6" height="6" viewBox="0 0 24 24" fill="none"
                    stroke="#0ea5e9" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" />
                  </svg>
                </span>
                <span className="text-[10px] font-mono text-[#0ea5e9]/70">
                  {clientIdentity.identity.zenya.name}
                </span>
              </div>
            )}
          </div>

          {/* User + logout */}
          <div className="flex items-center gap-3">
            <div className="flex flex-col items-end">
              <span className="text-sm font-medium text-white leading-none">
                <span className="sm:hidden">{client.name.split(' ')[0]}</span>
                <span className="hidden sm:inline">{client.company}</span>
              </span>
              <span className="text-xs text-slate-500 mt-0.5 hidden sm:block">{client.name}</span>
            </div>
            <button
              onClick={handleLogout}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-slate-400 hover:text-white
                         hover:bg-white/6 border border-transparent hover:border-white/8
                         transition-all duration-200"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                <polyline points="16 17 21 12 16 7"/>
                <line x1="21" y1="12" x2="9" y2="12"/>
              </svg>
              Sair
            </button>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="relative z-10 max-w-5xl mx-auto px-4 sm:px-6 py-8 sm:py-12">
        {/* Welcome */}
        <div className="mb-8">
          <h1 className="text-2xl sm:text-3xl font-bold text-white mb-1">
            {clientIdentity.greeting || `Olá, ${client.name.split(' ')[0]}`}
          </h1>
          <p className="text-slate-400 text-sm">
            Seu painel <span className="text-white/70">{client.company}</span> &mdash; tudo num so lugar.
          </p>
          {/* Quick stats from identity */}
          {clientIdentity.identity?.stats && (clientIdentity.identity.stats.conversationsToday > 0 || clientIdentity.identity.stats.brainChunks > 0) && (
            <div className="flex flex-wrap gap-3 mt-3">
              {clientIdentity.identity.stats.conversationsToday > 0 && (
                <div className="flex items-center gap-1.5 text-xs text-white/40">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#0ea5e9]" />
                  <span>
                    Zenya resolveu <span className="text-[#0ea5e9] font-medium">{clientIdentity.identity.stats.resolvedToday}</span> de {clientIdentity.identity.stats.conversationsToday} conversas hoje
                  </span>
                </div>
              )}
              {clientIdentity.identity.stats.brainChunks > 0 && (
                <div className="flex items-center gap-1.5 text-xs text-white/40">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#3b82f6]" />
                  <span>
                    Brain tem <span className="text-[#3b82f6] font-medium">{clientIdentity.identity.stats.brainChunks}</span> chunks
                  </span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Value Narrative — accumulated value storytelling */}
        <div className="mb-8">
          <ValueNarrative />
        </div>

        {/* Gamification — Brain XP, Zenya Level, Achievements, Timeline */}
        <div className="mb-8">
          <GamificationPanel />
        </div>

        {/* No services warning */}
        {!hasZenya && !hasTrafego && (
          <div className="glass rounded-2xl p-8 border border-yellow-500/20 text-center">
            <div className="w-12 h-12 rounded-full bg-yellow-500/10 border border-yellow-500/20 flex items-center justify-center mx-auto mb-4">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#eab308" strokeWidth="2">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                <line x1="12" y1="9" x2="12" y2="13"/>
                <line x1="12" y1="17" x2="12.01" y2="17"/>
              </svg>
            </div>
            <p className="text-white font-medium mb-1">Nenhum serviço ativo encontrado</p>
            <p className="text-slate-500 text-sm">Entre em contato com seu consultor Sparkle para mais informações.</p>
          </div>
        )}

        {/* Services */}
        <div className="space-y-10">
          {hasZenya && <DashboardZenya client={client} />}
          {hasTrafego && <DashboardTrafego client={client} />}
        </div>
      </main>

      {/* Footer */}
      <footer className="relative z-10 border-t border-white/5 mt-16 py-6">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 flex items-center justify-center">
          <span className="text-xs text-slate-700">&copy; {new Date().getFullYear()} {client.company}</span>
        </div>
      </footer>
    </div>
  )
}
