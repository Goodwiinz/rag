'use client';

import { cn } from '@/lib/utils';
import { api } from '@/services/api-client';
import { useAuthStore } from '@/stores/authStore';
import { AnimatePresence, motion } from 'framer-motion';
import {
  Activity,
  ArrowRight,
  BarChart3,
  Brain,
  Loader2,
  LogIn,
  Search,
  ShieldCheck,
  TrendingUp,
  Upload,
} from 'lucide-react';
import Link from 'next/link';
import React, { useEffect, useMemo, useRef, useState } from 'react';

import { ProgressBar } from './ArxivControls';
import {
  CORE_AI_CATEGORIES,
  ExtractionResult,
  getErrorMessage,
  getArxivTrackingErrorMessage,
  IngestionResult,
  POPULAR_CATEGORIES,
  splitValidAndInvalidPaperIds,
  StatsResult,
  TrackResult,
  ArXivPaper,
} from './arxivTypes';
import { ExtractTab } from './tabs/ExtractTab';
import { IngestTab } from './tabs/IngestTab';
import { StatsTab } from './tabs/StatsTab';
import { TrackingTab } from './tabs/TrackingTab';

type TabId = 'tracking' | 'ingest' | 'extract' | 'stats';

export default function ArxivManagement() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const isAuthLoading = useAuthStore((state) => state.isLoading);
  const [isTracking, setIsTracking] = useState(false);
  const [isIngesting, setIsIngesting] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);
  const [isStatsLoading, setIsStatsLoading] = useState(false);
  const [statsError, setStatsError] = useState('');
  const [trackingResult, setTrackingResult] = useState<TrackResult | null>(
    null
  );
  const [stats, setStats] = useState<StatsResult | null>(null);
  const [extractionResult, setExtractionResult] =
    useState<ExtractionResult | null>(null);
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState('');
  const [activeTab, setActiveTab] = useState<TabId>('tracking');
  const hasAppliedGuestDefault = useRef(false);

  const [selectedCategories, setSelectedCategories] = useState<string[]>([
    'cs.AI',
    'cs.LG',
    'cs.CV',
    'quant-ph',
  ]);
  const [daysBack, setDaysBack] = useState(1);
  const [maxResults, setMaxResults] = useState(50);
  const [updateDatabase, setUpdateDatabase] = useState(true);
  const [extractContentOnIngest, setExtractContentOnIngest] = useState(true);
  const [downloadPdfs, setDownloadPdfs] = useState(false);
  const [useCategoryFilterForSearch, setUseCategoryFilterForSearch] =
    useState(true);

  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<ArXivPaper[] | null>(null);
  const [selectedPaperIds, setSelectedPaperIds] = useState<string[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [ingestionResult, setIngestionResult] =
    useState<IngestionResult | null>(null);

  const [extractPaperIds, setExtractPaperIds] = useState('');
  const [extractTopics, setExtractTopics] = useState(true);
  const [extractKeyphrases, setExtractKeyphrases] = useState(true);
  const [extractCitations, setExtractCitations] = useState(true);
  const [extractSummaries, setExtractSummaries] = useState(true);
  const [updateKG, setUpdateKG] = useState(true);
  const [extractEntities, setExtractEntities] = useState(true);

  const tabs = [
    { id: 'tracking' as const, label: 'Track changes', icon: TrendingUp },
    { id: 'ingest' as const, label: 'Ingest papers', icon: Upload },
    { id: 'extract' as const, label: 'Extract features', icon: Brain },
    { id: 'stats' as const, label: 'Statistics', icon: BarChart3 },
  ];

  const parsedPaperIdState = useMemo(
    () => splitValidAndInvalidPaperIds(extractPaperIds),
    [extractPaperIds]
  );
  const parsedExtractIds = parsedPaperIdState.validIds;
  const invalidExtractIds = parsedPaperIdState.invalidIds;
  const isAnyOperationRunning =
    isTracking || isSearching || isIngesting || isExtracting;
  const canSelectAllResults = Boolean(
    searchResults && selectedPaperIds.length < searchResults.length
  );
  const hasMessageError = message.startsWith('ERROR:');
  const isGuest = !isAuthenticated && !isAuthLoading;
  const hasExtractionFeaturesEnabled =
    extractEntities ||
    extractTopics ||
    extractKeyphrases ||
    extractCitations ||
    extractSummaries;

  const fetchStats = async ({ showFeedback = false } = {}) => {
    setIsStatsLoading(true);
    setStatsError('');

    if (showFeedback) {
      setMessage('Refreshing tracking metrics…');
      setProgress(15);
    }

    try {
      const result = await api.get<StatsResult>('/arxiv/tracking/stats');
      setStats(result);

      if (showFeedback) {
        setProgress(100);
        setMessage('COMPLETED: Tracking metrics refreshed.');
      }
    } catch (error: any) {
      console.error('Failed to fetch stats:', error);
      const errorMessage = getErrorMessage(error);
      setStatsError(errorMessage);

      if (showFeedback) {
        setProgress(0);
        setMessage(`ERROR: ${errorMessage}`);
      }
    } finally {
      setIsStatsLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  useEffect(() => {
    if (isGuest && !hasAppliedGuestDefault.current) {
      setActiveTab('ingest');
      hasAppliedGuestDefault.current = true;
    }
  }, [isGuest]);

  const toggleCategory = (category: string) => {
    setSelectedCategories((prev) =>
      prev.includes(category)
        ? prev.filter((item) => item !== category)
        : [...prev, category]
    );
  };

  const applyCategoryPreset = (preset: 'core' | 'all' | 'clear') => {
    if (preset === 'core') {
      setSelectedCategories(
        CORE_AI_CATEGORIES.filter((cat) => POPULAR_CATEGORIES.includes(cat))
      );
      return;
    }

    if (preset === 'all') {
      setSelectedCategories(POPULAR_CATEGORIES);
      return;
    }

    setSelectedCategories([]);
  };

  const handleTrackChanges = async () => {
    if (isAnyOperationRunning || selectedCategories.length === 0) {
      return;
    }

    setIsTracking(true);
    setTrackingResult(null);
    setMessage(`Tracking changes for ${selectedCategories.length} categories…`);
    setProgress(10);

    try {
      setProgress(30);
      const result = await api.post<TrackResult>(
        '/arxiv/tracking/track-categories',
        {
          categories: selectedCategories,
          days_back: daysBack,
          update_database: updateDatabase,
        },
        { timeout: 300000 }
      );

      setProgress(75);
      setTrackingResult(result);

      if (result.result.applied && updateDatabase) {
        setMessage(
          `COMPLETED: Database updated with ${result.result.summary.new} new papers.`
        );
      } else {
        setMessage(
          `COMPLETED: Found ${result.result.summary.new} new and ${result.result.summary.updated} updated papers.`
        );
      }

      setProgress(100);
      await fetchStats();
    } catch (error: any) {
      console.error('Tracking failed:', error);
      setProgress(0);
      setMessage(`ERROR: ${getArxivTrackingErrorMessage(error)}`);
    } finally {
      setIsTracking(false);
    }
  };

  const handleSearchPapers = async () => {
    if (isAnyOperationRunning || !searchQuery.trim()) {
      return;
    }

    setIsSearching(true);
    setIngestionResult(null);
    setMessage(`Searching arXiv for "${searchQuery}"…`);
    setProgress(10);
    setSearchResults(null);
    setSelectedPaperIds([]);

    try {
      setProgress(40);
      const results = await api.post<ArXivPaper[]>(
        '/arxiv/search',
        {
          query: searchQuery.trim(),
          max_results: maxResults,
          categories:
            useCategoryFilterForSearch && selectedCategories.length > 0
              ? selectedCategories
              : null,
        },
        { timeout: 300000 }
      );

      setProgress(100);
      setSearchResults(results);
      setMessage(`Found ${results.length} matching papers.`);
    } catch (error: any) {
      console.error('Search failed:', error);
      setProgress(0);
      setMessage(`ERROR: ${getErrorMessage(error)}`);
    } finally {
      setIsSearching(false);
    }
  };

  const togglePaperSelection = (paperId: string) => {
    setSelectedPaperIds((prev) =>
      prev.includes(paperId)
        ? prev.filter((id) => id !== paperId)
        : [...prev, paperId]
    );
  };

  const selectAllSearchResults = () => {
    if (!searchResults || searchResults.length === 0) {
      return;
    }

    setSelectedPaperIds(searchResults.map((paper) => paper.id));
  };

  const handleIngestSelected = async () => {
    if (isAnyOperationRunning || selectedPaperIds.length === 0) {
      return;
    }

    setIsIngesting(true);
    setIngestionResult(null);
    setMessage(
      `Queueing ingestion for ${selectedPaperIds.length} selected papers…`
    );
    setProgress(15);

    try {
      setProgress(45);
      const result = await api.post<IngestionResult>(
        '/arxiv/ingest',
        {
          paper_ids: selectedPaperIds,
          download_pdfs: downloadPdfs,
          extract_content: extractContentOnIngest,
          batch_size: Math.min(20, Math.max(1, selectedPaperIds.length)),
        },
        { timeout: 300000 }
      );

      setProgress(100);
      setIngestionResult(result);
      setMessage(
        `COMPLETED: ${result.paper_count} papers queued for background ingestion.`
      );
    } catch (error: any) {
      console.error('Ingestion failed:', error);
      setProgress(0);
      setMessage(`ERROR: ${getErrorMessage(error)}`);
    } finally {
      setIsIngesting(false);
    }
  };

  const handleExtractFeatures = async () => {
    if (isAnyOperationRunning) {
      return;
    }

    if (invalidExtractIds.length > 0) {
      const invalidPreview = invalidExtractIds.slice(0, 3).join(', ');
      const suffix = invalidExtractIds.length > 3 ? '…' : '';
      setMessage(
        `ERROR: Invalid arXiv IDs detected (${invalidExtractIds.length}): ${invalidPreview}${suffix}`
      );
      return;
    }

    if (parsedExtractIds.length === 0) {
      setMessage('ERROR: Add at least one paper ID before extraction.');
      return;
    }

    if (!hasExtractionFeaturesEnabled) {
      setMessage('ERROR: Enable at least one extraction option.');
      return;
    }

    setIsExtracting(true);
    setExtractionResult(null);
    setMessage(`Extracting features from ${parsedExtractIds.length} papers…`);
    setProgress(10);

    try {
      setProgress(35);
      const result = await api.post<ExtractionResult>(
        '/arxiv/extraction/extract-features',
        {
          paper_ids: parsedExtractIds,
          extract_entities: extractEntities,
          extract_topics: extractTopics,
          extract_citations: extractCitations,
          extract_keyphrases: extractKeyphrases,
          extract_summaries: extractSummaries,
          update_knowledge_graph: updateKG,
        },
        { timeout: 300000 }
      );

      setProgress(100);
      setExtractionResult(result);
      setMessage(
        `COMPLETED: Features extracted for ${result.processed_count} papers.`
      );
    } catch (error: any) {
      console.error('Feature extraction failed:', error);
      setProgress(0);
      setMessage(`ERROR: ${getErrorMessage(error)}`);
    } finally {
      setIsExtracting(false);
    }
  };

  const overviewSteps = [
    {
      key: 'search',
      icon: Search,
      title: 'Search',
      description: 'Explore papers, compare abstracts, and build a shortlist.',
      state: 'Ready',
    },
    {
      key: 'ingest',
      icon: Upload,
      title: 'Queue',
      description: 'Push selected papers into background ingestion jobs.',
      state: isGuest ? 'Sign in' : 'Ready',
    },
    {
      key: 'extract',
      icon: Brain,
      title: 'Extract',
      description:
        'Generate entities, topics, keyphrases, citations, and summaries.',
      state: isGuest ? 'Sign in' : 'Ready',
    },
  ];

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-6">
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.9fr)]">
        <section className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
          <div className="border-b border-border bg-muted/30 p-6">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                <Activity aria-hidden="true" className="h-6 w-6 text-primary" />
              </div>
              <div className="space-y-2">
                <h1 className="text-xl font-semibold text-foreground sm:text-2xl">
                  arXiv research
                </h1>
                <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
                  Search the public arXiv corpus, track category changes, and
                  push selected papers into your workspace ingestion and
                  extraction pipeline.
                </p>
                <div className="flex flex-wrap gap-2 pt-1">
                  <span className="inline-flex items-center gap-1.5 rounded-md border border-border bg-background px-2.5 py-1 text-xs font-medium text-muted-foreground">
                    <Search
                      aria-hidden="true"
                      className="h-3.5 w-3.5 text-primary"
                    />
                    Public search
                  </span>
                  <span className="inline-flex items-center gap-1.5 rounded-md border border-border bg-background px-2.5 py-1 text-xs font-medium text-muted-foreground">
                    <BarChart3
                      aria-hidden="true"
                      className="h-3.5 w-3.5 text-primary"
                    />
                    Tracking stats
                  </span>
                  <span className="inline-flex items-center gap-1.5 rounded-md border border-border bg-background px-2.5 py-1 text-xs font-medium text-muted-foreground">
                    <ShieldCheck
                      aria-hidden="true"
                      className="h-3.5 w-3.5 text-primary"
                    />
                    {isGuest
                      ? 'Workspace actions locked'
                      : 'Workspace actions ready'}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="grid gap-3 p-6 md:grid-cols-3">
            {overviewSteps.map((step) => {
              const StepIcon = step.icon;
              return (
                <div
                  key={step.key}
                  className="rounded-lg border border-border bg-muted/20 p-4"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="rounded-lg bg-muted p-2 text-primary">
                      <StepIcon aria-hidden="true" className="h-4 w-4" />
                    </div>
                    <span className="text-xs font-medium text-muted-foreground">
                      {step.state}
                    </span>
                  </div>
                  <div className="mt-4 space-y-1.5">
                    <p className="text-sm font-medium text-foreground">
                      {step.title}
                    </p>
                    <p className="text-xs leading-relaxed text-muted-foreground">
                      {step.description}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        <aside className="space-y-4">
          <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-xs font-medium text-muted-foreground">
                  Current mode
                </p>
                <p className="mt-1 text-lg font-semibold text-foreground">
                  {isGuest ? 'Discovery mode' : 'Workspace mode'}
                </p>
              </div>
              <span className="rounded-md border border-border bg-muted px-2.5 py-1 text-xs font-medium text-foreground">
                {isGuest ? 'Guest' : 'Authenticated'}
              </span>
            </div>

            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
              {isGuest
                ? 'Public search and tracking stats stay available without signing in. Queueing ingestion, extraction, and category scans remain tied to an authenticated workspace.'
                : 'All tracking, ingestion, and extraction actions are available in this workspace session.'}
            </p>

            <div className="mt-4 flex flex-wrap gap-2">
              {isGuest ? (
                <Link
                  href="/login"
                  className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-[var(--nous-helios)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                >
                  <LogIn aria-hidden="true" className="h-4 w-4" />
                  Sign in to unlock workspace
                </Link>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={() => setActiveTab('tracking')}
                    className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-[var(--nous-helios)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                  >
                    Run tracking workflow
                    <ArrowRight aria-hidden="true" className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => setActiveTab('ingest')}
                    className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:border-[var(--nous-helios)] hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                  >
                    Review search results
                  </button>
                </>
              )}
            </div>
          </div>

          {isStatsLoading && !stats && (
            <div
              role="status"
              aria-live="polite"
              className="grid grid-cols-2 gap-3"
            >
              {[0, 1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="rounded-xl border border-border bg-card px-4 py-3 shadow-sm"
                >
                  <div className="h-3 w-16 animate-pulse rounded bg-muted" />
                  <div className="mt-2 h-7 w-12 animate-pulse rounded bg-muted" />
                </div>
              ))}
              <span className="sr-only">Loading tracking metrics…</span>
            </div>
          )}

          {!isStatsLoading && !stats && statsError && (
            <div
              role="alert"
              className="flex flex-col items-start gap-3 rounded-xl border border-border bg-card px-4 py-3 shadow-sm"
            >
              <p className="text-sm text-foreground">
                Couldn&apos;t load tracking metrics. {statsError}
              </p>
              <button
                type="button"
                onClick={() => fetchStats()}
                className="rounded text-sm font-medium text-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              >
                Retry
              </button>
            </div>
          )}

          {stats && (
            <div className="grid grid-cols-2 gap-3">
              {[
                {
                  label: 'Tracked',
                  value: stats.statistics.total_papers_tracked,
                },
                {
                  label: 'Active',
                  value: stats.statistics.active_papers,
                },
                {
                  label: 'Categories',
                  value: stats.statistics.categories_tracked,
                },
                {
                  label: 'Deleted',
                  value: stats.statistics.deleted_papers,
                },
              ].map((item) => (
                <div
                  key={item.label}
                  className="min-w-[110px] rounded-xl border border-border bg-card px-4 py-3 shadow-sm"
                >
                  <div className="text-xs text-muted-foreground">
                    {item.label}
                  </div>
                  <div className="mt-1 text-2xl font-semibold text-foreground tabular-nums">
                    {item.value}
                  </div>
                </div>
              ))}
            </div>
          )}
        </aside>
      </div>

      <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
        <div className="border-b border-border bg-muted/30 px-3 py-2 sm:px-4">
          <div className="overflow-x-auto">
            <div
              className="flex min-w-max items-center gap-1"
              role="tablist"
              aria-label="ArXiv management sections"
            >
              {tabs.map((tab) => {
                const Icon = tab.icon;
                const isActive = activeTab === tab.id;

                return (
                  <button
                    key={tab.id}
                    id={`tab-${tab.id}`}
                    type="button"
                    role="tab"
                    aria-selected={isActive}
                    aria-controls={`panel-${tab.id}`}
                    onClick={() => setActiveTab(tab.id)}
                    className={cn(
                      'relative flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors',
                      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background',
                      isActive
                        ? 'border-primary text-primary'
                        : 'border-transparent text-muted-foreground hover:text-foreground'
                    )}
                  >
                    <Icon aria-hidden="true" className="h-4 w-4" />
                    {tab.label}
                  </button>
                );
              })}
            </div>
          </div>

          {(isTracking ||
            isSearching ||
            isIngesting ||
            isExtracting ||
            message) && (
            <div className="mt-3 space-y-2 rounded-lg border border-border bg-background p-3">
              {(isTracking || isSearching || isIngesting || isExtracting) && (
                <ProgressBar
                  value={progress}
                  label={
                    isTracking
                      ? 'Tracking progress'
                      : isSearching
                        ? 'Search progress'
                        : isIngesting
                          ? 'Ingestion progress'
                          : 'Extraction progress'
                  }
                />
              )}
              {message && (
                <div
                  role={hasMessageError ? 'alert' : undefined}
                  className={cn(
                    'flex items-start gap-2 rounded-md border px-3 py-2 text-sm leading-relaxed',
                    hasMessageError
                      ? 'border-[var(--nous-mars)]/40 bg-[var(--nous-mars)]/10 text-foreground'
                      : 'border-border bg-muted/40 text-muted-foreground'
                  )}
                >
                  {hasMessageError && (
                    <span
                      aria-hidden="true"
                      className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--nous-mars)]"
                    />
                  )}
                  <span>{message}</span>
                </div>
              )}
            </div>
          )}

          <div className="sr-only" aria-live="polite">
            {message}
          </div>
        </div>

        <div className="p-4 sm:p-6 lg:p-7">
          <AnimatePresence mode="wait">
            <motion.section
              key={activeTab}
              id={`panel-${activeTab}`}
              role="tabpanel"
              aria-labelledby={`tab-${activeTab}`}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
              className="min-h-[420px]"
            >
              {activeTab === 'tracking' && (
                <TrackingTab
                  isAuthenticated={isAuthenticated}
                  selectedCategories={selectedCategories}
                  daysBack={daysBack}
                  updateDatabase={updateDatabase}
                  popularCategories={POPULAR_CATEGORIES}
                  isAnyOperationRunning={isAnyOperationRunning}
                  isTracking={isTracking}
                  isStatsLoading={isStatsLoading}
                  trackingResult={trackingResult}
                  onApplyCategoryPreset={applyCategoryPreset}
                  onToggleCategory={toggleCategory}
                  onDaysBackChange={setDaysBack}
                  onUpdateDatabaseChange={setUpdateDatabase}
                  onTrackChanges={handleTrackChanges}
                  onRefreshMetrics={() => fetchStats({ showFeedback: true })}
                />
              )}

              {activeTab === 'ingest' && (
                <IngestTab
                  isAuthenticated={isAuthenticated}
                  searchQuery={searchQuery}
                  maxResults={maxResults}
                  useCategoryFilterForSearch={useCategoryFilterForSearch}
                  selectedCategoriesCount={selectedCategories.length}
                  extractContentOnIngest={extractContentOnIngest}
                  downloadPdfs={downloadPdfs}
                  isAnyOperationRunning={isAnyOperationRunning}
                  isSearching={isSearching}
                  selectedPaperIds={selectedPaperIds}
                  isIngesting={isIngesting}
                  searchResults={searchResults}
                  canSelectAllResults={canSelectAllResults}
                  ingestionResult={ingestionResult}
                  onSearchQueryChange={setSearchQuery}
                  onMaxResultsChange={setMaxResults}
                  onUseCategoryFilterChange={setUseCategoryFilterForSearch}
                  onExtractContentChange={setExtractContentOnIngest}
                  onDownloadPdfsChange={setDownloadPdfs}
                  onSearchPapers={handleSearchPapers}
                  onClearSearch={() => {
                    setSearchResults(null);
                    setSelectedPaperIds([]);
                    setSearchQuery('');
                  }}
                  onIngestSelected={handleIngestSelected}
                  onSendIdsToExtract={() => {
                    if (selectedPaperIds.length > 0) {
                      setExtractPaperIds(selectedPaperIds.join('\n'));
                      setActiveTab('extract');
                    }
                  }}
                  onSelectAllSearchResults={selectAllSearchResults}
                  onClearSelectedPaperIds={() => setSelectedPaperIds([])}
                  onTogglePaperSelection={togglePaperSelection}
                />
              )}

              {activeTab === 'extract' && (
                <ExtractTab
                  isAuthenticated={isAuthenticated}
                  extractPaperIds={extractPaperIds}
                  parsedExtractIds={parsedExtractIds}
                  invalidExtractIds={invalidExtractIds}
                  isAnyOperationRunning={isAnyOperationRunning}
                  isExtracting={isExtracting}
                  extractionResult={extractionResult}
                  extractEntities={extractEntities}
                  extractTopics={extractTopics}
                  extractKeyphrases={extractKeyphrases}
                  extractCitations={extractCitations}
                  extractSummaries={extractSummaries}
                  updateKG={updateKG}
                  onExtractPaperIdsChange={setExtractPaperIds}
                  onExtractEntitiesChange={setExtractEntities}
                  onExtractTopicsChange={setExtractTopics}
                  onExtractKeyphrasesChange={setExtractKeyphrases}
                  onExtractCitationsChange={setExtractCitations}
                  onExtractSummariesChange={setExtractSummaries}
                  onUpdateKGChange={setUpdateKG}
                  onExtractFeatures={handleExtractFeatures}
                  onClearExtract={() => {
                    setExtractPaperIds('');
                    setExtractionResult(null);
                  }}
                />
              )}

              {activeTab === 'stats' && (
                <StatsTab
                  stats={stats}
                  statsError={statsError}
                  isAnyOperationRunning={isAnyOperationRunning}
                  isStatsLoading={isStatsLoading}
                  onRefresh={() => fetchStats({ showFeedback: true })}
                />
              )}
            </motion.section>
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
