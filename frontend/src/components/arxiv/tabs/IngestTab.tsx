import { cn } from '@/lib/utils';
import {
  Brain,
  CheckSquare,
  Database,
  Loader2,
  Search,
  Square,
  Terminal,
  Upload,
} from 'lucide-react';
import React from 'react';

import { CustomSlider, ToggleSwitch } from '../arxivControls';
import { ArXivPaper, IngestionResult } from '../arxivTypes';

interface IngestTabProps {
  searchQuery: string;
  maxResults: number;
  useCategoryFilterForSearch: boolean;
  selectedCategoriesCount: number;
  extractContentOnIngest: boolean;
  downloadPdfs: boolean;
  isAnyOperationRunning: boolean;
  isSearching: boolean;
  selectedPaperIds: string[];
  isIngesting: boolean;
  searchResults: ArXivPaper[] | null;
  canSelectAllResults: boolean;
  ingestionResult: IngestionResult | null;
  onSearchQueryChange: (value: string) => void;
  onMaxResultsChange: (value: number) => void;
  onUseCategoryFilterChange: (checked: boolean) => void;
  onExtractContentChange: (checked: boolean) => void;
  onDownloadPdfsChange: (checked: boolean) => void;
  onSearchPapers: () => void;
  onClearSearch: () => void;
  onIngestSelected: () => void;
  onSendIdsToExtract: () => void;
  onSelectAllSearchResults: () => void;
  onClearSelectedPaperIds: () => void;
  onTogglePaperSelection: (paperId: string) => void;
}

export function IngestTab({
  searchQuery,
  maxResults,
  useCategoryFilterForSearch,
  selectedCategoriesCount,
  extractContentOnIngest,
  downloadPdfs,
  isAnyOperationRunning,
  isSearching,
  selectedPaperIds,
  isIngesting,
  searchResults,
  canSelectAllResults,
  ingestionResult,
  onSearchQueryChange,
  onMaxResultsChange,
  onUseCategoryFilterChange,
  onExtractContentChange,
  onDownloadPdfsChange,
  onSearchPapers,
  onClearSearch,
  onIngestSelected,
  onSendIdsToExtract,
  onSelectAllSearchResults,
  onClearSelectedPaperIds,
  onTogglePaperSelection,
}: IngestTabProps) {
  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h3 className="flex items-center gap-2 text-sm font-mono font-bold uppercase tracking-tight text-[#E5E7EB]">
          <Upload className="h-4 w-4 text-[#00D4FF]" aria-hidden="true" />
          Search and Queue Ingestion
        </h3>
        <p className="text-[11px] font-mono leading-relaxed text-[#6B7280]">
          Search by topic, select relevant papers, and queue ingestion in one
          flow.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
        <div className="space-y-4 xl:col-span-5">
          <div className="space-y-4 rounded-xl border border-[#1A1A1A] bg-[#0A0A0A]/50 p-4">
            <div className="space-y-2">
              <label
                htmlFor="arxiv-query"
                className="text-[10px] font-mono font-bold uppercase tracking-widest text-[#9CA3AF]"
              >
                Search Query
              </label>
              <div className="relative">
                <Search
                  className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#6B7280]"
                  aria-hidden="true"
                />
                <input
                  id="arxiv-query"
                  name="arxivQuery"
                  type="text"
                  value={searchQuery}
                  onChange={(e) => onSearchQueryChange(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && onSearchPapers()}
                  placeholder="transformer interpretability…"
                  autoComplete="off"
                  className="w-full rounded-lg border border-[#1A1A1A] bg-[#111111] py-2.5 pl-10 pr-3 font-mono text-xs text-[#E5E7EB] placeholder:text-[#6B7280] focus:border-[#00FF9F]/50 focus:outline-none"
                />
              </div>
            </div>

            <CustomSlider
              label="Maximum Results"
              value={maxResults}
              onChange={onMaxResultsChange}
              min={1}
              max={100}
              step={1}
            />

            <div className="space-y-2 rounded-lg border border-dashed border-[#1A1A1A] bg-[#0A0A0A]/40 p-3">
              <ToggleSwitch
                checked={useCategoryFilterForSearch}
                onCheckedChange={onUseCategoryFilterChange}
                label={`Filter by selected categories (${selectedCategoriesCount})`}
              />
              <ToggleSwitch
                checked={extractContentOnIngest}
                onCheckedChange={onExtractContentChange}
                label="Extract Text Content"
              />
              <ToggleSwitch
                checked={downloadPdfs}
                onCheckedChange={onDownloadPdfsChange}
                label="Download Source PDF"
              />
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={onSearchPapers}
                disabled={isAnyOperationRunning || !searchQuery.trim()}
                className={cn(
                  'inline-flex flex-1 items-center justify-center gap-2 rounded-lg border px-4 py-2.5 text-[11px] font-mono font-bold uppercase transition-colors',
                  'border-[#00D4FF]/30 bg-[#00D4FF]/10 text-[#00D4FF] hover:bg-[#00D4FF]/20 disabled:cursor-not-allowed disabled:opacity-45'
                )}
              >
                {isSearching ? (
                  <Loader2
                    className="h-4 w-4 animate-spin"
                    aria-hidden="true"
                  />
                ) : (
                  <Search className="h-4 w-4" aria-hidden="true" />
                )}
                Search Papers
              </button>
              <button
                type="button"
                onClick={onClearSearch}
                disabled={isAnyOperationRunning}
                className="rounded-lg border border-[#1A1A1A] px-4 py-2.5 text-[11px] font-mono font-bold uppercase text-[#6B7280] hover:bg-[#151515] disabled:cursor-not-allowed disabled:opacity-45"
              >
                Clear Search
              </button>
            </div>
          </div>

          <div className="space-y-3 rounded-xl border border-[#1A1A1A] bg-[#0A0A0A]/50 p-4">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-mono uppercase tracking-widest text-[#9CA3AF]">
                Selected Papers
              </span>
              <span className="text-xs font-mono font-bold text-[#00FF9F]">
                {selectedPaperIds.length}
              </span>
            </div>

            <button
              type="button"
              onClick={onIngestSelected}
              disabled={isAnyOperationRunning || selectedPaperIds.length === 0}
              className={cn(
                'inline-flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-[11px] font-mono font-bold uppercase transition-colors',
                'bg-[#00FF9F] text-[#0A0A0A] hover:bg-[#00CC7F] disabled:cursor-not-allowed disabled:opacity-45'
              )}
            >
              {isIngesting ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <Database className="h-4 w-4" aria-hidden="true" />
              )}
              Queue Ingestion
            </button>

            <button
              type="button"
              onClick={onSendIdsToExtract}
              disabled={isAnyOperationRunning || selectedPaperIds.length === 0}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-[#1A1A1A] px-4 py-2.5 text-[11px] font-mono font-bold uppercase text-[#6B7280] hover:bg-[#151515] disabled:cursor-not-allowed disabled:opacity-45"
            >
              <Brain className="h-4 w-4" aria-hidden="true" />
              Send IDs to Extract
            </button>

            {ingestionResult && (
              <div className="rounded-lg border border-[#00FF9F]/25 bg-[#00FF9F]/5 p-3 text-[10px] font-mono leading-relaxed text-[#9CA3AF]">
                {ingestionResult.message} ({ingestionResult.paper_count} papers)
              </div>
            )}
          </div>
        </div>

        <div className="space-y-4 xl:col-span-7">
          <div className="rounded-xl border border-[#1A1A1A] bg-[#0A0A0A]/40 p-4">
            <div className="mb-3 flex items-center justify-between">
              <h4 className="text-[10px] font-mono font-bold uppercase tracking-widest text-[#9CA3AF]">
                Search Results
              </h4>
              {searchResults && searchResults.length > 0 && (
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={onSelectAllSearchResults}
                    disabled={!canSelectAllResults || isAnyOperationRunning}
                    className="rounded-md border border-[#1A1A1A] px-2 py-1 text-[9px] font-mono uppercase tracking-wide text-[#9CA3AF] hover:bg-[#151515] disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    Select All
                  </button>
                  <button
                    type="button"
                    onClick={onClearSelectedPaperIds}
                    disabled={
                      isAnyOperationRunning || selectedPaperIds.length === 0
                    }
                    className="rounded-md border border-[#1A1A1A] px-2 py-1 text-[9px] font-mono uppercase tracking-wide text-[#9CA3AF] hover:bg-[#151515] disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    Clear
                  </button>
                  <span className="text-[10px] font-mono text-[#6B7280]">
                    {selectedPaperIds.length}/{searchResults.length}
                  </span>
                </div>
              )}
            </div>

            {searchResults ? (
              searchResults.length > 0 ? (
                <div className="max-h-[560px] space-y-3 overflow-y-auto pr-1 terminal-scrollbar">
                  {searchResults.map((paper) => {
                    const isSelected = selectedPaperIds.includes(paper.id);

                    return (
                      <button
                        key={paper.id}
                        type="button"
                        aria-pressed={isSelected}
                        onClick={() => onTogglePaperSelection(paper.id)}
                        className={cn(
                          'w-full rounded-xl border p-4 text-left transition-colors touch-manipulation',
                          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00FF9F]/60 focus-visible:ring-offset-2 focus-visible:ring-offset-[#0A0A0A]',
                          isSelected
                            ? 'border-[#00FF9F]/45 bg-[#00FF9F]/10'
                            : 'border-[#1A1A1A] bg-[#0A0A0A] hover:border-[#333333]'
                        )}
                      >
                        <div className="flex items-start gap-3">
                          <div
                            className={cn(
                              'mt-0.5 rounded border p-1.5',
                              isSelected
                                ? 'border-[#00FF9F]/45 text-[#00FF9F]'
                                : 'border-[#1A1A1A] text-[#6B7280]'
                            )}
                            aria-hidden="true"
                          >
                            {isSelected ? (
                              <CheckSquare className="h-4 w-4" />
                            ) : (
                              <Square className="h-4 w-4" />
                            )}
                          </div>

                          <div className="min-w-0 flex-1 space-y-2">
                            <h5 className="line-clamp-2 text-xs font-mono font-bold text-[#E5E7EB]">
                              {paper.title}
                            </h5>
                            <p className="line-clamp-2 text-[10px] font-mono leading-relaxed text-[#6B7280]">
                              {paper.abstract}
                            </p>
                            <div className="flex flex-wrap gap-1.5">
                              <span className="rounded border border-[#1A1A1A] bg-[#111111] px-2 py-0.5 text-[9px] font-mono text-[#00D4FF]">
                                {paper.id}
                              </span>
                              {paper.categories.slice(0, 3).map((category) => (
                                <span
                                  key={category}
                                  className="rounded border border-[#1A1A1A] bg-[#111111] px-2 py-0.5 text-[9px] font-mono text-[#FFB700]"
                                >
                                  {category}
                                </span>
                              ))}
                              {paper.authors?.[0] && (
                                <span className="rounded border border-[#1A1A1A] bg-[#111111] px-2 py-0.5 text-[9px] font-mono text-[#6B7280]">
                                  {paper.authors[0]}
                                  {paper.authors.length > 1
                                    ? ` +${paper.authors.length - 1}`
                                    : ''}
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              ) : (
                <div className="rounded-lg border border-[#1A1A1A] bg-[#0A0A0A]/60 p-4 text-center text-[10px] font-mono text-[#6B7280]">
                  No results found for this query.
                </div>
              )
            ) : (
              <div className="rounded-lg border border-[#1A1A1A] bg-[#0A0A0A]/60 p-6 text-center">
                <Terminal
                  className="mx-auto mb-2 h-6 w-6 text-[#6B7280]"
                  aria-hidden="true"
                />
                <p className="text-[10px] font-mono uppercase tracking-widest text-[#6B7280]">
                  Run a search to build your ingestion list
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
