'use client'

/**
 * LoadingSkeleton — reusable shimmer placeholders.
 * AC15: same dimensions as final components, no CLS.
 */

import React from 'react'

interface SkeletonBoxProps {
  className?: string
}

export function SkeletonBox({ className = '' }: SkeletonBoxProps) {
  return <div className={`hq-skeleton rounded ${className}`} aria-hidden="true" />
}

/** Skeleton for a single KPI card */
export function KPICardSkeleton() {
  return (
    <div className="glass rounded-xl p-3 flex flex-col gap-2 min-h-[80px]">
      <SkeletonBox className="h-3 w-16" />
      <SkeletonBox className="h-6 w-20" />
      <SkeletonBox className="h-2 w-10" />
    </div>
  )
}

/** Skeleton for the 4-card KPI row */
export function KPIRowSkeleton() {
  return (
    <div className="grid grid-cols-2 xl:grid-cols-4 gap-3" aria-label="Loading KPI cards">
      {Array.from({ length: 4 }).map((_, i) => (
        <KPICardSkeleton key={i} />
      ))}
    </div>
  )
}

/** Skeleton for a single activity feed item */
export function ActivityItemSkeleton() {
  return (
    <div className="flex gap-2 items-start py-2 px-2 min-h-[48px]">
      <SkeletonBox className="h-4 w-4 rounded-full shrink-0 mt-0.5" />
      <div className="flex flex-col gap-1 flex-1">
        <SkeletonBox className="h-2 w-12" />
        <SkeletonBox className="h-3 w-full max-w-[200px]" />
      </div>
    </div>
  )
}

/** Skeleton for the activity feed panel */
export function ActivityFeedSkeleton({ lines = 8 }: { lines?: number }) {
  return (
    <div className="flex flex-col divide-y divide-white/[0.04]" aria-label="Loading activity feed">
      {Array.from({ length: lines }).map((_, i) => (
        <ActivityItemSkeleton key={i} />
      ))}
    </div>
  )
}

/** Skeleton for system health bar */
export function SystemHealthSkeleton() {
  return (
    <div className="glass rounded-xl p-3 flex items-center gap-4" aria-label="Loading system health">
      <SkeletonBox className="h-3 w-20" />
      <div className="flex gap-4 flex-1">
        {Array.from({ length: 4 }).map((_, i) => (
          <SkeletonBox key={i} className="h-3 w-16" />
        ))}
      </div>
    </div>
  )
}

/** Skeleton for the decisions pending section */
export function DecisionsSkeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="flex flex-col gap-2" aria-label="Loading decisions">
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="glass rounded-lg p-3 flex gap-2 items-start min-h-[56px]">
          <SkeletonBox className="h-4 w-4 rounded-full shrink-0 mt-0.5" />
          <div className="flex flex-col gap-1.5 flex-1">
            <SkeletonBox className="h-3 w-32" />
            <SkeletonBox className="h-2 w-48" />
          </div>
        </div>
      ))}
    </div>
  )
}
