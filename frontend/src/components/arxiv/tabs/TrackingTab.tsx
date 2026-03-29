import { cn } from '@/lib/utils';
import { Loader2, RefreshCw, Sparkles, Terminal } from 'lucide-react';
import React from 'react';

import { CustomSlider, ToggleSwitch } from '../arxivControls';
import { TrackResult } from '../arxivTypes';

interface TrackingTabProps {
  selectedCategories: string[];
  daysBack: number;
  updateDatabase: boolean;
  popularCategories: string[];
  isAnyOperationRunning: boolean;
  isTracking: boolean;
  isStatsLoading: boolean;
  trackingResult: TrackResult | null;
  onApplyCategoryPreset: (preset: 'core' | 'all' | 'clear') => void;
  onToggleCategory: (category: string) => void;
  onDaysBackChange: (value: number) => void;
  onUpdateDatabaseChange: (checked: boolean) => void;
  onTrackChanges: () => void;
  onRefreshMetrics: () => void;
}

export function TrackingTab({
  selectedCategories,
  daysBack,
  updateDatabase,
  popularCategories,
  isAnyOperationRunning,
  isTracking,
  isStatsLoading,
  trackingResult,
  onApplyCategoryPreset,
  onToggleCategory,
  onDaysBackChange,
  onUpdateDatabaseChange,
  onTrackChanges,
  onRefreshMetrics,
}: TrackingTabProps) {
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1 rounded-md border border-[var(--terminal-border)] bg-[var(--terminal-bg)]/50 px-2 py-1 text-[9px] font-mono uppercase tracking-wider text-muted-foreground">
          <Sparkles className="h-3 w-3 text-[var(--amber-gold)]" />
          Track New and Updated Papers
        </span>
        <span className="inline-flex items-center rounded-md border border-[var(--terminal-border)] bg-[var(--terminal-bg)]/50 px-2 py-1 text-[9px] font-mono uppercase tracking-wider text-muted-foreground">
          {selectedCategories.length} categories selected
        </span>
        <span className="inline-flex items-center rounded-md border border-[var(--terminal-border)] bg-[var(--terminal-bg)]/50 px-2 py-1 text-[9px] font-mono uppercase tracking-wider text-muted-foreground">
          {daysBack} day depth
        </span>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-12">
        <div className="space-y-5 xl:col-span-5">
          <div className="space-y-4 rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-bg)]/50 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-[10px] font-mono font-bold uppercase tracking-widest text-muted-foreground">
                Category Filter
              </h3>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => onApplyCategoryPreset('core')}
                  className="rounded-md border border-primary/25 px-2 py-1 text-[9px] font-mono uppercase tracking-wide text-primary hover:bg-primary/10"
                >
                  Core AI
                </button>
                <button
                  type="button"
                  onClick={() => onApplyCategoryPreset('all')}
                  className="rounded-md border border-[var(--terminal-border)] px-2 py-1 text-[9px] font-mono uppercase tracking-wide text-muted-foreground hover:bg-[var(--terminal-surface)]"
                >
                  Select All
                </button>
                <button
                  type="button"
                  onClick={() => onApplyCategoryPreset('clear')}
                  className="rounded-md border border-[var(--terminal-border)] px-2 py-1 text-[9px] font-mono uppercase tracking-wide text-muted-foreground hover:bg-[var(--terminal-surface)]"
                >
                  Clear
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {popularCategories.map((category) => (
                <ToggleSwitch
                  key={category}
                  checked={selectedCategories.includes(category)}
                  onCheckedChange={() => onToggleCategory(category)}
                  label={category}
                />
              ))}
            </div>

            <div className="space-y-1">
              <div className="text-[9px] font-mono uppercase tracking-wider text-muted-foreground">
                Selected
              </div>
              <div className="flex flex-wrap gap-1.5">
                {selectedCategories.length > 0 ? (
                  selectedCategories.map((category) => (
                    <span
                      key={category}
                      className="rounded-md border border-primary/20 bg-primary/10 px-2 py-0.5 text-[9px] font-mono uppercase tracking-wide text-primary"
                    >
                      {category}
                    </span>
                  ))
                ) : (
                  <span className="text-[10px] font-mono text-muted-foreground">
                    No categories selected.
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="space-y-5 rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-bg)]/50 p-4">
            <CustomSlider
              label="Lookback Window (Days)"
              value={daysBack}
              onChange={onDaysBackChange}
              min={1}
              max={30}
              step={1}
            />

            <ToggleSwitch
              checked={updateDatabase}
              onCheckedChange={onUpdateDatabaseChange}
              label="Auto Update Database"
            />
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={onTrackChanges}
              disabled={
                isAnyOperationRunning || selectedCategories.length === 0
              }
              className={cn(
                'inline-flex items-center gap-2 rounded-lg px-5 py-2.5 text-[11px] font-mono font-bold uppercase transition-colors touch-manipulation',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60 focus-visible:ring-offset-2 focus-visible:ring-offset-background',
                'bg-primary text-background hover:bg-primary/80 disabled:cursor-not-allowed disabled:opacity-45'
              )}
            >
              {isTracking ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <RefreshCw className="h-4 w-4" aria-hidden="true" />
              )}
              Run Change Scan
            </button>

            <button
              type="button"
              onClick={onRefreshMetrics}
              disabled={isAnyOperationRunning || isStatsLoading}
              className="rounded-lg border border-[var(--terminal-border)] px-5 py-2.5 text-[11px] font-mono font-bold uppercase text-muted-foreground transition-colors hover:bg-[var(--terminal-surface)] disabled:cursor-not-allowed disabled:opacity-45"
            >
              Refresh Metrics
            </button>
          </div>
        </div>

        <div className="space-y-5 xl:col-span-7">
          <div className="flex min-h-[320px] flex-col rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-bg)] p-5">
            <div className="mb-4 flex items-center justify-between border-b border-[var(--terminal-border)] pb-3">
              <span className="text-[9px] font-mono font-bold uppercase tracking-widest text-muted-foreground">
                Activity Feed
              </span>
              <span className="inline-flex items-center gap-1.5 text-[9px] font-mono text-primary">
                <span
                  className="h-1.5 w-1.5 rounded-full bg-primary"
                  aria-hidden="true"
                />
                Live
              </span>
            </div>

            {trackingResult ? (
              <div className="space-y-4">
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-4">
                  {[
                    {
                      label: 'New',
                      value: trackingResult.result.summary.new,
                      color: 'text-primary',
                    },
                    {
                      label: 'Updated',
                      value: trackingResult.result.summary.updated,
                      color: 'text-[var(--cyan)]',
                    },
                    {
                      label: 'Deleted',
                      value: trackingResult.result.summary.deleted,
                      color: 'text-[var(--amber-gold)]',
                    },
                    {
                      label: 'Errors',
                      value: trackingResult.result.summary.errors,
                      color: 'text-red-300',
                    },
                  ].map((item) => (
                    <div
                      key={item.label}
                      className="rounded-lg border border-[var(--terminal-border)] bg-[var(--terminal-surface)] p-3"
                    >
                      <div
                        className={cn(
                          'text-lg font-mono font-bold',
                          item.color
                        )}
                      >
                        {item.value}
                      </div>
                      <div className="mt-0.5 text-[9px] font-mono uppercase tracking-wide text-muted-foreground">
                        {item.label}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="rounded-lg border border-[var(--terminal-border)] bg-[var(--terminal-surface)] p-3 text-[10px] font-mono text-muted-foreground">
                  <div className="mb-2 text-[9px] uppercase tracking-wider text-muted-foreground">
                    Sync Summary
                  </div>
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                    <div>
                      <span className="text-muted-foreground">
                        Papers scanned:
                      </span>{' '}
                      <span className="text-foreground">
                        {trackingResult.result.papers_found}
                      </span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">
                        Changes detected:
                      </span>{' '}
                      <span className="text-foreground">
                        {trackingResult.result.changes_detected}
                      </span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">DB write:</span>{' '}
                      <span className="text-foreground">
                        {trackingResult.result.applied ? 'Enabled' : 'Dry Run'}
                      </span>
                    </div>
                  </div>
                </div>

                {trackingResult.result.applied && (
                  <div className="rounded-lg border border-primary/25 bg-primary/5 p-3 text-[10px] font-mono text-foreground">
                    Knowledge graph synchronization has been queued for detected
                    updates.
                  </div>
                )}
              </div>
            ) : (
              <div className="flex flex-1 flex-col items-center justify-center text-center opacity-50">
                <Terminal
                  className="mb-3 h-8 w-8 text-muted-foreground"
                  aria-hidden="true"
                />
                <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground">
                  Run a scan to view updates and actions
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
