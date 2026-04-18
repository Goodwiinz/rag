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
        <h3 className="flex items-center gap-2 text-sm font-mono font-bold uppercase tracking-tight text-[#E5E7EB]">
          <Brain className="h-4 w-4 text-[#FFB700]" aria-hidden="true" />
          Extract Research Signals
        </h3>
        <p className="text-[11px] font-mono leading-relaxed text-[#6B7280]">
          Extract entities, topics, keyphrases, citations, and summaries for
          specific papers, then optionally sync to the knowledge graph.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
        <div className="space-y-4 xl:col-span-5">
          <div className="space-y-4 rounded-xl border border-[#1A1A1A] bg-[#0A0A0A]/50 p-4">
            <div className="space-y-2">
              <label
                htmlFor="extract-paper-ids"
                className="text-[10px] font-mono font-bold uppercase tracking-widest text-[#9CA3AF]"
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
                className="w-full rounded-lg border border-[#1A1A1A] bg-[#111111] p-3 font-mono text-xs text-[#E5E7EB] placeholder:text-[#6B7280] focus:border-[#00FF9F]/50 focus:outline-none"
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
                  'bg-[#FFB700]/20 text-[#FFB700] hover:bg-[#FFB700]/30 disabled:cursor-not-allowed disabled:opacity-45'
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
                className="rounded-lg border border-[#1A1A1A] px-4 py-2.5 text-[11px] font-mono font-bold uppercase text-[#6B7280] hover:bg-[#151515] disabled:cursor-not-allowed disabled:opacity-45"
              >
                Clear
              </button>
            </div>
          </div>

          <div className="rounded-xl border border-[#1A1A1A] bg-[#0A0A0A]/50 p-4">
            <div className="text-[9px] font-mono uppercase tracking-widest text-[#6B7280]">
              Valid Paper IDs
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {parsedExtractIds.length > 0 ? (
                parsedExtractIds.slice(0, 20).map((paperId) => (
                  <span
                    key={paperId}
                    className="rounded border border-[#1A1A1A] bg-[#111111] px-2 py-0.5 text-[9px] font-mono text-[#9CA3AF]"
                  >
                    {paperId}
                  </span>
                ))
              ) : (
                <span className="text-[10px] font-mono text-[#6B7280]">
                  No paper IDs entered yet.
                </span>
              )}
            </div>

            {invalidExtractIds.length > 0 && (
              <div className="mt-3 rounded-lg border border-[#6B2A2A] bg-[#2B1111]/70 p-2.5">
                <div className="text-[9px] font-mono uppercase tracking-widest text-[#FFAEAE]">
                  Invalid IDs ({invalidExtractIds.length})
                </div>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {invalidExtractIds.slice(0, 12).map((paperId) => (
                    <span
                      key={paperId}
                      className="rounded border border-[#A83A3A] bg-[#3A1717] px-2 py-0.5 text-[9px] font-mono text-[#FFAEAE]"
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
          <div className="rounded-xl border border-[#1A1A1A] bg-[#0A0A0A] p-5">
            <div className="mb-4 flex items-center justify-between border-b border-[#1A1A1A] pb-3">
              <span className="text-[9px] font-mono font-bold uppercase tracking-widest text-[#9CA3AF]">
                Extraction Results
              </span>
              <span className="text-[10px] font-mono text-[#6B7280]">
                {extractionResult
                  ? `${extractionResult.processed_count} processed`
                  : 'Awaiting run'}
              </span>
            </div>

            {extractionResult ? (
              <div className="space-y-4">
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                  <div className="rounded-lg border border-[#1A1A1A] bg-[#111111] p-3">
                    <div className="text-[8px] font-mono uppercase tracking-widest text-[#6B7280]">
                      Status
                    </div>
                    <div className="mt-1 text-sm font-mono font-bold text-[#00FF9F]">
                      {extractionResult.status}
                    </div>
                  </div>
                  <div className="rounded-lg border border-[#1A1A1A] bg-[#111111] p-3">
                    <div className="text-[8px] font-mono uppercase tracking-widest text-[#6B7280]">
                      Papers
                    </div>
                    <div className="mt-1 text-sm font-mono font-bold text-[#E5E7EB]">
                      {extractionResult.processed_count}
                    </div>
                  </div>
                  <div className="rounded-lg border border-[#1A1A1A] bg-[#111111] p-3">
                    <div className="text-[8px] font-mono uppercase tracking-widest text-[#6B7280]">
                      Enabled Features
                    </div>
                    <div className="mt-1 text-sm font-mono font-bold text-[#FFB700]">
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
                            ? 'border-[#6B2A2A] bg-[#2B1111]/70'
                            : 'border-[#1A1A1A] bg-[#111111]'
                        )}
                      >
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div className="min-w-0">
                            <div className="truncate text-xs font-mono font-bold text-[#E5E7EB]">
                              {result.title || result.paper_id}
                            </div>
                            <div className="mt-1 text-[10px] font-mono text-[#6B7280]">
                              {result.paper_id}
                            </div>
                          </div>
                          <span
                            className={cn(
                              'rounded border px-2 py-0.5 text-[9px] font-mono uppercase tracking-wide',
                              hasFailed
                                ? 'border-[#A83A3A] text-[#FFAEAE]'
                                : 'border-[#00FF9F]/25 text-[#00FF9F]'
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
                                className="rounded border border-[#1A1A1A] bg-[#0A0A0A] px-2 py-0.5 text-[9px] font-mono uppercase text-[#9CA3AF]"
                              >
                                {key}
                              </span>
                            ))}
                          </div>
                        )}

                        {result.error && (
                          <div className="mt-2 text-[10px] font-mono text-[#FFAEAE]">
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
                  className="mb-3 h-8 w-8 text-[#6B7280]"
                  aria-hidden="true"
                />
                <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-[#6B7280]">
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
