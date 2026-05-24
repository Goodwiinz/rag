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
        <h3 className="flex items-center gap-2 text-sm font-mono font-bold uppercase tracking-tight text-foreground">
          <Upload className="h-4 w-4 text-[var(--cyan)]" aria-hidden="true" />
          Search and Queue Ingestion
        </h3>
        <p className="text-[11px] font-mono leading-relaxed text-muted-foreground">
          Search by topic, select relevant papers, and queue ingestion in one
          flow.
        </p>
      </div>

      {!isAuthenticated && (
        <div className="rounded-xl border border-[var(--cyan)]/20 bg-[var(--cyan)]/5 p-4">
          <div className="flex items-start gap-3">
            <div className="rounded-lg border border-[var(--cyan)]/20 bg-[var(--terminal-bg)]/70 p-2">
              <Lock
                className="h-4 w-4 text-[var(--cyan)]"
                aria-hidden="true"
              />
            </div>
            <div className="space-y-2">
              <p className="text-xs font-mono font-bold uppercase tracking-wider text-foreground">
                Public search stays open
              </p>
              <p className="text-[11px] font-mono leading-relaxed text-muted-foreground">
                Search papers and review results without signing in. Sign in to
                queue ingestion, send IDs to extraction, and save work to your
                workspace.
              </p>
              <a
                href="/login"
                className="inline-flex items-center gap-2 rounded-md border border-[var(--cyan)]/20 bg-[var(--terminal-bg)]/70 px-3 py-2 text-[10px] font-mono font-bold uppercase tracking-wider text-[var(--cyan)] transition-colors hover:bg-[var(--cyan)]/10"
              >
                <LogIn className="h-3.5 w-3.5" aria-hidden="true" />
                Sign In To Queue Ingestion
              </a>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
        <div className="space-y-4 xl:col-span-5">
          <div className="space-y-4 rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-bg)]/50 p-4">
            <div className="space-y-2">
              <label
                htmlFor="arxiv-query"
                className="text-[10px] font-mono font-bold uppercase tracking-widest text-muted-foreground"
              >
                Search Query
              </label>
              <div className="relative">
                <Search
                  className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground"
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
                  className="w-full rounded-lg border border-[var(--terminal-border)] bg-[var(--terminal-surface)] py-2.5 pl-10 pr-3 font-mono text-xs text-foreground placeholder:text-muted-foreground focus:border-primary/50 focus:outline-none"
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

            <div className="space-y-2 rounded-lg border border-dashed border-[var(--terminal-border)] bg-[var(--terminal-bg)]/40 p-3">
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
                  'border-[var(--cyan)]/30 bg-[var(--cyan)]/10 text-[var(--cyan)] hover:bg-[var(--cyan)]/20 disabled:cursor-not-allowed disabled:opacity-45'
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
                className="rounded-lg border border-[var(--terminal-border)] px-4 py-2.5 text-[11px] font-mono font-bold uppercase text-muted-foreground hover:bg-[var(--terminal-surface)] disabled:cursor-not-allowed disabled:opacity-45"
              >
                Clear Search
              </button>
            </div>
          </div>

          <div className="space-y-3 rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-bg)]/50 p-4">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground">
                Selected Papers
              </span>
              <span className="text-xs font-mono font-bold text-primary">
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
                'inline-flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-[11px] font-mono font-bold uppercase transition-colors',
                'bg-primary text-background hover:bg-primary/80 disabled:cursor-not-allowed disabled:opacity-45'
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
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-[var(--terminal-border)] px-4 py-2.5 text-[11px] font-mono font-bold uppercase text-muted-foreground hover:bg-[var(--terminal-surface)] disabled:cursor-not-allowed disabled:opacity-45"
            >
              <Brain className="h-4 w-4" aria-hidden="true" />
              Send IDs to Extract
            </button>

            {!isAuthenticated && (
              <div className="rounded-lg border border-[var(--terminal-border)] bg-[var(--terminal-bg)]/40 p-3 text-[10px] font-mono leading-relaxed text-muted-foreground">
                Sign in to queue ingestion and extraction.
              </div>
            )}

            {ingestionResult && (
              <div className="rounded-lg border border-primary/25 bg-primary/5 p-3 text-[10px] font-mono leading-relaxed text-muted-foreground">
                {ingestionResult.message} ({ingestionResult.paper_count} papers)
              </div>
            )}
          </div>
        </div>

        <div className="space-y-4 xl:col-span-7">
          <div className="rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-bg)]/40 p-4">
            <div className="mb-3 flex items-center justify-between">
              <h4 className="text-[10px] font-mono font-bold uppercase tracking-widest text-muted-foreground">
                Search Results
              </h4>
              {searchResults && searchResults.length > 0 && (
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={onSelectAllSearchResults}
                    disabled={!canSelectAllResults || isAnyOperationRunning}
                    className="rounded-md border border-[var(--terminal-border)] px-2 py-1 text-[9px] font-mono uppercase tracking-wide text-muted-foreground hover:bg-[var(--terminal-surface)] disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    Select All
                  </button>
                  <button
                    type="button"
                    onClick={onClearSelectedPaperIds}
                    disabled={
                      isAnyOperationRunning || selectedPaperIds.length === 0
                    }
                    className="rounded-md border border-[var(--terminal-border)] px-2 py-1 text-[9px] font-mono uppercase tracking-wide text-muted-foreground hover:bg-[var(--terminal-surface)] disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    Clear
                  </button>
                  <span className="text-[10px] font-mono text-muted-foreground">
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
                          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60 focus-visible:ring-offset-2 focus-visible:ring-offset-background',
                          isSelected
                            ? 'border-primary/45 bg-primary/10'
                            : 'border-[var(--terminal-border)] bg-[var(--terminal-bg)] hover:border-[var(--terminal-border)]'
                        )}
                      >
                        <div className="flex items-start gap-3">
                          <div
                            className={cn(
                              'mt-0.5 rounded border p-1.5',
                              isSelected
                                ? 'border-primary/45 text-primary'
                                : 'border-[var(--terminal-border)] text-muted-foreground'
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
                            <h5 className="line-clamp-2 text-xs font-mono font-bold text-foreground">
                              {paper.title}
                            </h5>
                            <p className="line-clamp-2 text-[10px] font-mono leading-relaxed text-muted-foreground">
                              {paper.abstract}
                            </p>
                            <div className="flex flex-wrap gap-1.5">
                              <span className="rounded border border-[var(--terminal-border)] bg-[var(--terminal-surface)] px-2 py-0.5 text-[9px] font-mono text-[var(--cyan)]">
                                {paper.id}
                              </span>
                              {paper.categories.slice(0, 3).map((category) => (
                                <span
                                  key={category}
                                  className="rounded border border-[var(--terminal-border)] bg-[var(--terminal-surface)] px-2 py-0.5 text-[9px] font-mono text-[var(--amber-gold)]"
                                >
                                  {category}
                                </span>
                              ))}
                              {paper.authors?.[0] && (
                                <span className="rounded border border-[var(--terminal-border)] bg-[var(--terminal-surface)] px-2 py-0.5 text-[9px] font-mono text-muted-foreground">
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
                <div className="rounded-lg border border-[var(--terminal-border)] bg-[var(--terminal-bg)]/60 p-4 text-center text-[10px] font-mono text-muted-foreground">
                  No results found for this query.
                </div>
              )
            ) : (
              <div className="rounded-lg border border-[var(--terminal-border)] bg-[var(--terminal-bg)]/60 p-6 text-center">
                <Terminal
                  className="mx-auto mb-2 h-6 w-6 text-muted-foreground"
                  aria-hidden="true"
                />
                <p className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground">
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
