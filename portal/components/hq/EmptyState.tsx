import { type LucideIcon } from 'lucide-react'

interface EmptyStateProps {
  icon: LucideIcon
  title: string
  description?: string
}

/**
 * EmptyState — reusable placeholder for routes not yet implemented.
 * Used by all /hq/* placeholder pages.
 */
export default function EmptyState({ icon: Icon, title, description }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center flex-1 min-h-0 py-20 px-6 text-center">
      <div className="mb-6">
        <Icon
          size={64}
          className="text-white/20 mx-auto"
          strokeWidth={1}
          aria-hidden="true"
        />
      </div>
      <h1 className="text-lg font-semibold text-white/50 mb-2">{title}</h1>
      {description && (
        <p className="text-sm text-white/30 max-w-xs leading-relaxed">{description}</p>
      )}
    </div>
  )
}
