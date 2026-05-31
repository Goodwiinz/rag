import { cn } from '@/lib/utils';
import {
  Activity,
  BarChart3,
  Cpu,
  FileText,
  HardDrive,
  Layers,
  Zap,
} from 'lucide-react';
import React from 'react';

import { StatsResult } from '../arxivTypes';

interface StatsTabProps {
  stats: StatsResult | null;
  statsError: string;
  isAnyOperationRunning: boolean;
  isStatsLoading: boolean;
  onRefresh: () => void;
}

export function StatsTab({
  stats,
  statsError,
  isAnyOperationRunning,
  isStatsLoading,
  onRefresh,
}: StatsTabProps) {
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="flex items-center gap-2 text-sm font-medium text-foreground">
          <BarChart3 aria-hidden="true" className="h-4 w-4 text-primary" />
          Tracking statistics
        </h3>
        <button
          type="button"
          onClick={onRefresh}
          disabled={isAnyOperationRunning || isStatsLoading}
          className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-muted-foreground transition-colors hover:border-[var(--nous-helios)] hover:text-foreground disabled:cursor-not-allowed disabled:opacity-45 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
        >
          {isStatsLoading ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {statsError && (
        <div
          role="alert"
          className="flex flex-col items-start gap-3 rounded-lg border border-border bg-muted/20 p-4"
        >
          <p className="text-sm text-foreground">
            Couldn&apos;t refresh statistics. {statsError}
          </p>
          <button
            type="button"
            onClick={onRefresh}
            disabled={isAnyOperationRunning || isStatsLoading}
            className="rounded text-sm font-medium text-primary underline-offset-4 hover:underline disabled:cursor-not-allowed disabled:opacity-45 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          >
            Retry
          </button>
        </div>
      )}

      {stats ? (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {[
              {
                label: 'System papers',
                value: stats.statistics.total_papers_tracked,
                icon: FileText,
              },
              {
                label: 'Active papers',
                value: stats.statistics.active_papers,
                icon: Activity,
              },
              {
                label: 'Category clusters',
                value: stats.statistics.categories_tracked,
                icon: Layers,
              },
              {
                label: 'Deleted papers',
                value: stats.statistics.deleted_papers,
                icon: Zap,
              },
            ].map((item) => (
              <div
                key={item.label}
                className="rounded-xl border border-border bg-card p-5 shadow-sm"
              >
                <div className="mb-3 w-fit rounded-lg bg-muted p-2 text-primary">
                  <item.icon aria-hidden="true" className="h-4 w-4" />
                </div>
                <div className="text-2xl font-semibold text-foreground tabular-nums">
                  {item.value}
                </div>
                <div className="mt-1 text-xs text-muted-foreground">
                  {item.label}
                </div>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
            <div className="rounded-xl border border-border bg-card p-5 shadow-sm xl:col-span-8">
              <div className="mb-5 flex items-center gap-2">
                <Cpu aria-hidden="true" className="h-4 w-4 text-primary" />
                <h4 className="text-sm font-medium text-foreground">
                  Category distribution
                </h4>
              </div>

              {stats.statistics.top_categories &&
              stats.statistics.top_categories.length > 0 ? (
                <div className="space-y-3">
                  {stats.statistics.top_categories.map(([category, count]) => (
                    <div key={category} className="space-y-1.5">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-[var(--nous-font-mono)] text-muted-foreground">
                          {category}
                        </span>
                        <span className="font-medium text-foreground tabular-nums">
                          {count}
                        </span>
                      </div>
                      <div
                        className="h-1.5 w-full overflow-hidden rounded-full bg-border"
                        role="progressbar"
                        aria-valuenow={count}
                        aria-valuemin={0}
                        aria-valuemax={Math.max(
                          stats.statistics.total_papers_tracked,
                          count
                        )}
                        aria-label={`${category} paper count`}
                      >
                        <div
                          className="h-full rounded-full bg-primary"
                          style={{
                            width: `${(count / Math.max(stats.statistics.total_papers_tracked, 1)) * 100}%`,
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  No category data tracked yet. Run a change scan to populate
                  this view.
                </p>
              )}
            </div>

            <div className="flex flex-col gap-3 rounded-xl border border-border bg-card p-5 shadow-sm xl:col-span-4">
              <div className="flex items-center gap-2">
                <HardDrive
                  aria-hidden="true"
                  className="h-4 w-4 text-muted-foreground"
                />
                <h4 className="text-sm font-medium text-foreground">
                  Tracker state
                </h4>
              </div>
              <p className="text-sm leading-relaxed text-muted-foreground">
                Tracking metrics are read from the corpus state file on each
                refresh.
              </p>
              <div className="mt-auto">
                <div className="text-xs text-muted-foreground">State file</div>
                <div className="mt-1 break-all font-[var(--nous-font-mono)] text-xs text-foreground">
                  {stats.statistics.state_file_path}
                </div>
              </div>
            </div>
          </div>
        </>
      ) : isStatsLoading ? (
        <div
          role="status"
          aria-live="polite"
          className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4"
        >
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className="rounded-xl border border-border bg-card p-5 shadow-sm"
            >
              <div className="mb-3 h-8 w-8 animate-pulse rounded-lg bg-muted" />
              <div className="h-7 w-12 animate-pulse rounded bg-muted" />
              <div className="mt-2 h-3 w-20 animate-pulse rounded bg-muted" />
            </div>
          ))}
          <span className="sr-only">Loading statistics…</span>
        </div>
      ) : (
        !statsError && (
          <div className="rounded-xl border border-border bg-card p-8 text-center shadow-sm">
            <div className="mx-auto mb-3 w-fit rounded-lg bg-muted p-3 text-muted-foreground">
              <BarChart3 aria-hidden="true" className="h-5 w-5" />
            </div>
            <p className="text-sm font-medium text-foreground">
              No statistics yet
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              Statistics populate once the tracker has scanned the corpus.
            </p>
          </div>
        )
      )}
    </div>
  );
}
