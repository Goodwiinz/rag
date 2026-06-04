import { cn } from '@/lib/utils';
import { AlertCircle, Brain, Loader2, Lock, LogIn, Zap } from 'lucide-react';
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
  const enabledFeatures = [
    extractEntities && 'Entities',
    extractTopics && 'Topics',
    extractKeyphrases && 'Keyphrases',
    extractCitations && 'Citations',
    extractSummaries && 'Summaries',
  ].filter(Boolean) as string[];

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h3 className="flex items-center gap-2 text-base font-semibold text-foreground">
          <Brain className="h-4 w-4 text-primary" aria-hidden="true" />
          Extract research signals
        </h3>
        <p className="font-[family-name:var(--nous-font-body)] text-sm leading-relaxed text-muted-foreground">
          Extract entities, topics, keyphrases, citations, and summaries for
          specific papers, then optionally sync to the knowledge graph.
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
                Extraction is workspace-only
              </p>
              <p className="font-[family-name:var(--nous-font-body)] text-sm leading-relaxed text-muted-foreground">
                Paste paper IDs to prep a run, then sign in to extract entities,
                citations, summaries, and knowledge-graph updates.
              </p>
              <a
                href="/login"
                className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              >
                <LogIn className="h-3.5 w-3.5" aria-hidden="true" />
                Sign in to extract
              </a>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
        <div className="space-y-4 xl:col-span-5">
          <div className="space-y-4 rounded-xl border border-border bg-background p-4">
            <div className="space-y-2">
              <label
                htmlFor="extract-paper-ids"
                className="text-sm font-medium text-foreground"
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
                className="w-full rounded-lg border border-border bg-card p-3 font-[family-name:var(--nous-font-mono)] text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40"
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
                  'inline-flex flex-1 items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition-colors',
                  'hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40 focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-45'
                )}
              >
                {isExtracting ? (
                  <Loader2
                    className="h-4 w-4 animate-spin"
                    aria-hidden="true"
                  />
                ) : (
                  <Zap className="h-4 w-4" aria-hidden="true" />
                )}
                Extract Features
              </button>

              <button
                type="button"
                onClick={onClearExtract}
                disabled={isAnyOperationRunning}
                className="rounded-lg border border-border px-4 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40 focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-45"
              >
                Clear
              </button>
            </div>
          </div>

          <div className="rounded-xl border border-border bg-background p-4">
            <div className="text-sm font-medium text-foreground">
              Valid paper IDs ({parsedExtractIds.length})
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {parsedExtractIds.length > 0 ? (
                parsedExtractIds.slice(0, 20).map((paperId) => (
                  <span
                    key={paperId}
                    className="max-w-full break-all rounded border border-border bg-card px-2 py-0.5 font-[family-name:var(--nous-font-mono)] text-xs text-muted-foreground"
                  >
                    {paperId}
                  </span>
                ))
              ) : (
                <span className="text-sm text-muted-foreground">
                  No paper IDs entered yet.
                </span>
              )}
              {parsedExtractIds.length > 20 && (
                <span className="text-xs text-muted-foreground">
                  +{parsedExtractIds.length - 20} more
                </span>
              )}
            </div>

            {invalidExtractIds.length > 0 && (
              <div
                role="alert"
                className="mt-3 rounded-lg border border-[var(--nous-mars)]/30 bg-[var(--nous-mars)]/10 p-2.5"
              >
                <div className="flex items-center gap-1.5 text-sm font-medium text-[var(--nous-mars)]">
                  <AlertCircle className="h-3.5 w-3.5" aria-hidden="true" />
                  Invalid IDs ({invalidExtractIds.length})
                </div>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {invalidExtractIds.slice(0, 12).map((paperId) => (
                    <span
                      key={paperId}
                      className="max-w-full break-all rounded border border-[var(--nous-mars)]/30 bg-[var(--nous-mars)]/10 px-2 py-0.5 font-[family-name:var(--nous-font-mono)] text-xs text-[var(--nous-mars)]"
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
          <div className="rounded-xl border border-border bg-card p-4 sm:p-5">
            <div className="mb-4 flex items-center justify-between border-b border-border pb-3">
              <span className="text-sm font-medium text-foreground">
                Extraction results
              </span>
              <span className="text-sm text-muted-foreground">
                {extractionResult
                  ? `${extractionResult.processed_count} processed`
                  : 'Awaiting run'}
              </span>
            </div>

            {extractionResult ? (
              <div className="space-y-4">
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                  <div className="rounded-lg border border-border bg-background p-3">
                    <div className="text-xs text-muted-foreground">Status</div>
                    <div className="mt-1 text-sm font-medium text-foreground">
                      {extractionResult.status}
                    </div>
                  </div>
                  <div className="rounded-lg border border-border bg-background p-3">
                    <div className="text-xs text-muted-foreground">Papers</div>
                    <div className="mt-1 text-sm font-medium tabular-nums text-foreground">
                      {extractionResult.processed_count}
                    </div>
                  </div>
                  <div className="rounded-lg border border-border bg-background p-3">
                    <div className="text-xs text-muted-foreground">
                      Enabled features
                    </div>
                    <div className="mt-1 text-sm font-medium text-foreground">
                      {enabledFeatures.length > 0
                        ? enabledFeatures.join(', ')
                        : 'None'}
                    </div>
                  </div>
                </div>

                <div className="max-h-[480px] space-y-3 overflow-y-auto pr-1 nous-scrollbar">
                  {extractionResult.results.map((result) => {
                    const featureKeys = Object.keys(result.features || {});
                    const hasFailed = result.extraction_status !== 'completed';

                    return (
                      <div
                        key={result.paper_id}
                        className={cn(
                          'rounded-lg border p-3',
                          hasFailed
                            ? 'border-[var(--nous-mars)]/30 bg-[var(--nous-mars)]/10'
                            : 'border-border bg-background'
                        )}
                      >
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div className="min-w-0">
                            <div className="truncate text-sm font-medium text-foreground">
                              {result.title || result.paper_id}
                            </div>
                            <div className="mt-1 font-[family-name:var(--nous-font-mono)] text-xs text-muted-foreground">
                              {result.paper_id}
                            </div>
                          </div>
                          <span
                            className={cn(
                              'inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs font-medium',
                              hasFailed
                                ? 'border-[var(--nous-mars)]/30 text-[var(--nous-mars)]'
                                : 'border-primary/30 text-primary'
                            )}
                          >
                            {hasFailed && (
                              <AlertCircle
                                className="h-3 w-3"
                                aria-hidden="true"
                              />
                            )}
                            {result.extraction_status}
                          </span>
                        </div>

                        {!hasFailed && featureKeys.length > 0 && (
                          <div className="mt-2 flex flex-wrap gap-1.5">
                            {featureKeys.map((key) => (
                              <span
                                key={key}
                                className="rounded border border-border bg-card px-2 py-0.5 text-xs text-muted-foreground"
                              >
                                {key}
                              </span>
                            ))}
                          </div>
                        )}

                        {result.error && (
                          <div className="mt-2 text-xs text-[var(--nous-mars)]">
                            {result.error}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : (
              <div className="flex min-h-[280px] flex-col items-center justify-center gap-3 text-center">
                <Brain
                  className="h-7 w-7 text-muted-foreground"
                  aria-hidden="true"
                />
                <p className="text-sm text-muted-foreground">
                  Extraction results will appear here.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
