import { cn } from '@/lib/utils';
import {
  Brain,
  CheckSquare,
  Database,
  Lock,
  Loader2,
  LogIn,
  Search,
  Square,
  Upload,
} from 'lucide-react';
import React from 'react';

import { CustomSlider, ToggleSwitch } from '../ArxivControls';
import { ArXivPaper, IngestionResult } from '../arxivTypes';

interface IngestTabProps {
  isAuthenticated: boolean;
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
  isAuthenticated,
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
        <h3 className="flex items-center gap-2 text-base font-semibold text-foreground">
          <Upload className="h-4 w-4 text-primary" aria-hidden="true" />
          Search and queue ingestion
        </h3>
        <p className="font-[family-name:var(--nous-font-body)] text-sm leading-relaxed text-muted-foreground">
          Search by topic, select relevant papers, and queue ingestion in one
          flow.
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
                Public search stays open
              </p>
              <p className="font-[family-name:var(--nous-font-body)] text-sm leading-relaxed text-muted-foreground">
                Search papers and review results without signing in. Sign in to
                queue ingestion, send IDs to extraction, and save work to your
                workspace.
              </p>
              <a
                href="/login"
                className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              >
                <LogIn className="h-3.5 w-3.5" aria-hidden="true" />
                Sign in to queue ingestion
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
                htmlFor="arxiv-query"
                className="text-sm font-medium text-foreground"
              >
                Search query
              </label>
              <div className="relative">
                <Search
                  className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
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
                  className="w-full rounded-lg border border-border bg-card py-2.5 pl-10 pr-3 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40"
                />
              </div>
            </div>

            <CustomSlider
              label="Maximum results"
              value={maxResults}
              onChange={onMaxResultsChange}
              min={1}
              max={100}
              step={1}
            />

            <div className="space-y-2 rounded-lg border border-border bg-card p-3">
              <ToggleSwitch
                checked={useCategoryFilterForSearch}
                onCheckedChange={onUseCategoryFilterChange}
                label={`Filter by selected categories (${selectedCategoriesCount})`}
              />
              <ToggleSwitch
                checked={extractContentOnIngest}
                onCheckedChange={onExtractContentChange}
                label="Extract text content"
              />
              <ToggleSwitch
                checked={downloadPdfs}
                onCheckedChange={onDownloadPdfsChange}
                label="Download source PDF"
              />
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={onSearchPapers}
                disabled={isAnyOperationRunning || !searchQuery.trim()}
                className={cn(
                  'inline-flex flex-1 items-center justify-center gap-2 rounded-lg border border-primary/40 bg-primary/10 px-4 py-2.5 text-sm font-medium text-primary transition-colors',
                  'hover:bg-primary/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40 focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-45'
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
                className="rounded-lg border border-border px-4 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40 focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-45"
              >
                Clear search
              </button>
            </div>
          </div>

          <div className="space-y-3 rounded-xl border border-border bg-background p-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-foreground">
                Selected papers
              </span>
              <span className="text-sm font-semibold tabular-nums text-foreground">
                {selectedPaperIds.length}
              </span>
            </div>

            <button
              type="button"
              onClick={onIngestSelected}
              disabled={
                !isAuthenticated ||
                isAnyOperationRunning ||
                selectedPaperIds.length === 0
              }
              className={cn(
                'inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition-colors',
                'hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40 focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-45'
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
              disabled={
                !isAuthenticated ||
                isAnyOperationRunning ||
                selectedPaperIds.length === 0
              }
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-border px-4 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40 focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-45"
            >
              <Brain className="h-4 w-4" aria-hidden="true" />
              Send IDs to extract
            </button>

            {!isAuthenticated && (
              <p className="rounded-lg border border-border bg-card p-3 font-[family-name:var(--nous-font-body)] text-sm leading-relaxed text-muted-foreground">
                Sign in to queue ingestion and extraction.
              </p>
            )}

            {ingestionResult && (
              <div className="rounded-lg border border-primary/30 bg-primary/5 p-3 text-sm leading-relaxed text-foreground">
                {ingestionResult.message} ({ingestionResult.paper_count} papers)
              </div>
            )}
          </div>
        </div>

        <div className="space-y-4 xl:col-span-7">
          <div className="rounded-xl border border-border bg-background p-4">
            <div className="mb-3 flex items-center justify-between">
              <h4 className="text-sm font-medium text-foreground">
                Search results
              </h4>
              {searchResults && searchResults.length > 0 && (
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={onSelectAllSearchResults}
                    disabled={!canSelectAllResults || isAnyOperationRunning}
                    className="rounded-md border border-border px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40 disabled:cursor-not-allowed disabled:opacity-40 sm:px-2 sm:py-1 sm:text-xs"
                  >
                    Select all
                  </button>
                  <button
                    type="button"
                    onClick={onClearSelectedPaperIds}
                    disabled={
                      isAnyOperationRunning || selectedPaperIds.length === 0
                    }
                    className="rounded-md border border-border px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40 disabled:cursor-not-allowed disabled:opacity-40 sm:px-2 sm:py-1 sm:text-xs"
                  >
                    Clear
                  </button>
                  <span className="text-xs tabular-nums text-muted-foreground">
                    {selectedPaperIds.length}/{searchResults.length}
                  </span>
                </div>
              )}
            </div>

            {searchResults ? (
              searchResults.length > 0 ? (
                <div className="max-h-[560px] space-y-3 overflow-y-auto pr-1 nous-scrollbar">
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
                          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40 focus-visible:ring-offset-2 focus-visible:ring-offset-background',
                          isSelected
                            ? 'border-primary/45 bg-primary/5'
                            : 'border-border bg-card hover:border-border'
                        )}
                      >
                        <div className="flex items-start gap-3">
                          <div
                            className={cn(
                              'mt-0.5 rounded border p-1.5',
                              isSelected
                                ? 'border-primary/45 text-primary'
                                : 'border-border text-muted-foreground'
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
                            <h5 className="line-clamp-2 text-sm font-medium text-foreground">
                              {paper.title}
                            </h5>
                            <p className="line-clamp-2 font-[family-name:var(--nous-font-body)] text-sm leading-relaxed text-muted-foreground">
                              {paper.abstract}
                            </p>
                            <div className="flex flex-wrap gap-1.5">
                              <span className="max-w-full break-all rounded border border-border bg-card px-2 py-0.5 font-[family-name:var(--nous-font-mono)] text-xs text-foreground">
                                {paper.id}
                              </span>
                              {paper.categories.slice(0, 3).map((category) => (
                                <span
                                  key={category}
                                  className="rounded border border-border bg-card px-2 py-0.5 text-xs text-muted-foreground"
                                >
                                  {category}
                                </span>
                              ))}
                              {paper.authors?.[0] && (
                                <span className="rounded border border-border bg-card px-2 py-0.5 text-xs text-muted-foreground">
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
                <div className="rounded-lg border border-border bg-card p-4 text-center text-sm text-muted-foreground">
                  No results found for this query.
                </div>
              )
            ) : (
              <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border bg-card p-8 text-center">
                <Search
                  className="h-6 w-6 text-muted-foreground"
                  aria-hidden="true"
                />
                <p className="text-sm text-muted-foreground">
                  Run a search to build your ingestion list.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
