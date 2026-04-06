'use client'

/**
 * WorkflowStepsBar — visual progress bar for AIOS pipeline steps.
 * Story 3.2 — AC6
 *
 * Steps: prd_approved → spec_approved → stories_ready → dev_complete →
 *        qa_approved → po_accepted → devops_deployed → done
 *
 * Visual states:
 * - Completed: CheckCircle (green-400)
 * - Current:   Circle with animate-pulse (yellow-400)
 * - Future:    Circle (white/30)
 */

import React from 'react'
import { CheckCircle2, Circle } from 'lucide-react'

export const PIPELINE_STEPS = [
  'prd_approved',
  'spec_approved',
  'stories_ready',
  'dev_complete',
  'qa_approved',
  'po_accepted',
  'devops_deployed',
  'done',
] as const

export type PipelineStep = typeof PIPELINE_STEPS[number]

const STEP_LABELS: Record<string, string> = {
  prd_approved: 'PRD',
  spec_approved: 'Spec',
  stories_ready: 'Stories',
  dev_complete: 'Dev',
  qa_approved: 'QA',
  po_accepted: 'PO',
  devops_deployed: 'Deploy',
  done: 'Done',
}

export interface WorkflowStepsBarProps {
  currentStep: string
  compact?: boolean
}

export default function WorkflowStepsBar({ currentStep, compact = false }: WorkflowStepsBarProps) {
  const currentIndex = PIPELINE_STEPS.indexOf(currentStep as PipelineStep)
  // If step not found, treat as step 0 (before anything)
  const activeIndex = currentIndex === -1 ? 0 : currentIndex

  if (compact) {
    // In compact mode: just render "step N / total" text (used in list rows per AC note)
    return (
      <span className="text-[0.6875rem] font-mono text-white/40">
        {activeIndex + 1} / {PIPELINE_STEPS.length}
      </span>
    )
  }

  return (
    <div className="flex items-start w-full" role="progressbar" aria-label={`Pipeline step: ${STEP_LABELS[currentStep] ?? currentStep}`}>
      {PIPELINE_STEPS.map((step, idx) => {
        const isCompleted = idx < activeIndex
        const isCurrent = idx === activeIndex
        const label = STEP_LABELS[step] ?? step

        return (
          <React.Fragment key={step}>
            {/* Step node */}
            <div className="flex flex-col items-center gap-1 flex-shrink-0">
              {isCompleted ? (
                <CheckCircle2
                  size={16}
                  className="text-green-400"
                  strokeWidth={1.75}
                  aria-label={`${label} concluido`}
                />
              ) : isCurrent ? (
                <Circle
                  size={16}
                  className="text-yellow-400 animate-pulse"
                  strokeWidth={1.75}
                  aria-label={`${label} em andamento`}
                />
              ) : (
                <Circle
                  size={16}
                  className="text-white/30 opacity-30"
                  strokeWidth={1.75}
                  aria-label={`${label} pendente`}
                />
              )}
              <span
                className={`text-[0.5625rem] leading-tight whitespace-nowrap ${
                  isCompleted
                    ? 'text-green-400/70'
                    : isCurrent
                    ? 'text-yellow-400/80'
                    : 'text-white/25'
                }`}
              >
                {label}
              </span>
            </div>

            {/* Connector line between steps */}
            {idx < PIPELINE_STEPS.length - 1 && (
              <div
                className={`flex-1 border-t mt-2 ${
                  idx < activeIndex ? 'border-green-400/30' : 'border-white/[0.10]'
                }`}
                aria-hidden="true"
              />
            )}
          </React.Fragment>
        )
      })}
    </div>
  )
}
