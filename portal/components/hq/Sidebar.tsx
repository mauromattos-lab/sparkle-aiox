'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard,
  Filter,
  Users,
  Bot,
  GitBranch,
  Brain,
  Sparkles,
  Settings,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'

interface NavItem {
  icon: React.ElementType
  label: string
  href: string
}

const NAV_ITEMS: NavItem[] = [
  { icon: LayoutDashboard, label: 'Command Center', href: '/hq' },
  { icon: Filter,          label: 'Pipeline',       href: '/hq/pipeline' },
  { icon: Users,           label: 'Clientes',       href: '/hq/clients' },
  { icon: Bot,             label: 'Agentes',        href: '/hq/agents' },
  { icon: GitBranch,       label: 'Workflows',      href: '/hq/workflows' },
  { icon: Brain,           label: 'Brain',          href: '/hq/brain' },
  { icon: Sparkles,        label: 'Conteúdo',       href: '/hq/content' },
  { icon: Settings,        label: 'Settings',       href: '/hq/settings' },
]

interface SidebarProps {
  collapsed: boolean
  onToggle: () => void
}

export default function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const pathname = usePathname()

  const isActive = (href: string) => {
    if (href === '/hq') {
      return pathname === '/hq' || pathname === '/hq/'
    }
    return pathname.startsWith(href)
  }

  return (
    <aside
      className="relative flex flex-col h-full bg-[#020208] border-r border-white/[0.08] transition-all duration-200 ease-in-out flex-shrink-0"
      style={{ width: collapsed ? 64 : 240 }}
      aria-label="Main navigation"
    >
      {/* Gradient top accent line */}
      <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-purple-500/40 to-transparent" />

      {/* Nav items */}
      <nav className="flex-1 overflow-hidden py-4 mt-2" role="navigation">
        <ul className="space-y-1 px-2" role="list">
          {NAV_ITEMS.map((item) => {
            const active = isActive(item.href)
            const Icon = item.icon

            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={[
                    'flex items-center gap-3 rounded-lg transition-all duration-150 group focus:outline-none focus-visible:ring-2 focus-visible:ring-purple-500',
                    collapsed ? 'justify-center px-0 py-2.5 mx-0' : 'px-3 py-2.5',
                    active
                      ? 'hq-nav-active'
                      : 'text-white/50 hover:bg-white/[0.06] hover:text-white/80',
                  ].join(' ')}
                  title={collapsed ? item.label : undefined}
                  aria-current={active ? 'page' : undefined}
                >
                  <Icon
                    size={18}
                    className={[
                      'flex-shrink-0 transition-colors duration-150',
                      active ? 'text-purple-400' : 'text-white/40 group-hover:text-white/70',
                    ].join(' ')}
                    strokeWidth={1.75}
                  />
                  {!collapsed && (
                    <span
                      className={[
                        'text-[0.8125rem] font-medium truncate transition-colors duration-150',
                        active ? 'text-purple-300' : 'text-white/50 group-hover:text-white/80',
                      ].join(' ')}
                    >
                      {item.label}
                    </span>
                  )}
                </Link>
              </li>
            )
          })}
        </ul>
      </nav>

      {/* Collapse toggle button at bottom */}
      <div className="p-2 border-t border-white/[0.06]">
        <button
          onClick={onToggle}
          className={[
            'flex items-center gap-2 w-full rounded-lg py-2 text-white/30 hover:text-white/60 hover:bg-white/[0.05] transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-purple-500',
            collapsed ? 'justify-center px-0' : 'px-3',
          ].join(' ')}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? (
            <ChevronRight size={16} strokeWidth={1.75} />
          ) : (
            <>
              <ChevronLeft size={16} strokeWidth={1.75} />
              <span className="text-xs">Recolher</span>
            </>
          )}
        </button>
      </div>
    </aside>
  )
}
