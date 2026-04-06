'use client'

/**
 * AgentCardSkeleton — shimmer placeholder for AgentCard.
 * Story 3.1 — AC9
 *
 * Uses hq-skeleton class (shimmer via CSS in globals.css).
 * Simulates card layout: icon 40x40 + name line + role line + status + task line.
 */

import React from 'react'
import { SkeletonBox } from '@/components/hq/LoadingSkeleton'

export default function AgentCardSkeleton() {
  return (
    <div
      className="bg-white/[0.04] backdrop-blur-xl border border-white/[0.08] rounded-xl p-4 flex flex-col gap-3 min-h-[120px]"
      aria-hidden="true"
    >
      {/* Top row: icon + name + status */}
      <div className="flex items-start gap-3">
        {/* Icon placeholder 40x40 */}
        <SkeletonBox className="w-10 h-10 rounded-lg flex-shrink-0" />

        {/* Name + type lines */}
        <div className="flex flex-col gap-1.5 flex-1">
          <SkeletonBox className="h-3 w-28" />
          <SkeletonBox className="h-2.5 w-16" />
        </div>

        {/* Status bullet */}
        <SkeletonBox className="w-2 h-2 rounded-full flex-shrink-0 mt-1" />
      </div>

      {/* Task line */}
      <SkeletonBox className="h-2.5 w-48 max-w-full" />

      {/* Bottom row: capabilities + badge */}
      <div className="flex items-center justify-between mt-auto">
        <SkeletonBox className="h-2 w-20" />
        <SkeletonBox className="h-4 w-16 rounded" />
      </div>
    </div>
  )
}
