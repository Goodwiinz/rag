import { cn } from '@/lib/utils';
import {
  Activity,
  BarChart3,
  Cpu,
  FileText,
  Globe,
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
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="flex items-center gap-2 text-sm font-mono font-bold uppercase tracking-tight text-foreground">
          <BarChart3
            className="h-4 w-4 text-[var(--cyan)]"
            aria-hidden="true"
          />
          System Statistics
        </h3>
        <button
          type="button"
          onClick={onRefresh}
          disabled={isAnyOperationRunning || isStatsLoading}
          className="rounded-lg border border-[var(--terminal-border)] px-4 py-2 text-[11px] font-mono font-bold uppercase text-muted-foreground hover:bg-[var(--terminal-surface)] disabled:cursor-not-allowed disabled:opacity-45"
        >
          Refresh
        </button>
      </div>

      {statsError && (
        <div className="rounded-lg border border-red-900 bg-red-950/70 p-3 text-[10px] font-mono text-red-300">
          Unable to refresh stats: {statsError}
        </div>
      )}

      {stats ? (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {[
              {
                label: 'System Papers',
                value: stats.statistics.total_papers_tracked,
                color: 'text-foreground',
                icon: FileText,
              },
              {
                label: 'Active Papers',
                value: stats.statistics.active_papers,
                color: 'text-primary',
                icon: Activity,
              },
              {
                label: 'Category Clusters',
                value: stats.statistics.categories_tracked,
                color: 'text-[var(--cyan)]',
                icon: Layers,
              },
              {
                label: 'Deleted Papers',
                value: stats.statistics.deleted_papers,
                color: 'text-[var(--amber-gold)]',
                icon: Zap,
              },
            ].map((item) => (
              <div
                key={item.label}
                className="relative overflow-hidden rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-bg)]/50 p-5"
              >
                <item.icon
                  className="absolute -right-2 -top-2 h-14 w-14 text-[var(--terminal-border)] opacity-25"
                  aria-hidden="true"
                />
                <div className={cn('text-2xl font-mono font-bold', item.color)}>
                  {item.value}
                </div>
                <div className="mt-1 text-[9px] font-mono uppercase tracking-widest text-muted-foreground">
                  {item.label}
                </div>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
            <div className="rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-bg)]/50 p-5 xl:col-span-8">
              <div className="mb-5 flex items-center gap-2">
                <Cpu className="h-4 w-4 text-primary" aria-hidden="true" />
                <h4 className="text-xs font-mono font-bold uppercase tracking-widest text-foreground">
                  Category Distribution
                </h4>
              </div>

              <div className="space-y-3">
                {stats.statistics.top_categories?.map(([category, count]) => (
                  <div key={category} className="space-y-1.5">
                    <div className="flex items-center justify-between text-[10px] font-mono uppercase">
                      <span className="text-muted-foreground">{category}</span>
                      <span className="font-bold text-primary">{count}</span>
                    </div>
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--terminal-border)]">
                      <div
                        className="h-full rounded-full bg-primary/40"
                        style={{
                          width: `${(count / Math.max(stats.statistics.total_papers_tracked, 1)) * 100}%`,
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-bg)]/50 p-5 xl:col-span-4">
              <Globe
                className="h-10 w-10 text-[var(--terminal-border)]"
                aria-hidden="true"
              />
              <p className="text-center text-[10px] font-mono uppercase tracking-[0.25em] text-muted-foreground">
                Grid Status Active
              </p>
              <p className="text-center text-[10px] font-mono text-muted-foreground">
                Synchronization latency: optimal
              </p>
              <p className="text-center text-[9px] font-mono text-muted-foreground">
                State file: {stats.statistics.state_file_path}
              </p>
            </div>
          </div>
        </>
      ) : (
        <div className="rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-bg)]/50 p-6 text-center text-[11px] font-mono text-muted-foreground">
          Statistics are unavailable right now.
        </div>
      )}
    </div>
  );
}
