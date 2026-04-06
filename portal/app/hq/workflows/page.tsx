import { GitBranch } from 'lucide-react'
import EmptyState from '@/components/hq/EmptyState'

export default function WorkflowsPage() {
  return (
    <div className="hq-page-enter hq-density flex flex-col gap-4 h-full">
      <div className="flex items-center gap-3">
        <GitBranch size={20} className="text-purple-400" strokeWidth={1.75} aria-hidden="true" />
        <div>
          <h1 className="text-[0.9375rem] font-semibold text-white/80 leading-tight">Workflows</h1>
          <p className="text-[0.6875rem] text-white/30 font-mono mt-0.5">/hq/workflows</p>
        </div>
      </div>
      <EmptyState
        icon={GitBranch}
        title="Visualizacao de Workflows"
        description="Em desenvolvimento — Sprint 3 Story 3.2"
      />
    </div>
  )
}
