'use client'

import { useSearchParams } from 'next/navigation'
import { Suspense } from 'react'

const MSG_MAP: Record<string, { text: string; type: 'error' | 'info' }> = {
  'link-expirado':     { text: 'Este link expirou. Solicite um novo pelo WhatsApp.', type: 'error' },
  'token-invalido':    { text: 'Link inválido. Solicite um novo pelo WhatsApp.', type: 'error' },
  'acesso-negado':     { text: 'Para acessar seu portal, use o link enviado pelo WhatsApp.', type: 'error' },
  'sessao-expirada':   { text: 'Sua sessão expirou. Solicite um novo link pelo WhatsApp.', type: 'info' },
  'erro-autenticacao': { text: 'Não foi possível verificar seu acesso. Tente novamente ou fale com seu consultor Sparkle.', type: 'error' },
}

function LoginContent() {
  const searchParams = useSearchParams()
  const msgKey = searchParams.get('msg') ?? ''
  const notice = MSG_MAP[msgKey] ?? null

  const whatsappUrl = 'https://wa.me/5512982201239?text=Ol%C3%A1%2C%20preciso%20do%20link%20de%20acesso%20ao%20portal%20Sparkle.'

  return (
    <div className="w-full max-w-md mx-auto">
      {/* Logo */}
      <div className="text-center mb-10">
        <div className="inline-flex items-center gap-2 mb-4">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-accent to-accent-light flex items-center justify-center glow-accent">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" fill="white" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <span className="text-xl font-semibold text-white tracking-tight">Sparkle AI</span>
        </div>
        <h1 className="text-3xl font-bold text-white mb-2">Portal do Cliente</h1>
        <p className="text-slate-400 text-sm">
          Seu painel de resultados — acesse pelo link enviado no WhatsApp
        </p>
      </div>

      {/* Card principal */}
      <div className="glass rounded-2xl p-8 border border-white/8 text-center space-y-6">

        {/* Aviso contextual (link expirado, sessão expirada etc.) */}
        {notice && (
          <div className={`flex items-center gap-2 px-4 py-3 rounded-xl text-sm text-left
            ${notice.type === 'error'
              ? 'bg-red-500/10 border border-red-500/20 text-red-400'
              : 'bg-yellow-500/10 border border-yellow-500/20 text-yellow-400'
            }`}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="shrink-0">
              <circle cx="12" cy="12" r="10"/>
              <line x1="12" y1="8" x2="12" y2="12"/>
              <line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            {notice.text}
          </div>
        )}

        {/* Ícone WhatsApp */}
        <div className="flex justify-center">
          <div className="w-16 h-16 rounded-2xl bg-green-500/10 border border-green-500/20 flex items-center justify-center">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" fill="#22c55e"/>
            </svg>
          </div>
        </div>

        {/* Instrução */}
        <div>
          <p className="text-white font-medium text-base mb-2">
            Acesse pelo link enviado no WhatsApp
          </p>
          <p className="text-slate-400 text-sm leading-relaxed">
            Para acessar seu portal, solicite o link de acesso com seu consultor Sparkle pelo WhatsApp.
            O link expira em 30 minutos após o envio.
          </p>
        </div>

        {/* CTA */}
        <a
          href={whatsappUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center justify-center gap-2 w-full py-3 px-6 rounded-xl font-semibold text-sm text-white
                     bg-green-600 hover:bg-green-500 active:scale-[0.98]
                     transition-all duration-200"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="white" xmlns="http://www.w3.org/2000/svg">
            <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
          </svg>
          Solicitar link de acesso
        </a>
      </div>
    </div>
  )
}

export default function LoginForm() {
  return (
    <Suspense fallback={<div className="w-full max-w-md mx-auto h-64 glass rounded-2xl animate-pulse" />}>
      <LoginContent />
    </Suspense>
  )
}
