import type { Metadata } from 'next'
import './globals.css'
import PremiumHeader from '@/components/PremiumHeader'
import PremiumFooter from '@/components/PremiumFooter'

export const metadata: Metadata = {
  title: 'Portal do Cliente — Sparkle AI',
  description: 'Acompanhe seus serviços Sparkle AI em tempo real.',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="pt-BR">
      <body className="bg-background min-h-screen bg-grid antialiased flex flex-col">
        <PremiumHeader />
        <main className="flex-1 pt-14 page-content">
          {children}
        </main>
        <PremiumFooter />
      </body>
    </html>
  )
}
