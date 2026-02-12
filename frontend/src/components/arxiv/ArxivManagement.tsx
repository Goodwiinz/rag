'use client';

import { apiClient } from '@/services/apiClient';
import { cn } from '@/lib/utils';
import {
  Activity,
  BarChart3,
  Brain,
  CheckSquare,
  Cpu,
  Database,
  FileText,
  Globe,
  Layers,
  Loader2,
  RefreshCw,
  Search,
  Sparkles,
  Square,
  Terminal,
  TrendingUp,
  Upload,
  Zap,
} from 'lucide-react';
import React, { useEffect, useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';

interface TrackResult {
  status: string;
  timestamp: string;
  result: {
    categories: string[];
    period_days: number;
    papers_found: number;
    changes_detected: number;
    changes_by_type: {
      new: Array<any>;
      updated: Array<any>;
      deleted: Array<any>;
    };
    applied: boolean;
    summary: {
      new: number;
      updated: number;
      deleted: number;
      errors: number;
    };
  };
}

interface StatsResult {
  status: string;
  timestamp: string;
  statistics: {
    total_papers_tracked: number;
    active_papers: number;
    deleted_papers: number;
    categories_tracked: number;
    top_categories: Array<[string, number]>;
    recent_changes_week: any;
    state_file_path: string;
  };
}

interface ExtractionResult {
  status: string;
  message: string;
  processed_count: number;
  results: Array<{
    paper_id: string;
    title: string;
    extraction_status: string;
    features: {
      entities?: any;
      topics?: string[] | { error: string };
      keyphrases?: string[] | { error: string };
      summary?: string | { error: string };
      citations?: any;
    };
    error?: string;
  }>;
}

interface ArXivPaper {
  id: string;
  title: string;
  authors: string[];
  abstract: string;
  published: string;
  updated: string;
  categories: string[];
  primary_category?: string;
  pdf_url?: string;
}

interface IngestionResult {
  message: string;
  paper_count: number;
  status: string;
}

const CORE_AI_CATEGORIES = ['cs.AI', 'cs.LG', 'cs.CV', 'cs.CL', 'stat.ML'];

const normalizePaperIds = (value: string) =>
  value
    .split(/[\s,\n]+/)
    .map((id) => id.trim())
    .filter(Boolean);

const ToggleSwitch: React.FC<{
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  label: string;
}> = ({ checked, onCheckedChange, label }) => (
  <button
    type="button"
    role="switch"
    aria-checked={checked}
    aria-label={label}
    onClick={() => onCheckedChange(!checked)}
    className={cn(
      'group flex w-full items-center justify-between rounded-lg border px-2.5 py-2 font-mono text-[10px] font-bold uppercase tracking-wider transition-colors touch-manipulation',
      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00FF9F]/60 focus-visible:ring-offset-2 focus-visible:ring-offset-[#0A0A0A]',
      checked
        ? 'border-[#00FF9F]/50 bg-[#00FF9F]/10 text-[#E5E7EB]'
        : 'border-[#1A1A1A] bg-[#0A0A0A]/40 text-[#9CA3AF] hover:border-[#333333]'
    )}
  >
    <span className="truncate pr-3 text-left">{label}</span>
    <span
      className={cn(
        'relative inline-flex h-5 w-9 shrink-0 rounded-full border transition-colors',
        checked
          ? 'border-[#00FF9F]/60 bg-[#00FF9F]/20'
          : 'border-[#1A1A1A] bg-[#111111]'
      )}
      aria-hidden="true"
    >
      <span
        className={cn(
          'mt-[2px] ml-[2px] block h-3.5 w-3.5 rounded-full transition-transform',
          checked
            ? 'translate-x-4 bg-[#00FF9F] shadow-[0_0_8px_rgba(0,255,159,0.65)]'
            : 'translate-x-0 bg-[#6B7280]'
        )}
      />
    </span>
  </button>
);

const ProgressBar: React.FC<{ value: number; label?: string }> = ({
  value,
  label,
}) => (
  <div className="w-full space-y-1.5">
    {label && (
      <div className="flex items-center justify-between text-[9px] font-mono uppercase tracking-widest text-[#6B7280]">
        <span>{label}</span>
        <span className="font-bold text-[#00FF9F]">{Math.round(value)}%</span>
      </div>
    )}
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-[#1A1A1A]">
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: `${value}%` }}
        transition={{ duration: 0.35, ease: 'easeOut' }}
        className="h-full rounded-full bg-gradient-to-r from-[#00CC7F] to-[#00FF9F] shadow-[0_0_10px_rgba(0,255,159,0.35)]"
      />
    </div>
  </div>
);

const CustomSlider: React.FC<{
  value: number;
  onChange: (value: number) => void;
  min: number;
  max: number;
  step: number;
  label: string;
}> = ({ value, onChange, min, max, step, label }) => (
  <div className="space-y-3">
    <div className="flex items-center justify-between">
      <label className="text-[10px] font-mono font-bold uppercase tracking-widest text-[#6B7280]">
        {label}
      </label>
      <span className="rounded border border-[#00FF9F]/20 bg-[#00FF9F]/10 px-2 py-0.5 text-[10px] font-mono font-bold text-[#00FF9F]">
        {value}
      </span>
    </div>
    <input
      type="range"
      value={value}
      onChange={(e) => onChange(Number(e.target.value))}
      min={min}
      max={max}
      step={step}
      className="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-[#1A1A1A] accent-[#00FF9F]"
    />
  </div>
);

export default function ArxivManagement() {
  const [isTracking, setIsTracking] = useState(false);
  const [isIngesting, setIsIngesting] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);
  const [trackingResult, setTrackingResult] = useState<TrackResult | null>(
    null
  );
  const [stats, setStats] = useState<StatsResult | null>(null);
  const [extractionResult, setExtractionResult] =
    useState<ExtractionResult | null>(null);
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState('');
  const [activeTab, setActiveTab] = useState('tracking');

  const [selectedCategories, setSelectedCategories] = useState<string[]>([
    'cs.AI',
    'cs.LG',
    'cs.CV',
    'quant-ph',
  ]);
  const [daysBack, setDaysBack] = useState(1);
  const [maxResults, setMaxResults] = useState(50);
  const [updateDatabase, setUpdateDatabase] = useState(true);
  const [extractEntities, setExtractEntities] = useState(true);
  const [downloadPdfs, setDownloadPdfs] = useState(false);

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

  const popularCategories = [
    'cs.AI',
    'cs.LG',
    'cs.CV',
    'cs.CL',
    'cs.RO',
    'quant-ph',
    'stat.ML',
    'math.OC',
    'physics.data-an',
    'eess.IV',
  ];

  const tabs = [
    { id: 'tracking', label: 'Track Changes', icon: TrendingUp },
    { id: 'ingest', label: 'Ingest Papers', icon: Upload },
    { id: 'extract', label: 'Extract Features', icon: Brain },
    { id: 'stats', label: 'Statistics', icon: BarChart3 },
  ];

  const parsedExtractIds = useMemo(
    () => normalizePaperIds(extractPaperIds),
    [extractPaperIds]
  );
  const hasMessageError = message.startsWith('ERROR:');
  const hasExtractionFeaturesEnabled =
    extractEntities ||
    extractTopics ||
    extractKeyphrases ||
    extractCitations ||
    extractSummaries;

  const fetchStats = async () => {
    try {
      const result = await apiClient.get<StatsResult>('/arxiv/tracking/stats');
      setStats(result);
    } catch (error: any) {
      console.error('Failed to fetch stats:', error);
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
        CORE_AI_CATEGORIES.filter((cat) => popularCategories.includes(cat))
      );
      return;
    }

    if (preset === 'all') {
      setSelectedCategories(popularCategories);
      return;
    }

    setSelectedCategories([]);
  };

  const handleTrackChanges = async () => {
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
      setMessage(`ERROR: ${error.response?.data?.detail || error.message}`);
    } finally {
      setIsTracking(false);
    }
  };

  const handleSearchPapers = async () => {
    if (!searchQuery.trim()) return;

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
          query: searchQuery,
          max_results: maxResults,
          categories: selectedCategories.length > 0 ? selectedCategories : null,
        }
      );

      setProgress(100);
      setSearchResults(results);
      setMessage(`Found ${results.length} matching papers.`);
    } catch (error: any) {
      console.error('Search failed:', error);
      setProgress(0);
      setMessage(`ERROR: ${error.response?.data?.detail || error.message}`);
    } finally {
      setIsSearching(false);
    }
  };

  const handleIngestSelected = async () => {
    if (selectedPaperIds.length === 0) return;

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
          extract_content: extractEntities,
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
      setMessage(`ERROR: ${error.response?.data?.detail || error.message}`);
    } finally {
      setIsIngesting(false);
    }
  };

  const handleExtractFeatures = async () => {
    const paperIds = normalizePaperIds(extractPaperIds);

    if (paperIds.length === 0) {
      setMessage('ERROR: Add at least one paper ID before extraction.');
      return;
    }

    if (!hasExtractionFeaturesEnabled) {
      setMessage('ERROR: Enable at least one extraction option.');
      return;
    }

    setIsExtracting(true);
    setExtractionResult(null);
    setMessage(`Extracting features from ${paperIds.length} papers…`);
    setProgress(10);

    try {
      setProgress(35);
      const result = await apiClient.postWithLongTimeout<ExtractionResult>(
        '/arxiv/extraction/extract-features',
        {
          paper_ids: paperIds,
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
      setMessage(`ERROR: ${error.response?.data?.detail || error.message}`);
    } finally {
      setIsExtracting(false);
    }
  };

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="flex items-start gap-4">
          <div className="rounded-lg border border-[#1A1A1A] bg-[#0A0A0A] p-2.5">
            <Activity className="h-6 w-6 text-[#00FF9F]" />
          </div>
          <div>
            <h1 className="text-2xl font-mono font-bold text-[#00FF9F]">
              ArXiv Research Hub
            </h1>
            <div className="mt-1 flex items-center gap-2">
              <span
                className="h-1.5 w-1.5 rounded-full bg-[#00FF9F]"
                aria-hidden="true"
              />
              <span className="text-sm text-gray-500">
                Track, ingest, and extract insights from ArXiv papers
              </span>
            </div>
          </div>
        </div>

        {stats && (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {[
              {
                label: 'Tracked',
                value: stats.statistics.total_papers_tracked,
                color: 'text-[#00FF9F]',
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
                      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00FF9F]/60 focus-visible:ring-offset-2 focus-visible:ring-offset-[#0A0A0A]',
                      isActive
                        ? 'border-[#00FF9F] text-[#00FF9F]'
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
                <div className="space-y-6">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="inline-flex items-center gap-1 rounded-md border border-[#1A1A1A] bg-[#0A0A0A]/50 px-2 py-1 text-[9px] font-mono uppercase tracking-wider text-[#9CA3AF]">
                      <Sparkles className="h-3 w-3 text-[#FFB700]" />
                      Track New and Updated Papers
                    </span>
                    <span className="inline-flex items-center rounded-md border border-[#1A1A1A] bg-[#0A0A0A]/50 px-2 py-1 text-[9px] font-mono uppercase tracking-wider text-[#9CA3AF]">
                      {selectedCategories.length} categories selected
                    </span>
                    <span className="inline-flex items-center rounded-md border border-[#1A1A1A] bg-[#0A0A0A]/50 px-2 py-1 text-[9px] font-mono uppercase tracking-wider text-[#9CA3AF]">
                      {daysBack} day depth
                    </span>
                  </div>

                  <div className="grid grid-cols-1 gap-6 xl:grid-cols-12">
                    <div className="space-y-5 xl:col-span-5">
                      <div className="space-y-4 rounded-xl border border-[#1A1A1A] bg-[#0A0A0A]/50 p-4">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <h3 className="text-[10px] font-mono font-bold uppercase tracking-widest text-[#9CA3AF]">
                            Category Filter
                          </h3>
                          <div className="flex flex-wrap gap-2">
                            <button
                              type="button"
                              onClick={() => applyCategoryPreset('core')}
                              className="rounded-md border border-[#00FF9F]/25 px-2 py-1 text-[9px] font-mono uppercase tracking-wide text-[#00FF9F] hover:bg-[#00FF9F]/10"
                            >
                              Core AI
                            </button>
                            <button
                              type="button"
                              onClick={() => applyCategoryPreset('all')}
                              className="rounded-md border border-[#1A1A1A] px-2 py-1 text-[9px] font-mono uppercase tracking-wide text-[#6B7280] hover:bg-[#151515]"
                            >
                              Select All
                            </button>
                            <button
                              type="button"
                              onClick={() => applyCategoryPreset('clear')}
                              className="rounded-md border border-[#1A1A1A] px-2 py-1 text-[9px] font-mono uppercase tracking-wide text-[#6B7280] hover:bg-[#151515]"
                            >
                              Clear
                            </button>
                          </div>
                        </div>

                        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                          {popularCategories.map((category) => (
                            <ToggleSwitch
                              key={category}
                              checked={selectedCategories.includes(category)}
                              onCheckedChange={() => toggleCategory(category)}
                              label={category}
                            />
                          ))}
                        </div>

                        <div className="space-y-1">
                          <div className="text-[9px] font-mono uppercase tracking-wider text-[#6B7280]">
                            Selected
                          </div>
                          <div className="flex flex-wrap gap-1.5">
                            {selectedCategories.length > 0 ? (
                              selectedCategories.map((category) => (
                                <span
                                  key={category}
                                  className="rounded-md border border-[#00FF9F]/20 bg-[#00FF9F]/10 px-2 py-0.5 text-[9px] font-mono uppercase tracking-wide text-[#00FF9F]"
                                >
                                  {category}
                                </span>
                              ))
                            ) : (
                              <span className="text-[10px] font-mono text-[#6B7280]">
                                No categories selected.
                              </span>
                            )}
                          </div>
                        </div>
                      </div>

                      <div className="space-y-5 rounded-xl border border-[#1A1A1A] bg-[#0A0A0A]/50 p-4">
                        <CustomSlider
                          label="Lookback Window (Days)"
                          value={daysBack}
                          onChange={setDaysBack}
                          min={1}
                          max={30}
                          step={1}
                        />

                        <ToggleSwitch
                          checked={updateDatabase}
                          onCheckedChange={setUpdateDatabase}
                          label="Auto Update Database"
                        />
                      </div>

                      <div className="flex flex-wrap items-center gap-3">
                        <button
                          type="button"
                          onClick={handleTrackChanges}
                          disabled={
                            isTracking || selectedCategories.length === 0
                          }
                          className={cn(
                            'inline-flex items-center gap-2 rounded-lg px-5 py-2.5 text-[11px] font-mono font-bold uppercase transition-colors touch-manipulation',
                            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00FF9F]/60 focus-visible:ring-offset-2 focus-visible:ring-offset-[#0A0A0A]',
                            'bg-[#00FF9F] text-[#0A0A0A] hover:bg-[#00CC7F] disabled:cursor-not-allowed disabled:opacity-45'
                          )}
                        >
                          {isTracking ? (
                            <Loader2
                              className="h-4 w-4 animate-spin"
                              aria-hidden="true"
                            />
                          ) : (
                            <RefreshCw className="h-4 w-4" aria-hidden="true" />
                          )}
                          Run Change Scan
                        </button>

                        <button
                          type="button"
                          onClick={fetchStats}
                          className="rounded-lg border border-[#1A1A1A] px-5 py-2.5 text-[11px] font-mono font-bold uppercase text-[#6B7280] transition-colors hover:bg-[#151515]"
                        >
                          Refresh Metrics
                        </button>
                      </div>
                    </div>

                    <div className="space-y-5 xl:col-span-7">
                      <div className="flex min-h-[320px] flex-col rounded-xl border border-[#1A1A1A] bg-[#0A0A0A] p-5">
                        <div className="mb-4 flex items-center justify-between border-b border-[#1A1A1A] pb-3">
                          <span className="text-[9px] font-mono font-bold uppercase tracking-widest text-[#9CA3AF]">
                            Activity Feed
                          </span>
                          <span className="inline-flex items-center gap-1.5 text-[9px] font-mono text-[#00FF9F]">
                            <span
                              className="h-1.5 w-1.5 rounded-full bg-[#00FF9F]"
                              aria-hidden="true"
                            />
                            Live
                          </span>
                        </div>

                        {trackingResult ? (
                          <div className="space-y-4">
                            <div className="grid grid-cols-1 gap-2 sm:grid-cols-4">
                              {[
                                {
                                  label: 'New',
                                  value: trackingResult.result.summary.new,
                                  color: 'text-[#00FF9F]',
                                },
                                {
                                  label: 'Updated',
                                  value: trackingResult.result.summary.updated,
                                  color: 'text-[#00D4FF]',
                                },
                                {
                                  label: 'Deleted',
                                  value: trackingResult.result.summary.deleted,
                                  color: 'text-[#FFB700]',
                                },
                                {
                                  label: 'Errors',
                                  value: trackingResult.result.summary.errors,
                                  color: 'text-[#FFAEAE]',
                                },
                              ].map((item) => (
                                <div
                                  key={item.label}
                                  className="rounded-lg border border-[#1A1A1A] bg-[#111111] p-3"
                                >
                                  <div
                                    className={cn(
                                      'text-lg font-mono font-bold',
                                      item.color
                                    )}
                                  >
                                    {item.value}
                                  </div>
                                  <div className="mt-0.5 text-[9px] font-mono uppercase tracking-wide text-[#6B7280]">
                                    {item.label}
                                  </div>
                                </div>
                              ))}
                            </div>

                            <div className="rounded-lg border border-[#1A1A1A] bg-[#111111] p-3 text-[10px] font-mono text-[#9CA3AF]">
                              <div className="mb-2 text-[9px] uppercase tracking-wider text-[#6B7280]">
                                Sync Summary
                              </div>
                              <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                                <div>
                                  <span className="text-[#6B7280]">
                                    Papers scanned:
                                  </span>{' '}
                                  <span className="text-[#E5E7EB]">
                                    {trackingResult.result.papers_found}
                                  </span>
                                </div>
                                <div>
                                  <span className="text-[#6B7280]">
                                    Changes detected:
                                  </span>{' '}
                                  <span className="text-[#E5E7EB]">
                                    {trackingResult.result.changes_detected}
                                  </span>
                                </div>
                                <div>
                                  <span className="text-[#6B7280]">
                                    DB write:
                                  </span>{' '}
                                  <span className="text-[#E5E7EB]">
                                    {trackingResult.result.applied
                                      ? 'Enabled'
                                      : 'Dry Run'}
                                  </span>
                                </div>
                              </div>
                            </div>

                            {trackingResult.result.applied && (
                              <div className="rounded-lg border border-[#00FF9F]/25 bg-[#00FF9F]/5 p-3 text-[10px] font-mono text-[#E5E7EB]">
                                Knowledge graph synchronization has been queued
                                for detected updates.
                              </div>
                            )}
                          </div>
                        ) : (
                          <div className="flex flex-1 flex-col items-center justify-center text-center opacity-50">
                            <Terminal
                              className="mb-3 h-8 w-8 text-[#6B7280]"
                              aria-hidden="true"
                            />
                            <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-[#6B7280]">
                              Run a scan to view updates and actions
                            </p>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'ingest' && (
                <div className="space-y-6">
                  <div className="space-y-1">
                    <h3 className="flex items-center gap-2 text-sm font-mono font-bold uppercase tracking-tight text-[#E5E7EB]">
                      <Upload
                        className="h-4 w-4 text-[#00D4FF]"
                        aria-hidden="true"
                      />
                      Search and Queue Ingestion
                    </h3>
                    <p className="text-[11px] font-mono leading-relaxed text-[#6B7280]">
                      Search by topic, select relevant papers, and queue
                      ingestion in one flow.
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
                              onChange={(e) => setSearchQuery(e.target.value)}
                              onKeyDown={(e) =>
                                e.key === 'Enter' && handleSearchPapers()
                              }
                              placeholder="transformer interpretability…"
                              autoComplete="off"
                              className="w-full rounded-lg border border-[#1A1A1A] bg-[#111111] py-2.5 pl-10 pr-3 font-mono text-xs text-[#E5E7EB] placeholder:text-[#6B7280] focus:border-[#00FF9F]/50 focus:outline-none"
                            />
                          </div>
                        </div>

                        <CustomSlider
                          label="Maximum Results"
                          value={maxResults}
                          onChange={setMaxResults}
                          min={1}
                          max={100}
                          step={1}
                        />

                        <div className="space-y-2 rounded-lg border border-dashed border-[#1A1A1A] bg-[#0A0A0A]/40 p-3">
                          <ToggleSwitch
                            checked={extractEntities}
                            onCheckedChange={setExtractEntities}
                            label="Extract Text Content"
                          />
                          <ToggleSwitch
                            checked={downloadPdfs}
                            onCheckedChange={setDownloadPdfs}
                            label="Download Source PDF"
                          />
                        </div>

                        <div className="flex flex-wrap items-center gap-2">
                          <button
                            type="button"
                            onClick={handleSearchPapers}
                            disabled={isSearching || !searchQuery.trim()}
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
                            onClick={() => {
                              setSearchResults(null);
                              setSelectedPaperIds([]);
                              setSearchQuery('');
                            }}
                            className="rounded-lg border border-[#1A1A1A] px-4 py-2.5 text-[11px] font-mono font-bold uppercase text-[#6B7280] hover:bg-[#151515]"
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
                          onClick={handleIngestSelected}
                          disabled={
                            isIngesting || selectedPaperIds.length === 0
                          }
                          className={cn(
                            'inline-flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-[11px] font-mono font-bold uppercase transition-colors',
                            'bg-[#00FF9F] text-[#0A0A0A] hover:bg-[#00CC7F] disabled:cursor-not-allowed disabled:opacity-45'
                          )}
                        >
                          {isIngesting ? (
                            <Loader2
                              className="h-4 w-4 animate-spin"
                              aria-hidden="true"
                            />
                          ) : (
                            <Database className="h-4 w-4" aria-hidden="true" />
                          )}
                          Queue Ingestion
                        </button>

                        <button
                          type="button"
                          onClick={() => {
                            if (selectedPaperIds.length > 0) {
                              setExtractPaperIds(selectedPaperIds.join('\n'));
                              setActiveTab('extract');
                            }
                          }}
                          disabled={selectedPaperIds.length === 0}
                          className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-[#1A1A1A] px-4 py-2.5 text-[11px] font-mono font-bold uppercase text-[#6B7280] hover:bg-[#151515] disabled:cursor-not-allowed disabled:opacity-45"
                        >
                          <Brain className="h-4 w-4" aria-hidden="true" />
                          Send IDs to Extract
                        </button>

                        {ingestionResult && (
                          <div className="rounded-lg border border-[#00FF9F]/25 bg-[#00FF9F]/5 p-3 text-[10px] font-mono leading-relaxed text-[#9CA3AF]">
                            {ingestionResult.message} (
                            {ingestionResult.paper_count} papers)
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
                          {searchResults && (
                            <span className="text-[10px] font-mono text-[#6B7280]">
                              {searchResults.length} papers
                            </span>
                          )}
                        </div>

                        {searchResults ? (
                          searchResults.length > 0 ? (
                            <div className="max-h-[560px] space-y-3 overflow-y-auto pr-1 terminal-scrollbar">
                              {searchResults.map((paper) => {
                                const isSelected = selectedPaperIds.includes(
                                  paper.id
                                );

                                return (
                                  <button
                                    key={paper.id}
                                    type="button"
                                    aria-pressed={isSelected}
                                    onClick={() => {
                                      setSelectedPaperIds((prev) =>
                                        prev.includes(paper.id)
                                          ? prev.filter((id) => id !== paper.id)
                                          : [...prev, paper.id]
                                      );
                                    }}
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
                                          {paper.categories
                                            .slice(0, 3)
                                            .map((category) => (
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
              )}

              {activeTab === 'extract' && (
                <div className="space-y-6">
                  <div className="space-y-1">
                    <h3 className="flex items-center gap-2 text-sm font-mono font-bold uppercase tracking-tight text-[#E5E7EB]">
                      <Brain
                        className="h-4 w-4 text-[#FFB700]"
                        aria-hidden="true"
                      />
                      Extract Research Signals
                    </h3>
                    <p className="text-[11px] font-mono leading-relaxed text-[#6B7280]">
                      Extract entities, topics, keyphrases, citations, and
                      summaries for specific papers, then optionally sync to the
                      knowledge graph.
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
                            onChange={(e) => setExtractPaperIds(e.target.value)}
                            placeholder={'2501.12345\n2501.67890…'}
                            rows={7}
                            className="w-full rounded-lg border border-[#1A1A1A] bg-[#111111] p-3 font-mono text-xs text-[#E5E7EB] placeholder:text-[#6B7280] focus:border-[#00FF9F]/50 focus:outline-none"
                          />
                        </div>

                        <div className="grid grid-cols-1 gap-2">
                          <ToggleSwitch
                            checked={extractEntities}
                            onCheckedChange={setExtractEntities}
                            label="Extract Entities"
                          />
                          <ToggleSwitch
                            checked={extractTopics}
                            onCheckedChange={setExtractTopics}
                            label="Extract Topics"
                          />
                          <ToggleSwitch
                            checked={extractKeyphrases}
                            onCheckedChange={setExtractKeyphrases}
                            label="Extract Keyphrases"
                          />
                          <ToggleSwitch
                            checked={extractCitations}
                            onCheckedChange={setExtractCitations}
                            label="Extract Citations"
                          />
                          <ToggleSwitch
                            checked={extractSummaries}
                            onCheckedChange={setExtractSummaries}
                            label="Generate Summaries"
                          />
                          <ToggleSwitch
                            checked={updateKG}
                            onCheckedChange={setUpdateKG}
                            label="Update Knowledge Graph"
                          />
                        </div>

                        <div className="flex flex-wrap items-center gap-2">
                          <button
                            type="button"
                            onClick={handleExtractFeatures}
                            disabled={
                              isExtracting || parsedExtractIds.length === 0
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
                            onClick={() => {
                              setExtractPaperIds('');
                              setExtractionResult(null);
                            }}
                            className="rounded-lg border border-[#1A1A1A] px-4 py-2.5 text-[11px] font-mono font-bold uppercase text-[#6B7280] hover:bg-[#151515]"
                          >
                            Clear
                          </button>
                        </div>
                      </div>

                      <div className="rounded-xl border border-[#1A1A1A] bg-[#0A0A0A]/50 p-4">
                        <div className="text-[9px] font-mono uppercase tracking-widest text-[#6B7280]">
                          Paper IDs Ready
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
                                const featureKeys = Object.keys(
                                  result.features || {}
                                );
                                const hasFailed =
                                  result.extraction_status !== 'completed';

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
              )}

              {activeTab === 'stats' && (
                <div className="space-y-8">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <h3 className="flex items-center gap-2 text-sm font-mono font-bold uppercase tracking-tight text-[#E5E7EB]">
                      <BarChart3
                        className="h-4 w-4 text-[#00D4FF]"
                        aria-hidden="true"
                      />
                      System Statistics
                    </h3>
                    <button
                      type="button"
                      onClick={fetchStats}
                      className="rounded-lg border border-[#1A1A1A] px-4 py-2 text-[11px] font-mono font-bold uppercase text-[#6B7280] hover:bg-[#151515]"
                    >
                      Refresh
                    </button>
                  </div>

                  {stats ? (
                    <>
                      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
                        {[
                          {
                            label: 'System Papers',
                            value: stats.statistics.total_papers_tracked,
                            color: 'text-[#E5E7EB]',
                            icon: FileText,
                          },
                          {
                            label: 'Active Papers',
                            value: stats.statistics.active_papers,
                            color: 'text-[#00FF9F]',
                            icon: Activity,
                          },
                          {
                            label: 'Category Clusters',
                            value: stats.statistics.categories_tracked,
                            color: 'text-[#00D4FF]',
                            icon: Layers,
                          },
                          {
                            label: 'Deleted Papers',
                            value: stats.statistics.deleted_papers,
                            color: 'text-[#FFB700]',
                            icon: Zap,
                          },
                        ].map((item) => (
                          <div
                            key={item.label}
                            className="relative overflow-hidden rounded-xl border border-[#1A1A1A] bg-[#0A0A0A]/50 p-5"
                          >
                            <item.icon
                              className="absolute -right-2 -top-2 h-14 w-14 text-[#1A1A1A] opacity-25"
                              aria-hidden="true"
                            />
                            <div
                              className={cn(
                                'text-2xl font-mono font-bold',
                                item.color
                              )}
                            >
                              {item.value}
                            </div>
                            <div className="mt-1 text-[9px] font-mono uppercase tracking-widest text-[#6B7280]">
                              {item.label}
                            </div>
                          </div>
                        ))}
                      </div>

                      <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
                        <div className="rounded-xl border border-[#1A1A1A] bg-[#0A0A0A]/50 p-5 xl:col-span-8">
                          <div className="mb-5 flex items-center gap-2">
                            <Cpu
                              className="h-4 w-4 text-[#00FF9F]"
                              aria-hidden="true"
                            />
                            <h4 className="text-xs font-mono font-bold uppercase tracking-widest text-[#E5E7EB]">
                              Category Distribution
                            </h4>
                          </div>

                          <div className="space-y-3">
                            {stats.statistics.top_categories?.map(
                              ([category, count]) => (
                                <div key={category} className="space-y-1.5">
                                  <div className="flex items-center justify-between text-[10px] font-mono uppercase">
                                    <span className="text-[#9CA3AF]">
                                      {category}
                                    </span>
                                    <span className="font-bold text-[#00FF9F]">
                                      {count}
                                    </span>
                                  </div>
                                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-[#1A1A1A]">
                                    <div
                                      className="h-full rounded-full bg-[#00FF9F]/40"
                                      style={{
                                        width: `${(count / Math.max(stats.statistics.total_papers_tracked, 1)) * 100}%`,
                                      }}
                                    />
                                  </div>
                                </div>
                              )
                            )}
                          </div>
                        </div>

                        <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-[#1A1A1A] bg-[#0A0A0A]/50 p-5 xl:col-span-4">
                          <Globe
                            className="h-10 w-10 text-[#1A1A1A]"
                            aria-hidden="true"
                          />
                          <p className="text-center text-[10px] font-mono uppercase tracking-[0.25em] text-[#9CA3AF]">
                            Grid Status Active
                          </p>
                          <p className="text-center text-[10px] font-mono text-[#6B7280]">
                            Synchronization latency: optimal
                          </p>
                          <p className="text-center text-[9px] font-mono text-[#6B7280]">
                            State file: {stats.statistics.state_file_path}
                          </p>
                        </div>
                      </div>
                    </>
                  ) : (
                    <div className="rounded-xl border border-[#1A1A1A] bg-[#0A0A0A]/50 p-6 text-center text-[11px] font-mono text-[#6B7280]">
                      Statistics are unavailable right now.
                    </div>
                  )}
                </div>
              )}
            </motion.section>
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
