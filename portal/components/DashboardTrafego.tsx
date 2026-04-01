'use client'

import { useEffect, useState } from 'react'
import Card from './Card'
import type { Client } from '@/lib/supabase'

type Props = { client: Client }

type TrafegoMetrics = {
  investimento_7d: number
  leads_7d: number
  impressoes_7d: number
  ctr_medio: number
  cliques_7d: number
}

export default function DashboardTrafego({ client }: Props) {
  const [metrics, setMetrics] = useState<TrafegoMetrics | null>(null)

  useEffect(() => {
    fetch('/api/metrics/trafego')
      .then(r => r.ok ? r.json() : null)
      .then(d => d && setMetrics(d))
      .catch(() => {})
  }, [])

  const diasAtivo = client.created_at
    ? Math.floor((Date.now() - new Date(client.created_at).getTime()) / (1000 * 60 * 60 * 24))
    : null

  return (
    <section>
      <div className="flex items-center gap-3 mb-6">
        <div className="w-8 h-8 rounded-lg bg-cyan/10 border border-cyan/30 flex items-center justify-center">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#00e5ff" strokeWidth="2">
            <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/>
            <polyline points="17 6 23 6 23 12"/>
          </svg>
        </div>
        <div>
          <h2 className="text-base font-semibold text-white">Tráfego Pago</h2>
          <p className="text-xs text-slate-500">Meta Ads &amp; Google Ads gerenciados</p>
        </div>
        <div className="ml-auto">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-cyan/10 border border-cyan/20 text-cyan">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan animate-pulse"/>
            Campanhas ativas
          </span>
        </div>
      </div>

      <div className="mb-4">
        <Card
          title="Gestão ativa há"
          value={diasAtivo !== null ? `${diasAtivo} dias` : '—'}
          subtitle="Campanhas sendo gerenciadas"
          accent="cyan"
          highlight
        />
      </div>

      {metrics && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
          <Card
            title="Investimento 7 dias"
            value={`R$${metrics.investimento_7d.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
            subtitle="Total gasto no período"
            accent="purple"
          />
          <Card title="Leads gerados" value={String(metrics.leads_7d)} subtitle="Últimos 7 dias" accent="green" />
          <Card title="Impressões" value={metrics.impressoes_7d.toLocaleString('pt-BR')} subtitle="Alcance total" accent="cyan" />
          <Card title="CTR médio" value={`${metrics.ctr_medio}%`} subtitle="Taxa de cliques" accent="purple" />
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
        <Card title="Próximo vencimento" value={`Dia ${client.due_day}`} subtitle="Renovação mensal" accent="purple" />
        {metrics ? (
          <Card title="Cliques" value={String(metrics.cliques_7d)} subtitle="Cliques nos anúncios (7 dias)" accent="green" />
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
        <p className="text-xs text-slate-500 mb-4">Dúvidas sobre suas campanhas ou relatórios — seu consultor responde no WhatsApp.</p>
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
