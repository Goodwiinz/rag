import { cn } from '@/lib/utils';
import { Brain, Loader2, Lock, LogIn, Zap } from 'lucide-react';
import React from 'react';

import { ToggleSwitch } from '../ArxivControls';
import { ExtractionResult } from '../arxivTypes';

interface ExtractTabProps {
  isAuthenticated: boolean;
  extractPaperIds: string;
  parsedExtractIds: string[];
  invalidExtractIds: string[];
  isAnyOperationRunning: boolean;
  isExtracting: boolean;
  extractionResult: ExtractionResult | null;
  extractEntities: boolean;
  extractTopics: boolean;
  extractKeyphrases: boolean;
  extractCitations: boolean;
  extractSummaries: boolean;
  updateKG: boolean;
  onExtractPaperIdsChange: (value: string) => void;
  onExtractEntitiesChange: (checked: boolean) => void;
  onExtractTopicsChange: (checked: boolean) => void;
  onExtractKeyphrasesChange: (checked: boolean) => void;
  onExtractCitationsChange: (checked: boolean) => void;
  onExtractSummariesChange: (checked: boolean) => void;
  onUpdateKGChange: (checked: boolean) => void;
  onExtractFeatures: () => void;
  onClearExtract: () => void;
}

export function ExtractTab({
  isAuthenticated,
  extractPaperIds,
  parsedExtractIds,
  invalidExtractIds,
  isAnyOperationRunning,
  isExtracting,
  extractionResult,
  extractEntities,
  extractTopics,
  extractKeyphrases,
  extractCitations,
  extractSummaries,
  updateKG,
  onExtractPaperIdsChange,
  onExtractEntitiesChange,
  onExtractTopicsChange,
  onExtractKeyphrasesChange,
  onExtractCitationsChange,
  onExtractSummariesChange,
  onUpdateKGChange,
  onExtractFeatures,
  onClearExtract,
}: ExtractTabProps) {
  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h3 className="flex items-center gap-2 text-sm font-medium text-foreground">
          <Brain aria-hidden="true" className="h-4 w-4 text-primary" />
          Extract research signals
        </h3>
        <p className="text-sm leading-relaxed text-muted-foreground">
          Extract entities, topics, keyphrases, citations, and summaries for
          specific papers, then optionally sync to the knowledge graph.
        </p>
      </div>

      {!isAuthenticated && (
        <div className="rounded-lg border border-border bg-muted/20 p-4">
          <div className="flex items-start gap-3">
            <div className="rounded-lg bg-muted p-2 text-primary">
              <Lock aria-hidden="true" className="h-4 w-4" />
            </div>
            <div className="space-y-2">
              <p className="text-sm font-medium text-foreground">
                Extraction is workspace-only
              </p>
              <p className="text-sm leading-relaxed text-muted-foreground">
                Paste paper IDs to prep a run, then sign in to extract entities,
                citations, summaries, and knowledge-graph updates.
              </p>
              <a
                href="/login"
                className="inline-flex items-center gap-2 rounded-md border border-border bg-background px-3 py-2 text-sm font-medium text-primary transition-colors hover:border-[var(--nous-helios)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              >
                <LogIn aria-hidden="true" className="h-3.5 w-3.5" />
                Sign in to extract
              </a>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
        <div className="space-y-4 xl:col-span-5">
          <div className="space-y-4 rounded-lg border border-border bg-muted/20 p-4">
            <div className="space-y-2">
              <label
                htmlFor="extract-paper-ids"
                className="text-xs font-medium text-muted-foreground"
              >
                Paper IDs (one per line or comma-separated)
              </label>
              <textarea
                id="extract-paper-ids"
                name="extractPaperIds"
                value={extractPaperIds}
                onChange={(e) => onExtractPaperIdsChange(e.target.value)}
                placeholder={'2501.12345\n2501.67890…'}
                rows={7}
                className="w-full rounded-lg border border-border bg-background p-3 font-[var(--nous-font-mono)] text-sm text-foreground placeholder:text-muted-foreground transition-colors focus:border-primary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </div>

            <div className="grid grid-cols-1 gap-2">
              <ToggleSwitch
                checked={extractEntities}
                onCheckedChange={onExtractEntitiesChange}
                label="Extract entities"
              />
              <ToggleSwitch
                checked={extractTopics}
                onCheckedChange={onExtractTopicsChange}
                label="Extract topics"
              />
              <ToggleSwitch
                checked={extractKeyphrases}
                onCheckedChange={onExtractKeyphrasesChange}
                label="Extract keyphrases"
              />
              <ToggleSwitch
                checked={extractCitations}
                onCheckedChange={onExtractCitationsChange}
                label="Extract citations"
              />
              <ToggleSwitch
                checked={extractSummaries}
                onCheckedChange={onExtractSummariesChange}
                label="Generate summaries"
              />
              <ToggleSwitch
                checked={updateKG}
                onCheckedChange={onUpdateKGChange}
                label="Update knowledge graph"
              />
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={onExtractFeatures}
                disabled={
                  !isAuthenticated ||
                  isAnyOperationRunning ||
                  parsedExtractIds.length === 0 ||
                  invalidExtractIds.length > 0
                }
                className={cn(
                  'inline-flex flex-1 items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors',
                  'bg-primary text-primary-foreground hover:bg-[var(--nous-helios)] disabled:cursor-not-allowed disabled:opacity-45',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background'
                )}
              >
                {isExtracting ? (
                  <Loader2
                    aria-hidden="true"
                    className="h-4 w-4 animate-spin"
                  />
                ) : (
                  <Zap aria-hidden="true" className="h-4 w-4" />
                )}
                {isExtracting ? 'Extracting…' : 'Extract features'}
              </button>

              <button
                type="button"
                onClick={onClearExtract}
                disabled={isAnyOperationRunning}
                className="rounded-lg border border-border px-4 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:border-[var(--nous-helios)] hover:text-foreground disabled:cursor-not-allowed disabled:opacity-45 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              >
                Clear
              </button>
            </div>
          </div>

          <div className="rounded-lg border border-border bg-muted/20 p-4">
            <div className="text-xs font-medium text-muted-foreground">
              Valid paper IDs
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {parsedExtractIds.length > 0 ? (
                parsedExtractIds.slice(0, 20).map((paperId) => (
                  <span
                    key={paperId}
                    className="rounded border border-border bg-background px-2 py-0.5 font-[var(--nous-font-mono)] text-xs text-foreground"
                  >
                    {paperId}
                  </span>
                ))
              ) : (
                <span className="text-xs text-muted-foreground">
                  No paper IDs entered yet.
                </span>
              )}
            </div>

            {invalidExtractIds.length > 0 && (
              <div
                role="alert"
                className="mt-3 rounded-lg border border-[var(--nous-mars)]/40 bg-[var(--nous-mars)]/10 p-2.5"
              >
                <div className="text-xs font-medium text-foreground">
                  Invalid IDs ({invalidExtractIds.length})
                </div>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {invalidExtractIds.slice(0, 12).map((paperId) => (
                    <span
                      key={paperId}
                      className="rounded border border-[var(--nous-mars)]/40 bg-background px-2 py-0.5 font-[var(--nous-font-mono)] text-xs text-foreground"
                    >
                      {paperId}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="space-y-4 xl:col-span-7">
          <div className="rounded-lg border border-border bg-muted/20 p-5">
            <div className="mb-4 flex items-center justify-between border-b border-border pb-3">
              <span className="text-sm font-medium text-foreground">
                Extraction results
              </span>
              <span className="text-xs text-muted-foreground">
                {extractionResult
                  ? `${extractionResult.processed_count} processed`
                  : 'Awaiting run'}
              </span>
            </div>

            {extractionResult ? (
              <div className="space-y-4">
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                  <div className="rounded-lg border border-border bg-card p-3 shadow-sm">
                    <div className="text-xs text-muted-foreground">Status</div>
                    <div className="mt-1 text-sm font-medium text-foreground">
                      {extractionResult.status}
                    </div>
                  </div>
                  <div className="rounded-lg border border-border bg-card p-3 shadow-sm">
                    <div className="text-xs text-muted-foreground">Papers</div>
                    <div className="mt-1 text-sm font-medium text-foreground tabular-nums">
                      {extractionResult.processed_count}
                    </div>
                  </div>
                  <div className="rounded-lg border border-border bg-card p-3 shadow-sm">
                    <div className="text-xs text-muted-foreground">
                      Enabled features
                    </div>
                    <div className="mt-1 text-sm font-medium text-foreground">
                      {[
                        extractEntities && 'E',
                        extractTopics && 'T',
                        extractKeyphrases && 'K',
                        extractCitations && 'C',
                        extractSummaries && 'S',
                      ]
                        .filter(Boolean)
                        .join(' / ')}
                    </div>
                  </div>
                </div>

                <div className="max-h-[480px] space-y-3 overflow-y-auto pr-1">
                  {extractionResult.results.map((result) => {
                    const featureKeys = Object.keys(result.features || {});
                    const hasFailed = result.extraction_status !== 'completed';

                    return (
                      <div
                        key={result.paper_id}
                        role={hasFailed ? 'alert' : undefined}
                        className={cn(
                          'rounded-lg border p-3',
                          hasFailed
                            ? 'border-[var(--nous-mars)]/40 bg-[var(--nous-mars)]/10'
                            : 'border-border bg-card shadow-sm'
                        )}
                      >
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div className="min-w-0">
                            <div className="truncate text-sm font-medium text-foreground">
                              {result.title || result.paper_id}
                            </div>
                            <div className="mt-1 font-[var(--nous-font-mono)] text-xs text-muted-foreground">
                              {result.paper_id}
                            </div>
                          </div>
                          <span
                            className={cn(
                              'inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-xs font-medium',
                              hasFailed
                                ? 'border-[var(--nous-mars)]/40 text-[var(--nous-mars)]'
                                : 'border-[var(--nous-terra)]/40 text-[var(--nous-terra)]'
                            )}
                          >
                            <span
                              aria-hidden="true"
                              className={cn(
                                'h-1.5 w-1.5 rounded-full',
                                hasFailed
                                  ? 'bg-[var(--nous-mars)]'
                                  : 'bg-[var(--nous-terra)]'
                              )}
                            />
                            {result.extraction_status}
                          </span>
                        </div>

                        {!hasFailed && featureKeys.length > 0 && (
                          <div className="mt-2 flex flex-wrap gap-1.5">
                            {featureKeys.map((key) => (
                              <span
                                key={key}
                                className="rounded border border-border bg-background px-2 py-0.5 text-xs text-muted-foreground"
                              >
                                {key}
                              </span>
                            ))}
                          </div>
                        )}

                        {result.error && (
                          <div className="mt-2 text-xs text-foreground">
                            {result.error}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : (
              <div className="flex min-h-[280px] flex-col items-center justify-center text-center">
                <div className="mb-3 rounded-lg bg-muted p-3 text-muted-foreground">
                  <Brain aria-hidden="true" className="h-6 w-6" />
                </div>
                <p className="text-sm font-medium text-foreground">
                  No extraction yet
                </p>
                <p className="mt-1 max-w-xs text-sm text-muted-foreground">
                  Add paper IDs, choose what to extract, and run to see results
                  here.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
