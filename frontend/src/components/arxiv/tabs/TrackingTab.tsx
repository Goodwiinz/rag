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
        <span className="inline-flex items-center gap-1 rounded-md border border-[#1A1A1A] bg-[#0A0A0A]/50 px-2 py-1 text-[9px] font-mono uppercase tracking-wider text-[#9CA3AF]">
          <Sparkles className="h-3 w-3 text-[#FFB700]" />
          Track New and Updated Papers
        </span>
        <span className="inline-flex items-center rounded-md border border-[#1A1A1A] bg-[#0A0A0A]/50 px-2 py-1 text-[9px] font-mono uppercase tracking-wider text-[#9CA3AF]">
          {selectedCategories.length} categories selected
        </span>
        <span className="inline-flex items-center rounded-md border border-[#1A1A1A] bg-[#0A0A0A]/50 px-2 py-1 text-[9px] font-mono uppercase tracking-wider text-[#9CA3AF]">
          {daysBack} day depth
        </span>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-12">
        <div className="space-y-5 xl:col-span-5">
          <div className="space-y-4 rounded-xl border border-[#1A1A1A] bg-[#0A0A0A]/50 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-[10px] font-mono font-bold uppercase tracking-widest text-[#9CA3AF]">
                Category Filter
              </h3>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => onApplyCategoryPreset('core')}
                  className="rounded-md border border-[#D4A039]/25 px-2 py-1 text-[9px] font-mono uppercase tracking-wide text-[#D4A039] hover:bg-[#D4A039]/10"
                >
                  Core AI
                </button>
                <button
                  type="button"
                  onClick={() => onApplyCategoryPreset('all')}
                  className="rounded-md border border-[#1A1A1A] px-2 py-1 text-[9px] font-mono uppercase tracking-wide text-[#6B7280] hover:bg-[#151515]"
                >
                  Select All
                </button>
                <button
                  type="button"
                  onClick={() => onApplyCategoryPreset('clear')}
                  className="rounded-md border border-[#1A1A1A] px-2 py-1 text-[9px] font-mono uppercase tracking-wide text-[#6B7280] hover:bg-[#151515]"
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
              <div className="text-[9px] font-mono uppercase tracking-wider text-[#6B7280]">
                Selected
              </div>
              <div className="flex flex-wrap gap-1.5">
                {selectedCategories.length > 0 ? (
                  selectedCategories.map((category) => (
                    <span
                      key={category}
                      className="rounded-md border border-[#D4A039]/20 bg-[#D4A039]/10 px-2 py-0.5 text-[9px] font-mono uppercase tracking-wide text-[#D4A039]"
                    >
                      {category}
                    </span>
                  ))
                ) : (
                  <span className="text-[10px] font-mono text-[#6B7280]">
                    No categories selected.
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="space-y-5 rounded-xl border border-[#1A1A1A] bg-[#0A0A0A]/50 p-4">
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
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#D4A039]/60 focus-visible:ring-offset-2 focus-visible:ring-offset-[#0A0A0A]',
                'bg-[#D4A039] text-[#0A0A0A] hover:bg-[#B8882F] disabled:cursor-not-allowed disabled:opacity-45'
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
              className="rounded-lg border border-[#1A1A1A] px-5 py-2.5 text-[11px] font-mono font-bold uppercase text-[#6B7280] transition-colors hover:bg-[#151515] disabled:cursor-not-allowed disabled:opacity-45"
            >
              Refresh Metrics
            </button>
          </div>
        </div>

        <div className="space-y-5 xl:col-span-7">
          <div className="flex min-h-[320px] flex-col rounded-xl border border-[#1A1A1A] bg-[#0A0A0A] p-5">
            <div className="mb-4 flex items-center justify-between border-b border-[#1A1A1A] pb-3">
              <span className="text-[9px] font-mono font-bold uppercase tracking-widest text-[#9CA3AF]">
                Activity Feed
              </span>
              <span className="inline-flex items-center gap-1.5 text-[9px] font-mono text-[#D4A039]">
                <span
                  className="h-1.5 w-1.5 rounded-full bg-[#D4A039]"
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
                      color: 'text-[#D4A039]',
                    },
                    {
                      label: 'Updated',
                      value: trackingResult.result.summary.updated,
                      color: 'text-[#00D4FF]',
                    },
                    {
                      label: 'Deleted',
                      value: trackingResult.result.summary.deleted,
                      color: 'text-[#FFB700]',
                    },
                    {
                      label: 'Errors',
                      value: trackingResult.result.summary.errors,
                      color: 'text-[#FFAEAE]',
                    },
                  ].map((item) => (
                    <div
                      key={item.label}
                      className="rounded-lg border border-[#1A1A1A] bg-[#111111] p-3"
                    >
                      <div
                        className={cn(
                          'text-lg font-mono font-bold',
                          item.color
                        )}
                      >
                        {item.value}
                      </div>
                      <div className="mt-0.5 text-[9px] font-mono uppercase tracking-wide text-[#6B7280]">
                        {item.label}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="rounded-lg border border-[#1A1A1A] bg-[#111111] p-3 text-[10px] font-mono text-[#9CA3AF]">
                  <div className="mb-2 text-[9px] uppercase tracking-wider text-[#6B7280]">
                    Sync Summary
                  </div>
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                    <div>
                      <span className="text-[#6B7280]">Papers scanned:</span>{' '}
                      <span className="text-[#E5E7EB]">
                        {trackingResult.result.papers_found}
                      </span>
                    </div>
                    <div>
                      <span className="text-[#6B7280]">Changes detected:</span>{' '}
                      <span className="text-[#E5E7EB]">
                        {trackingResult.result.changes_detected}
                      </span>
                    </div>
                    <div>
                      <span className="text-[#6B7280]">DB write:</span>{' '}
                      <span className="text-[#E5E7EB]">
                        {trackingResult.result.applied ? 'Enabled' : 'Dry Run'}
                      </span>
                    </div>
                  </div>
                </div>

                {trackingResult.result.applied && (
                  <div className="rounded-lg border border-[#D4A039]/25 bg-[#D4A039]/5 p-3 text-[10px] font-mono text-[#E5E7EB]">
                    Knowledge graph synchronization has been queued for detected
                    updates.
                  </div>
                )}
              </div>
            ) : (
              <div className="flex flex-1 flex-col items-center justify-center text-center opacity-50">
                <Terminal
                  className="mb-3 h-8 w-8 text-[#6B7280]"
                  aria-hidden="true"
                />
                <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-[#6B7280]">
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
