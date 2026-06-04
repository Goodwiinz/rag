import { AlertCircle, BarChart3 } from 'lucide-react';
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
        <h3 className="flex items-center gap-2 text-base font-semibold text-foreground">
          <BarChart3 className="h-4 w-4 text-primary" aria-hidden="true" />
          Tracking statistics
        </h3>
        <button
          type="button"
          onClick={onRefresh}
          disabled={isAnyOperationRunning || isStatsLoading}
          className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40 focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-45"
        >
          Refresh
        </button>
      </div>

      {statsError && (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-lg border border-[var(--nous-mars)]/30 bg-[var(--nous-mars)]/10 p-3 text-sm text-[var(--nous-mars)]"
        >
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>Could not refresh statistics. {statsError}</span>
        </div>
      )}

      {stats ? (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
          <div className="rounded-xl border border-border bg-card p-6 xl:col-span-4">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Papers tracked
            </p>
            <p className="mt-2 text-4xl font-semibold tabular-nums text-foreground">
              {stats.statistics.total_papers_tracked}
            </p>
            <dl className="mt-5 space-y-3 border-t border-border pt-5">
              <div className="flex items-center justify-between">
                <dt className="text-sm text-muted-foreground">Active</dt>
                <dd className="text-sm font-medium tabular-nums text-foreground">
                  {stats.statistics.active_papers}
                </dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-sm text-muted-foreground">Deleted</dt>
                <dd className="text-sm font-medium tabular-nums text-foreground">
                  {stats.statistics.deleted_papers}
                </dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-sm text-muted-foreground">
                  Categories tracked
                </dt>
                <dd className="text-sm font-medium tabular-nums text-foreground">
                  {stats.statistics.categories_tracked}
                </dd>
              </div>
            </dl>
          </div>

          <div className="rounded-xl border border-border bg-card p-6 xl:col-span-8">
            <h4 className="text-sm font-medium text-foreground">
              Top categories
            </h4>
            {stats.statistics.top_categories &&
            stats.statistics.top_categories.length > 0 ? (
              <div className="mt-5 space-y-3">
                {stats.statistics.top_categories.map(([category, count]) => (
                  <div key={category} className="space-y-1.5">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-foreground">{category}</span>
                      <span className="font-medium tabular-nums text-muted-foreground">
                        {count}
                      </span>
                    </div>
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
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
              <p className="mt-5 text-sm text-muted-foreground">
                No category breakdown yet. Run a change scan to populate it.
              </p>
            )}
          </div>
        </div>
      ) : (
        <div className="rounded-xl border border-border bg-card p-8 text-center text-sm text-muted-foreground">
          {isStatsLoading
            ? 'Loading statistics…'
            : 'Statistics are unavailable right now.'}
        </div>
      )}
    </div>
  );
}
