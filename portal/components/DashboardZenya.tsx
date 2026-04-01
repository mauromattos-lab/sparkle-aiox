'use client'

import Card from './Card'
import type { Client } from '@/lib/supabase'

type Props = {
  client: Client
}

export default function DashboardZenya({ client }: Props) {
  const isActive = client.status === 'active' || client.status === 'ativo'

  // Calcular "Zenya ativa há X dias" a partir de created_at (se disponível)
  const createdAt = client.created_at
  let diasAtiva: number | null = null
  if (createdAt) {
    const diff = Date.now() - new Date(createdAt).getTime()
    diasAtiva = Math.floor(diff / (1000 * 60 * 60 * 24))
  }

  // Próxima segunda-feira
  const hoje = new Date()
  const diasParaSegunda = (8 - hoje.getDay()) % 7 || 7
  const proximaSegunda = new Date(hoje)
  proximaSegunda.setDate(hoje.getDate() + diasParaSegunda)
  const proximaSegundaStr = proximaSegunda.toLocaleDateString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
  })

  return (
    <section>
      {/* Section header */}
      <div className="flex items-center gap-3 mb-6">
        <div className="w-8 h-8 rounded-lg bg-accent/20 border border-accent/30 flex items-center justify-center">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#a855f7" strokeWidth="2">
            <path d="M12 2L2 7l10 5 10-5-10-5z"/>
            <path d="M2 17l10 5 10-5"/>
            <path d="M2 12l10 5 10-5"/>
          </svg>
        </div>
        <div>
          <h2 className="text-base font-semibold text-white">Zenya — Atendimento IA</h2>
          <p className="text-xs text-slate-500">Agente de WhatsApp inteligente</p>
        </div>
        {/* Status badge */}
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

      {/* Card destaque: plano/valor (maior hierarquia visual) */}
      <div className="mb-4">
        <Card
          title="Seu plano"
          value={`R$${client.mrr.toLocaleString('pt-BR')}/mês`}
          subtitle={client.plan}
          accent="cyan"
          highlight
        />
      </div>

      {/* Cards secundários */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
        <Card
          title="Próximo vencimento"
          value={`Dia ${client.due_day}`}
          subtitle="Renovação mensal"
          accent="purple"
        />
        {diasAtiva !== null ? (
          <Card
            title="Zenya ativa há"
            value={`${diasAtiva} dias`}
            subtitle="Atendimento contínuo no WhatsApp"
            accent="green"
          />
        ) : (
          <Card
            title="Próximo relatório"
            value={`Seg, ${proximaSegundaStr}`}
            subtitle="Resumo semanal de atendimentos"
            accent="green"
          />
        )}
      </div>

      {/* Card: canal de contato */}
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
