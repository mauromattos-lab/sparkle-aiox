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

/** Skeleton for pipeline kanban — AC10: 6 columns, 3 cards each */
export function PipelineSkeleton() {
  return (
    <div
      className="grid gap-3 flex-1 min-h-0"
      style={{ gridTemplateColumns: 'repeat(6, minmax(220px, 1fr))' }}
      aria-label="Loading pipeline"
    >
      {Array.from({ length: 6 }).map((_, col) => (
        <div key={col} className="flex flex-col gap-2 min-w-[220px]">
          {/* Column header skeleton */}
          <div className="glass rounded-lg px-3 py-2 flex items-center justify-between">
            <SkeletonBox className="h-3 w-20" />
            <SkeletonBox className="h-4 w-6 rounded-full" />
          </div>
          {/* Card skeletons */}
          {Array.from({ length: 3 }).map((_, card) => (
            <div key={card} className="glass rounded-lg p-3 flex flex-col gap-2 min-h-[80px]">
              <div className="flex items-center justify-between">
                <SkeletonBox className="h-3 w-24" />
                <SkeletonBox className="h-4 w-4 rounded-full" />
              </div>
              <SkeletonBox className="h-2.5 w-16" />
              <SkeletonBox className="h-2 w-20" />
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}

/** Skeleton for a single client card */
export function ClientCardSkeleton() {
  return (
    <div className="bg-white/[0.04] backdrop-blur-xl border border-white/10 rounded-lg p-3 flex flex-col gap-2 min-h-[120px]">
      <div className="flex items-start justify-between">
        <div className="flex flex-col gap-1.5 flex-1">
          <SkeletonBox className="h-3 w-24" />
          <SkeletonBox className="h-2.5 w-16" />
        </div>
        <SkeletonBox className="h-4 w-12" />
      </div>
      <div className="flex gap-1.5">
        <SkeletonBox className="h-4 w-14 rounded" />
        <SkeletonBox className="h-4 w-12 rounded" />
      </div>
      <div className="flex items-center justify-between mt-auto pt-1 border-t border-white/[0.04]">
        <SkeletonBox className="h-3 w-20" />
        <SkeletonBox className="h-2.5 w-12" />
      </div>
    </div>
  )
}

/** Skeleton for the clients grid (6 cards) — AC12 */
export function ClientsSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div
      className="grid gap-3"
      style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))' }}
      aria-label="Loading clients"
    >
      {Array.from({ length: count }).map((_, i) => (
        <ClientCardSkeleton key={i} />
      ))}
    </div>
  )
}

/** Skeleton for workflow list — AC10 */
export function WorkflowListSkeleton({ lines = 5 }: { lines?: number }) {
  return (
    <div className="flex flex-col divide-y divide-white/[0.04]" aria-label="Loading workflows">
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="flex items-center gap-3 py-3 px-3 min-h-[52px]">
          <SkeletonBox className="h-4 w-4 rounded-full shrink-0" />
          <div className="flex flex-col gap-1.5 flex-1">
            <SkeletonBox className="h-3 w-32" />
            <SkeletonBox className="h-2 w-20" />
          </div>
          <SkeletonBox className="h-4 w-20 rounded-full" />
          <SkeletonBox className="h-3 w-14" />
        </div>
      ))}
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

/** Skeleton for Brain view (Story 3.3) — AC10 */
export function BrainSkeleton() {
  return (
    <div className="flex flex-col gap-4" aria-label="Loading Brain view">
      {/* 4 KPI cards */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="bg-white/[0.04] backdrop-blur-xl border border-white/10 rounded-lg p-3 flex flex-col gap-2 min-h-[80px]"
          >
            <SkeletonBox className="h-3 w-20" />
            <SkeletonBox className="h-7 w-12" />
          </div>
        ))}
      </div>
      {/* 3 namespace card placeholders */}
      <div
        className="grid gap-3"
        style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))' }}
      >
        {Array.from({ length: 3 }).map((_, i) => (
          <div
            key={i}
            className="bg-white/[0.04] backdrop-blur-xl border border-white/10 rounded-lg p-4 flex flex-col gap-2"
            style={{ minHeight: 120 }}
          >
            <div className="flex justify-between">
              <SkeletonBox className="h-3 w-24" />
              <SkeletonBox className="h-5 w-8" />
            </div>
            <SkeletonBox className="h-1.5 w-full rounded-full" />
            <SkeletonBox className="h-2.5 w-32" />
          </div>
        ))}
      </div>
      {/* 5 table row placeholders */}
      <div className="flex flex-col gap-1.5">
        {Array.from({ length: 5 }).map((_, i) => (
          <SkeletonBox key={i} className="h-9 w-full rounded" />
        ))}
      </div>
    </div>
  )
}
