import { cn } from '@/lib/utils';
import { Loader2, Lock, LogIn, RefreshCw } from 'lucide-react';
import React from 'react';

import { CustomSlider, ToggleSwitch } from '../ArxivControls';
import { TrackResult } from '../arxivTypes';

interface TrackingTabProps {
  isAuthenticated: boolean;
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
  isAuthenticated,
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
      <div className="space-y-1">
        <h3 className="text-base font-semibold text-foreground">
          Track new and updated papers
        </h3>
        <p className="font-[family-name:var(--nous-font-body)] text-sm leading-relaxed text-muted-foreground">
          {selectedCategories.length} categories selected, {daysBack} day
          lookback.
        </p>
      </div>

      {!isAuthenticated && (
        <div className="rounded-xl border border-border bg-background p-4">
          <div className="flex items-start gap-3">
            <div className="rounded-lg border border-border bg-card p-2">
              <Lock className="h-4 w-4 text-primary" aria-hidden="true" />
            </div>
            <div className="space-y-2">
              <p className="text-sm font-medium text-foreground">
                Workspace scan required
              </p>
              <p className="font-[family-name:var(--nous-font-body)] text-sm leading-relaxed text-muted-foreground">
                Change scans update the tracked corpus for your workspace. Sign
                in to run scans, or keep using public search and statistics.
              </p>
              <a
                href="/login"
                className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              >
                <LogIn className="h-3.5 w-3.5" aria-hidden="true" />
                Sign in to run scans
              </a>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-12">
        <div className="space-y-5 xl:col-span-5">
          <div className="space-y-4 rounded-xl border border-border bg-background p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h4 className="text-sm font-medium text-foreground">
                Category filter
              </h4>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => onApplyCategoryPreset('core')}
                  className="rounded-md border border-primary/30 px-2 py-1 text-xs font-medium text-primary transition-colors hover:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40"
                >
                  Core AI
                </button>
                <button
                  type="button"
                  onClick={() => onApplyCategoryPreset('all')}
                  className="rounded-md border border-border px-2 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40"
                >
                  Select all
                </button>
                <button
                  type="button"
                  onClick={() => onApplyCategoryPreset('clear')}
                  className="rounded-md border border-border px-2 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40"
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

            <div className="space-y-1.5">
              <div className="text-xs text-muted-foreground">Selected</div>
              <div className="flex flex-wrap gap-1.5">
                {selectedCategories.length > 0 ? (
                  selectedCategories.map((category) => (
                    <span
                      key={category}
                      className="rounded-md border border-primary/30 bg-primary/5 px-2 py-0.5 text-xs font-medium text-primary"
                    >
                      {category}
                    </span>
                  ))
                ) : (
                  <span className="text-sm text-muted-foreground">
                    No categories selected.
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="space-y-5 rounded-xl border border-border bg-background p-4">
            <CustomSlider
              label="Lookback window (days)"
              value={daysBack}
              onChange={onDaysBackChange}
              min={1}
              max={30}
              step={1}
            />

            <ToggleSwitch
              checked={updateDatabase}
              onCheckedChange={onUpdateDatabaseChange}
              label="Auto-update database"
            />
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={onTrackChanges}
              disabled={
                !isAuthenticated ||
                isAnyOperationRunning ||
                selectedCategories.length === 0
              }
              className={cn(
                'inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition-colors touch-manipulation',
                'hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40 focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-45'
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
              className="rounded-lg border border-border px-5 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40 focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-45"
            >
              Refresh metrics
            </button>
          </div>
        </div>

        <div className="space-y-5 xl:col-span-7">
          <div className="flex min-h-[320px] flex-col rounded-xl border border-border bg-card p-5">
            <div className="mb-4 border-b border-border pb-3">
              <span className="text-sm font-medium text-foreground">
                Last scan
              </span>
            </div>

            {trackingResult ? (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                  {[
                    {
                      label: 'New',
                      value: trackingResult.result.summary.new,
                      isError: false,
                    },
                    {
                      label: 'Updated',
                      value: trackingResult.result.summary.updated,
                      isError: false,
                    },
                    {
                      label: 'Deleted',
                      value: trackingResult.result.summary.deleted,
                      isError: false,
                    },
                    {
                      label: 'Errors',
                      value: trackingResult.result.summary.errors,
                      isError: trackingResult.result.summary.errors > 0,
                    },
                  ].map((item) => (
                    <div
                      key={item.label}
                      className="rounded-lg border border-border bg-background p-3"
                    >
                      <div
                        className={cn(
                          'text-lg font-semibold tabular-nums',
                          item.isError
                            ? 'text-[var(--nous-mars)]'
                            : 'text-foreground'
                        )}
                      >
                        {item.value}
                      </div>
                      <div className="mt-0.5 text-xs text-muted-foreground">
                        {item.label}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="rounded-lg border border-border bg-background p-3 text-sm text-muted-foreground">
                  <div className="mb-2 text-xs font-medium text-foreground">
                    Scan summary
                  </div>
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                    <div>
                      <span className="text-muted-foreground">
                        Papers scanned:
                      </span>{' '}
                      <span className="font-medium text-foreground">
                        {trackingResult.result.papers_found}
                      </span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">
                        Changes detected:
                      </span>{' '}
                      <span className="font-medium text-foreground">
                        {trackingResult.result.changes_detected}
                      </span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">
                        Database write:
                      </span>{' '}
                      <span className="font-medium text-foreground">
                        {trackingResult.result.applied ? 'Enabled' : 'Dry run'}
                      </span>
                    </div>
                  </div>
                </div>

                {trackingResult.result.applied && (
                  <div className="rounded-lg border border-primary/30 bg-primary/5 p-3 text-sm text-foreground">
                    Knowledge graph sync has been queued for the detected
                    updates.
                  </div>
                )}
              </div>
            ) : (
              <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
                <RefreshCw
                  className="h-7 w-7 text-muted-foreground"
                  aria-hidden="true"
                />
                <p className="text-sm text-muted-foreground">
                  Run a scan to view updates and actions.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
