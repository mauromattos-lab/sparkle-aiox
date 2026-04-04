import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Login — Sparkle AIOX',
  description: 'Acesse seu cockpit de IA personalizada.',
}

/**
 * Layout exclusivo para /login — esconde PremiumHeader/Footer do root layout
 * e remove o padding-top que o root layout aplica na <main>.
 * Usa CSS inline para sobrescrever sem afetar outras rotas.
 */
export default function LoginLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <>
      {/* Hide root layout header/footer and reset padding for full-screen login */}
      <style>{`
        header { display: none !important; }
        footer { display: none !important; }
        main.page-content { padding-top: 0 !important; }
      `}</style>
      <div className="min-h-screen bg-background flex flex-col">
        {children}
      </div>
    </>
  )
}
