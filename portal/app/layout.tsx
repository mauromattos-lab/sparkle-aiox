import type { Metadata } from 'next'
import './globals.css'

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
      <body className="bg-background min-h-screen bg-grid antialiased">
        {children}
      </body>
    </html>
  )
}
