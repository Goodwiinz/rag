import { cn } from '@/lib/utils';
import { Brain, Loader2, Zap } from 'lucide-react';
import React from 'react';

import { ToggleSwitch } from '../arxivControls';
import { ExtractionResult } from '../arxivTypes';

interface ExtractTabProps {
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
        <h3 className="flex items-center gap-2 text-sm font-mono font-bold uppercase tracking-tight text-foreground">
          <Brain
            className="h-4 w-4 text-[var(--amber-gold)]"
            aria-hidden="true"
          />
          Extract Research Signals
        </h3>
        <p className="text-[11px] font-mono leading-relaxed text-muted-foreground">
          Extract entities, topics, keyphrases, citations, and summaries for
          specific papers, then optionally sync to the knowledge graph.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
        <div className="space-y-4 xl:col-span-5">
          <div className="space-y-4 rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-bg)]/50 p-4">
            <div className="space-y-2">
              <label
                htmlFor="extract-paper-ids"
                className="text-[10px] font-mono font-bold uppercase tracking-widest text-muted-foreground"
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
                className="w-full rounded-lg border border-[var(--terminal-border)] bg-[var(--terminal-surface)] p-3 font-mono text-xs text-foreground placeholder:text-muted-foreground focus:border-primary/50 focus:outline-none"
              />
            </div>

            <div className="grid grid-cols-1 gap-2">
              <ToggleSwitch
                checked={extractEntities}
                onCheckedChange={onExtractEntitiesChange}
                label="Extract Entities"
              />
              <ToggleSwitch
                checked={extractTopics}
                onCheckedChange={onExtractTopicsChange}
                label="Extract Topics"
              />
              <ToggleSwitch
                checked={extractKeyphrases}
                onCheckedChange={onExtractKeyphrasesChange}
                label="Extract Keyphrases"
              />
              <ToggleSwitch
                checked={extractCitations}
                onCheckedChange={onExtractCitationsChange}
                label="Extract Citations"
              />
              <ToggleSwitch
                checked={extractSummaries}
                onCheckedChange={onExtractSummariesChange}
                label="Generate Summaries"
              />
              <ToggleSwitch
                checked={updateKG}
                onCheckedChange={onUpdateKGChange}
                label="Update Knowledge Graph"
              />
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={onExtractFeatures}
                disabled={
                  isAnyOperationRunning ||
                  parsedExtractIds.length === 0 ||
                  invalidExtractIds.length > 0
                }
                className={cn(
                  'inline-flex flex-1 items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-[11px] font-mono font-bold uppercase transition-colors',
                  'bg-[var(--amber-gold)]/20 text-[var(--amber-gold)] hover:bg-[var(--amber-gold)]/30 disabled:cursor-not-allowed disabled:opacity-45'
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
                className="rounded-lg border border-[var(--terminal-border)] px-4 py-2.5 text-[11px] font-mono font-bold uppercase text-muted-foreground hover:bg-[var(--terminal-surface)] disabled:cursor-not-allowed disabled:opacity-45"
              >
                Clear
              </button>
            </div>
          </div>

          <div className="rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-bg)]/50 p-4">
            <div className="text-[9px] font-mono uppercase tracking-widest text-muted-foreground">
              Valid Paper IDs
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {parsedExtractIds.length > 0 ? (
                parsedExtractIds.slice(0, 20).map((paperId) => (
                  <span
                    key={paperId}
                    className="rounded border border-[var(--terminal-border)] bg-[var(--terminal-surface)] px-2 py-0.5 text-[9px] font-mono text-muted-foreground"
                  >
                    {paperId}
                  </span>
                ))
              ) : (
                <span className="text-[10px] font-mono text-muted-foreground">
                  No paper IDs entered yet.
                </span>
              )}
            </div>

            {invalidExtractIds.length > 0 && (
              <div className="mt-3 rounded-lg border border-red-900 bg-red-950/70 p-2.5">
                <div className="text-[9px] font-mono uppercase tracking-widest text-red-300">
                  Invalid IDs ({invalidExtractIds.length})
                </div>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {invalidExtractIds.slice(0, 12).map((paperId) => (
                    <span
                      key={paperId}
                      className="rounded border border-red-800 bg-red-950 px-2 py-0.5 text-[9px] font-mono text-red-300"
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
          <div className="rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-bg)] p-5">
            <div className="mb-4 flex items-center justify-between border-b border-[var(--terminal-border)] pb-3">
              <span className="text-[9px] font-mono font-bold uppercase tracking-widest text-muted-foreground">
                Extraction Results
              </span>
              <span className="text-[10px] font-mono text-muted-foreground">
                {extractionResult
                  ? `${extractionResult.processed_count} processed`
                  : 'Awaiting run'}
              </span>
            </div>

            {extractionResult ? (
              <div className="space-y-4">
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                  <div className="rounded-lg border border-[var(--terminal-border)] bg-[var(--terminal-surface)] p-3">
                    <div className="text-[8px] font-mono uppercase tracking-widest text-muted-foreground">
                      Status
                    </div>
                    <div className="mt-1 text-sm font-mono font-bold text-primary">
                      {extractionResult.status}
                    </div>
                  </div>
                  <div className="rounded-lg border border-[var(--terminal-border)] bg-[var(--terminal-surface)] p-3">
                    <div className="text-[8px] font-mono uppercase tracking-widest text-muted-foreground">
                      Papers
                    </div>
                    <div className="mt-1 text-sm font-mono font-bold text-foreground">
                      {extractionResult.processed_count}
                    </div>
                  </div>
                  <div className="rounded-lg border border-[var(--terminal-border)] bg-[var(--terminal-surface)] p-3">
                    <div className="text-[8px] font-mono uppercase tracking-widest text-muted-foreground">
                      Enabled Features
                    </div>
                    <div className="mt-1 text-sm font-mono font-bold text-[var(--amber-gold)]">
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

                <div className="max-h-[480px] space-y-3 overflow-y-auto pr-1 terminal-scrollbar">
                  {extractionResult.results.map((result) => {
                    const featureKeys = Object.keys(result.features || {});
                    const hasFailed = result.extraction_status !== 'completed';

                    return (
                      <div
                        key={result.paper_id}
                        className={cn(
                          'rounded-lg border p-3',
                          hasFailed
                            ? 'border-red-900 bg-red-950/70'
                            : 'border-[var(--terminal-border)] bg-[var(--terminal-surface)]'
                        )}
                      >
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div className="min-w-0">
                            <div className="truncate text-xs font-mono font-bold text-foreground">
                              {result.title || result.paper_id}
                            </div>
                            <div className="mt-1 text-[10px] font-mono text-muted-foreground">
                              {result.paper_id}
                            </div>
                          </div>
                          <span
                            className={cn(
                              'rounded border px-2 py-0.5 text-[9px] font-mono uppercase tracking-wide',
                              hasFailed
                                ? 'border-red-800 text-red-300'
                                : 'border-primary/25 text-primary'
                            )}
                          >
                            {result.extraction_status}
                          </span>
                        </div>

                        {!hasFailed && featureKeys.length > 0 && (
                          <div className="mt-2 flex flex-wrap gap-1.5">
                            {featureKeys.map((key) => (
                              <span
                                key={key}
                                className="rounded border border-[var(--terminal-border)] bg-[var(--terminal-bg)] px-2 py-0.5 text-[9px] font-mono uppercase text-muted-foreground"
                              >
                                {key}
                              </span>
                            ))}
                          </div>
                        )}

                        {result.error && (
                          <div className="mt-2 text-[10px] font-mono text-red-300">
                            {result.error}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : (
              <div className="flex min-h-[280px] flex-col items-center justify-center text-center opacity-50">
                <Brain
                  className="mb-3 h-8 w-8 text-muted-foreground"
                  aria-hidden="true"
                />
                <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground">
                  Extraction results will appear here
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
