'use client'

import { useEffect, useState } from 'react'
import Card from './Card'
import type { Client } from '@/lib/supabase'

type Props = { client: Client }

type ZenyaMetrics = {
  total_mes: number
  hoje: number
  taxa_resolucao: number
  conversoes: number
  satisfacao: number
}

export default function DashboardZenya({ client }: Props) {
  const [metrics, setMetrics] = useState<ZenyaMetrics | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 8000)
    fetch('/api/metrics/zenya', { signal: controller.signal })
      .then(r => r.ok ? r.json() : null)
      .then(d => d && setMetrics(d))
      .catch(() => {})
      .finally(() => clearTimeout(timeout))
  }, [])

  const isActive = client.status === 'active' || client.status === 'ativo'
  const diasAtiva = client.created_at
    ? Math.floor((Date.now() - new Date(client.created_at).getTime()) / (1000 * 60 * 60 * 24))
    : null

  return (
    <section>
      <div className="flex items-center gap-3 mb-6">
        <div className="w-8 h-8 rounded-lg overflow-hidden border border-accent/30">
          <img src="/zenya.png" alt="Zenya" className="w-full h-full object-cover" />
        </div>
        <div>
          <h2 className="text-base font-semibold text-white">Zenya — Atendimento IA</h2>
          <p className="text-xs text-slate-500">Agente de WhatsApp inteligente</p>
        </div>
        <div className="ml-auto">
          {isActive ? (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"/>
              Zenya ativa
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-yellow-500/10 border border-yellow-500/20 text-yellow-400">
              <span className="w-1.5 h-1.5 rounded-full bg-yellow-400"/>
              Configurando
            </span>
          )}
        </div>
      </div>

      <div className="mb-4">
        <Card
          title="Zenya ativa há"
          value={diasAtiva !== null ? `${diasAtiva} dias` : '—'}
          subtitle="Atendimento contínuo no WhatsApp"
          accent="cyan"
          highlight
        />
      </div>

      {metrics && (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <Card title="Conversas este mês" value={String(metrics.total_mes)} subtitle="Total de atendimentos" accent="purple" />
          <Card title="Hoje" value={String(metrics.hoje)} subtitle="Conversas iniciadas" accent="cyan" />
          <Card title="Taxa de resolução" value={`${metrics.taxa_resolucao}%`} subtitle="Resolvidos pela Zenya" accent="green" />
          <Card title="Conversões" value={String(metrics.conversoes)} subtitle="Leads convertidos" accent="purple" />
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
        <Card title="Próximo vencimento" value={`Dia ${client.due_day}`} subtitle="Renovação mensal" accent="purple" />
        {metrics ? (
          <Card title="Satisfação" value={`${metrics.satisfacao}%`} subtitle="Conversas com sentimento positivo" accent="green" />
        ) : (
          <Card title="Plano" value={`R$${client.mrr.toLocaleString('pt-BR')}/mês`} subtitle={client.plan} accent="green" />
        )}
      </div>

      <div className="glass rounded-2xl p-5 border border-white/8">
        <div className="flex items-center gap-2 mb-3">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#25d366" strokeWidth="2">
            <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>
          </svg>
          <h3 className="text-sm font-medium text-slate-300">Fale com a Sparkle</h3>
        </div>
        <p className="text-xs text-slate-500 mb-4">Dúvidas, ajustes ou suporte — seu consultor responde no WhatsApp.</p>
        <a
          href="https://wa.me/5512981303249"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium
                     bg-emerald-500/10 border border-emerald-500/20 text-emerald-400
                     hover:bg-emerald-500/20 transition-all duration-200"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>
          </svg>
          Abrir WhatsApp
        </a>
      </div>
    </section>
  )
}
