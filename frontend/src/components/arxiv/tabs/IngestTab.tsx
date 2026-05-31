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
  Terminal,
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
        <h3 className="flex items-center gap-2 text-sm font-medium text-foreground">
          <Upload aria-hidden="true" className="h-4 w-4 text-primary" />
          Search and queue ingestion
        </h3>
        <p className="text-sm leading-relaxed text-muted-foreground">
          Search by topic, select relevant papers, and queue ingestion in one
          flow.
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
                Public search stays open
              </p>
              <p className="text-sm leading-relaxed text-muted-foreground">
                Search papers and review results without signing in. Sign in to
                queue ingestion, send IDs to extraction, and save work to your
                workspace.
              </p>
              <a
                href="/login"
                className="inline-flex items-center gap-2 rounded-md border border-border bg-background px-3 py-2 text-sm font-medium text-primary transition-colors hover:border-[var(--nous-helios)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              >
                <LogIn aria-hidden="true" className="h-3.5 w-3.5" />
                Sign in to queue ingestion
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
                htmlFor="arxiv-query"
                className="text-xs font-medium text-muted-foreground"
              >
                Search query
              </label>
              <div className="relative">
                <Search
                  aria-hidden="true"
                  className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
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
                  className="w-full rounded-lg border border-border bg-background py-2.5 pl-10 pr-3 text-sm text-foreground placeholder:text-muted-foreground transition-colors focus:border-primary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
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

            <div className="space-y-2 rounded-lg border border-dashed border-border bg-background/40 p-3">
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
                  'inline-flex flex-1 items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors',
                  'bg-primary text-primary-foreground hover:bg-[var(--nous-helios)] disabled:cursor-not-allowed disabled:opacity-45',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background'
                )}
              >
                {isSearching ? (
                  <Loader2
                    aria-hidden="true"
                    className="h-4 w-4 animate-spin"
                  />
                ) : (
                  <Search aria-hidden="true" className="h-4 w-4" />
                )}
                {isSearching ? 'Searching…' : 'Search papers'}
              </button>
              <button
                type="button"
                onClick={onClearSearch}
                disabled={isAnyOperationRunning}
                className="rounded-lg border border-border px-4 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:border-[var(--nous-helios)] hover:text-foreground disabled:cursor-not-allowed disabled:opacity-45 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              >
                Clear search
              </button>
            </div>
          </div>

          <div className="space-y-3 rounded-lg border border-border bg-muted/20 p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">
                Selected papers
              </span>
              <span className="text-sm font-medium text-foreground tabular-nums">
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
                'inline-flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors',
                'bg-primary text-primary-foreground hover:bg-[var(--nous-helios)] disabled:cursor-not-allowed disabled:opacity-45',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background'
              )}
            >
              {isIngesting ? (
                <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
              ) : (
                <Database aria-hidden="true" className="h-4 w-4" />
              )}
              {isIngesting ? 'Queueing…' : 'Queue ingestion'}
            </button>

            <button
              type="button"
              onClick={onSendIdsToExtract}
              disabled={
                !isAuthenticated ||
                isAnyOperationRunning ||
                selectedPaperIds.length === 0
              }
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-border px-4 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:border-[var(--nous-helios)] hover:text-foreground disabled:cursor-not-allowed disabled:opacity-45 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
              <Brain aria-hidden="true" className="h-4 w-4" />
              Send IDs to extract
            </button>

            {!isAuthenticated && (
              <div className="rounded-lg border border-border bg-background/40 p-3 text-sm leading-relaxed text-muted-foreground">
                Sign in to queue ingestion and extraction.
              </div>
            )}

            {ingestionResult && (
              <div className="rounded-lg border border-primary/25 bg-primary/5 p-3 text-sm leading-relaxed text-foreground">
                {ingestionResult.message} ({ingestionResult.paper_count} papers)
              </div>
            )}
          </div>
        </div>

        <div className="space-y-4 xl:col-span-7">
          <div className="rounded-lg border border-border bg-muted/20 p-4">
            <div className="mb-3 flex items-center justify-between">
              <h4 className="text-sm font-medium text-foreground">
                Search results
              </h4>
              {searchResults && searchResults.length > 0 && (
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={onSelectAllSearchResults}
                    disabled={!canSelectAllResults || isAnyOperationRunning}
                    className="rounded-md border border-border px-2.5 py-1 text-xs font-medium text-muted-foreground transition-colors hover:border-[var(--nous-helios)] hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                  >
                    Select all
                  </button>
                  <button
                    type="button"
                    onClick={onClearSelectedPaperIds}
                    disabled={
                      isAnyOperationRunning || selectedPaperIds.length === 0
                    }
                    className="rounded-md border border-border px-2.5 py-1 text-xs font-medium text-muted-foreground transition-colors hover:border-[var(--nous-helios)] hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                  >
                    Clear
                  </button>
                  <span className="text-xs text-muted-foreground tabular-nums">
                    {selectedPaperIds.length}/{searchResults.length}
                  </span>
                </div>
              )}
            </div>

            {searchResults ? (
              searchResults.length > 0 ? (
                <div className="max-h-[560px] space-y-3 overflow-y-auto pr-1">
                  {searchResults.map((paper) => {
                    const isSelected = selectedPaperIds.includes(paper.id);

                    return (
                      <button
                        key={paper.id}
                        type="button"
                        aria-pressed={isSelected}
                        onClick={() => onTogglePaperSelection(paper.id)}
                        className={cn(
                          'w-full rounded-lg border p-4 text-left transition-colors',
                          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background',
                          isSelected
                            ? 'border-primary/45 bg-primary/10'
                            : 'border-border bg-card hover:border-[var(--nous-helios)] hover:shadow-sm'
                        )}
                      >
                        <div className="flex items-start gap-3">
                          <div
                            className={cn(
                              'mt-0.5 rounded-md border p-1.5',
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
                            <p className="line-clamp-2 font-[var(--nous-font-body)] text-sm leading-relaxed text-muted-foreground">
                              {paper.abstract}
                            </p>
                            <div className="flex flex-wrap gap-1.5">
                              <span className="rounded border border-border bg-background px-2 py-0.5 font-[var(--nous-font-mono)] text-xs text-foreground">
                                {paper.id}
                              </span>
                              {paper.categories.slice(0, 3).map((category) => (
                                <span
                                  key={category}
                                  className="rounded border border-border bg-background px-2 py-0.5 font-[var(--nous-font-mono)] text-xs text-muted-foreground"
                                >
                                  {category}
                                </span>
                              ))}
                              {paper.authors?.[0] && (
                                <span className="rounded border border-border bg-background px-2 py-0.5 text-xs text-muted-foreground">
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
                <div className="rounded-lg border border-border bg-card p-6 text-center text-sm text-muted-foreground">
                  No papers matched this query. Try broader terms or turn off
                  the category filter.
                </div>
              )
            ) : (
              <div className="rounded-lg border border-border bg-card p-8 text-center">
                <div className="mx-auto mb-3 w-fit rounded-lg bg-muted p-3 text-muted-foreground">
                  <Terminal aria-hidden="true" className="h-5 w-5" />
                </div>
                <p className="text-sm font-medium text-foreground">
                  No search yet
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
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
