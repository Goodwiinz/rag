'use client';

import { cn } from '@/lib/utils';
import { apiClient } from '@/services/apiClient';
import { AnimatePresence, motion } from 'framer-motion';
import {
  Activity,
  BarChart3,
  Brain,
  Loader2,
  TrendingUp,
  Upload,
} from 'lucide-react';
import React, { useEffect, useMemo, useState } from 'react';

import { ProgressBar } from './arxivControls';
import {
  CORE_AI_CATEGORIES,
  ExtractionResult,
  getErrorMessage,
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
    { id: 'tracking' as const, label: 'Track Changes', icon: TrendingUp },
    { id: 'ingest' as const, label: 'Ingest Papers', icon: Upload },
    { id: 'extract' as const, label: 'Extract Features', icon: Brain },
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
      const result = await apiClient.get<StatsResult>('/arxiv/tracking/stats');
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
      const result = await apiClient.postWithLongTimeout<TrackResult>(
        '/arxiv/tracking/track-categories',
        {
          categories: selectedCategories,
          days_back: daysBack,
          update_database: updateDatabase,
        }
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
      setMessage(`ERROR: ${getErrorMessage(error)}`);
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
      const results = await apiClient.postWithLongTimeout<ArXivPaper[]>(
        '/arxiv/search',
        {
          query: searchQuery.trim(),
          max_results: maxResults,
          categories:
            useCategoryFilterForSearch && selectedCategories.length > 0
              ? selectedCategories
              : null,
        }
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
      const result = await apiClient.postWithLongTimeout<IngestionResult>(
        '/arxiv/ingest',
        {
          paper_ids: selectedPaperIds,
          download_pdfs: downloadPdfs,
          extract_content: extractContentOnIngest,
          batch_size: Math.min(20, Math.max(1, selectedPaperIds.length)),
        }
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
      const result = await apiClient.postWithLongTimeout<ExtractionResult>(
        '/arxiv/extraction/extract-features',
        {
          paper_ids: parsedExtractIds,
          extract_entities: extractEntities,
          extract_topics: extractTopics,
          extract_citations: extractCitations,
          extract_keyphrases: extractKeyphrases,
          extract_summaries: extractSummaries,
          update_knowledge_graph: updateKG,
        }
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

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="flex items-start gap-4">
          <div className="rounded-lg border border-[#1A1A1A] bg-[#0A0A0A] p-2.5">
            <Activity className="h-6 w-6 text-[#D4A039]" />
          </div>
          <div>
            <h1 className="text-2xl font-mono font-bold text-[#D4A039]">
              ArXiv Research Hub
            </h1>
            <div className="mt-1 flex items-center gap-2">
              <span
                className="h-1.5 w-1.5 rounded-full bg-[#D4A039]"
                aria-hidden="true"
              />
              <span className="text-sm text-gray-500">
                Track, ingest, and extract insights from ArXiv papers
              </span>
            </div>
          </div>
        </div>

        {isStatsLoading && !stats && (
          <div className="inline-flex items-center gap-2 rounded-lg border border-[#1A1A1A] bg-[#111111] px-3 py-2 text-[10px] font-mono text-[#9CA3AF]">
            <Loader2 className="h-3.5 w-3.5 animate-spin text-[#D4A039]" />
            Loading metrics…
          </div>
        )}

        {!isStatsLoading && !stats && statsError && (
          <div className="max-w-md rounded-lg border border-[#6B2A2A] bg-[#2B1111]/70 px-3 py-2 text-[10px] font-mono text-[#FFAEAE]">
            Unable to load stats: {statsError}
          </div>
        )}

        {stats && (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {[
              {
                label: 'Tracked',
                value: stats.statistics.total_papers_tracked,
                color: 'text-[#D4A039]',
              },
              {
                label: 'Active',
                value: stats.statistics.active_papers,
                color: 'text-[#00D4FF]',
              },
              {
                label: 'Categories',
                value: stats.statistics.categories_tracked,
                color: 'text-[#E5E7EB]',
              },
              {
                label: 'Deleted',
                value: stats.statistics.deleted_papers,
                color: 'text-[#FFB700]',
              },
            ].map((item) => (
              <div
                key={item.label}
                className="min-w-[110px] rounded-lg border border-[#1A1A1A] bg-[#111111] px-3 py-2"
              >
                <div className="text-[10px] font-mono uppercase tracking-wide text-gray-500">
                  {item.label}
                </div>
                <div className={cn('text-lg font-mono font-bold', item.color)}>
                  {item.value}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="rounded-lg border border-[#1A1A1A] bg-[#0A0A0A]">
        <div className="border-b border-[#1A1A1A] bg-[#0A0A0A] px-3 py-2 sm:px-4">
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
                      'relative flex items-center gap-2 border-b-2 px-4 py-2 text-sm font-mono transition-colors touch-manipulation',
                      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#D4A039]/60 focus-visible:ring-offset-2 focus-visible:ring-offset-[#0A0A0A]',
                      isActive
                        ? 'border-[#D4A039] text-[#D4A039]'
                        : 'border-transparent text-gray-500 hover:text-gray-300'
                    )}
                  >
                    <Icon className="h-3.5 w-3.5" aria-hidden="true" />
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
            <div className="mt-3 space-y-2 rounded-lg border border-[#1A1A1A] bg-[#0A0A0A]/60 p-3">
              {(isTracking || isSearching || isIngesting || isExtracting) && (
                <ProgressBar
                  value={progress}
                  label={
                    isTracking
                      ? 'Tracking Progress'
                      : isSearching
                        ? 'Search Progress'
                        : isIngesting
                          ? 'Ingestion Progress'
                          : 'Extraction Progress'
                  }
                />
              )}
              {message && (
                <div
                  className={cn(
                    'rounded-md border px-3 py-2 text-[11px] font-mono leading-relaxed',
                    hasMessageError
                      ? 'border-[#6B2A2A] bg-[#2B1111] text-[#FFAEAE]'
                      : 'border-[#1A1A1A] bg-[#151515] text-[#9CA3AF]'
                  )}
                >
                  {message}
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
              initial={{ opacity: 0, y: 8, filter: 'blur(8px)' }}
              animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
              exit={{ opacity: 0, y: -8, filter: 'blur(8px)' }}
              transition={{ duration: 0.25 }}
              className="min-h-[420px]"
            >
              {activeTab === 'tracking' && (
                <TrackingTab
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
