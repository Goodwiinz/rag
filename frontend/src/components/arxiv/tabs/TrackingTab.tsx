import { cn } from '@/lib/utils';
import {
  Loader2,
  Lock,
  LogIn,
  RefreshCw,
  Sparkles,
  Terminal,
} from 'lucide-react';
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
      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1.5 rounded-md border border-border bg-muted/30 px-2.5 py-1 text-xs font-medium text-muted-foreground">
          <Sparkles aria-hidden="true" className="h-3.5 w-3.5 text-primary" />
          Track new and updated papers
        </span>
        <span className="inline-flex items-center rounded-md border border-border bg-muted/30 px-2.5 py-1 text-xs text-muted-foreground tabular-nums">
          {selectedCategories.length} categories selected
        </span>
        <span className="inline-flex items-center rounded-md border border-border bg-muted/30 px-2.5 py-1 text-xs text-muted-foreground tabular-nums">
          {daysBack} day depth
        </span>
      </div>

      {!isAuthenticated && (
        <div className="rounded-lg border border-border bg-muted/20 p-4">
          <div className="flex items-start gap-3">
            <div className="rounded-lg bg-muted p-2 text-primary">
              <Lock aria-hidden="true" className="h-4 w-4" />
            </div>
            <div className="space-y-2">
              <p className="text-sm font-medium text-foreground">
                Workspace scan required
              </p>
              <p className="text-sm leading-relaxed text-muted-foreground">
                Change scans update the tracked corpus for your workspace. Sign
                in to run scans, or keep using public search and stats.
              </p>
              <a
                href="/login"
                className="inline-flex items-center gap-2 rounded-md border border-border bg-background px-3 py-2 text-sm font-medium text-primary transition-colors hover:border-[var(--nous-helios)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              >
                <LogIn aria-hidden="true" className="h-3.5 w-3.5" />
                Sign in to run scans
              </a>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-12">
        <div className="space-y-5 xl:col-span-5">
          <div className="space-y-4 rounded-lg border border-border bg-muted/20 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-sm font-medium text-foreground">
                Category filter
              </h3>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => onApplyCategoryPreset('core')}
                  className="rounded-md border border-primary/25 px-2.5 py-1 text-xs font-medium text-primary transition-colors hover:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                >
                  Core AI
                </button>
                <button
                  type="button"
                  onClick={() => onApplyCategoryPreset('all')}
                  className="rounded-md border border-border px-2.5 py-1 text-xs font-medium text-muted-foreground transition-colors hover:border-[var(--nous-helios)] hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                >
                  Select all
                </button>
                <button
                  type="button"
                  onClick={() => onApplyCategoryPreset('clear')}
                  className="rounded-md border border-border px-2.5 py-1 text-xs font-medium text-muted-foreground transition-colors hover:border-[var(--nous-helios)] hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
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
                      className="rounded-md border border-primary/20 bg-primary/10 px-2 py-0.5 font-[var(--nous-font-mono)] text-xs text-primary"
                    >
                      {category}
                    </span>
                  ))
                ) : (
                  <span className="text-xs text-muted-foreground">
                    No categories selected.
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="space-y-5 rounded-lg border border-border bg-muted/20 p-4">
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
                'inline-flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-medium transition-colors',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background',
                'bg-primary text-primary-foreground hover:bg-[var(--nous-helios)] disabled:cursor-not-allowed disabled:opacity-45'
              )}
            >
              {isTracking ? (
                <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw aria-hidden="true" className="h-4 w-4" />
              )}
              {isTracking ? 'Scanning…' : 'Run change scan'}
            </button>

            <button
              type="button"
              onClick={onRefreshMetrics}
              disabled={isAnyOperationRunning || isStatsLoading}
              className="rounded-lg border border-border px-5 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:border-[var(--nous-helios)] hover:text-foreground disabled:cursor-not-allowed disabled:opacity-45 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
              Refresh metrics
            </button>
          </div>
        </div>

        <div className="space-y-5 xl:col-span-7">
          <div className="flex min-h-[320px] flex-col rounded-lg border border-border bg-muted/20 p-5">
            <div className="mb-4 flex items-center justify-between border-b border-border pb-3">
              <span className="text-sm font-medium text-foreground">
                Scan results
              </span>
              {trackingResult && (
                <span className="text-xs text-muted-foreground">
                  Last scan complete
                </span>
              )}
            </div>

            {trackingResult ? (
              <div className="space-y-4">
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-4">
                  {[
                    {
                      label: 'New',
                      value: trackingResult.result.summary.new,
                      tone: 'text-foreground',
                    },
                    {
                      label: 'Updated',
                      value: trackingResult.result.summary.updated,
                      tone: 'text-foreground',
                    },
                    {
                      label: 'Deleted',
                      value: trackingResult.result.summary.deleted,
                      tone: 'text-[var(--nous-corona)]',
                    },
                    {
                      label: 'Errors',
                      value: trackingResult.result.summary.errors,
                      tone:
                        trackingResult.result.summary.errors > 0
                          ? 'text-[var(--nous-mars)]'
                          : 'text-foreground',
                    },
                  ].map((item) => (
                    <div
                      key={item.label}
                      className="rounded-lg border border-border bg-card p-3 shadow-sm"
                    >
                      <div
                        className={cn(
                          'text-lg font-semibold tabular-nums',
                          item.tone
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

                <div className="rounded-lg border border-border bg-card p-3 text-sm shadow-sm">
                  <div className="mb-2 text-xs font-medium text-muted-foreground">
                    Sync summary
                  </div>
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                    <div>
                      <span className="text-muted-foreground">
                        Papers scanned:
                      </span>{' '}
                      <span className="font-medium text-foreground tabular-nums">
                        {trackingResult.result.papers_found}
                      </span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">
                        Changes detected:
                      </span>{' '}
                      <span className="font-medium text-foreground tabular-nums">
                        {trackingResult.result.changes_detected}
                      </span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">DB write:</span>{' '}
                      <span className="font-medium text-foreground">
                        {trackingResult.result.applied ? 'Enabled' : 'Dry run'}
                      </span>
                    </div>
                  </div>
                </div>

                {trackingResult.result.applied && (
                  <div className="rounded-lg border border-primary/25 bg-primary/5 p-3 text-sm text-foreground">
                    Knowledge graph synchronization has been queued for detected
                    updates.
                  </div>
                )}
              </div>
            ) : (
              <div className="flex flex-1 flex-col items-center justify-center text-center">
                <div className="mb-3 rounded-lg bg-muted p-3 text-muted-foreground">
                  <Terminal aria-hidden="true" className="h-6 w-6" />
                </div>
                <p className="text-sm font-medium text-foreground">
                  No scan yet
                </p>
                <p className="mt-1 max-w-xs text-sm text-muted-foreground">
                  Pick categories and run a change scan to see new, updated, and
                  deleted papers here.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
