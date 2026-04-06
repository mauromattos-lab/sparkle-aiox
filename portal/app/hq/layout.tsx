/**
 * HQ Layout — workstation layout for Mauro.
 *
 * Structure:
 *   ┌──────────┬──────────────────────────────┬─────────────┐
 *   │          │       Header (56px)           │             │
 *   │ Sidebar  ├──────────────────────────────┤  Detail     │
 *   │  64/240px│       Main content           │  Panel      │
 *   │          │       (children)             │  (380px)    │
 *   └──────────┴──────────────────────────────┴─────────────┘
 *
 * - Route group (hq)/ — completely isolated from /dashboard
 * - No auth check here — Story 1.2 will add middleware for /hq/*
 * - SidebarController is a client component; layout.tsx itself stays server
 */
import type { Metadata } from 'next'
import SidebarController from '@/components/hq/SidebarController'
import DetailPanel from '@/components/hq/DetailPanel'
import { DetailPanelProvider } from '@/components/hq/DetailPanelContext'

export const metadata: Metadata = {
  title: 'Portal HQ — Sparkle',
  description: 'Workstation do fundador — Sparkle AIOX',
}

export default function HQLayout({ children }: { children: React.ReactNode }) {
  return (
    <DetailPanelProvider>
      <SidebarController>
        {/* Main + DetailPanel side by side */}
        <div className="flex flex-1 overflow-hidden min-h-0">
          {/* Main content area */}
          <main
            className="flex-1 overflow-auto p-4 min-w-0"
            id="hq-main"
            role="main"
          >
            {children}
          </main>

          {/* Detail Panel — push on >= 1440px (xl), overlay on smaller */}
          <DetailPanel />
        </div>
      </SidebarController>
    </DetailPanelProvider>
  )
}
