"use client";

import { apiClient } from '@/services/apiClient';
import { Activity, BarChart3, BookOpen, Brain, CheckCircle, CheckSquare, Database, FileText, Hash, Link2, Loader2, RefreshCw, Search, Square, TrendingUp, Upload } from 'lucide-react';
import React, { useState } from 'react';

// Terminal Observatory Theme Constants
// Using centralized theme constants
import { THEME } from '@/theme/constants';

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

// ArXiv paper from search results
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

// Ingestion result from API
interface IngestionResult {
  message: string;
  paper_count: number;
  status: string;
}

// Custom Toggle Switch Component
const ToggleSwitch: React.FC<{
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  id?: string;
}> = ({ checked, onCheckedChange, id }) => (
  <button
    id={id}
    type="button"
    role="switch"
    aria-checked={checked}
    onClick={() => onCheckedChange(!checked)}
    className="relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors duration-200"
    style={{
      background: checked ? `${THEME.colors.primary}40` : THEME.colors.borderMuted,
      border: `1px solid ${checked ? THEME.colors.primary : THEME.colors.border}`,
    }}
  >
    <span
      className="pointer-events-none block h-4 w-4 rounded-full transition-transform duration-200"
      style={{
        transform: checked ? 'translateX(16px)' : 'translateX(0)',
        background: checked ? THEME.colors.primary : THEME.colors.textMuted,
        marginTop: '1px',
        marginLeft: '1px',
      }}
    />
  </button>
);

// Custom Progress Bar
const ProgressBar: React.FC<{ value: number }> = ({ value }) => (
  <div className="h-2 w-full rounded-full overflow-hidden" style={{ background: THEME.colors.borderMuted }}>
    <div
      className="h-full rounded-full transition-all duration-500"
      style={{
        width: `${value}%`,
        background: `linear-gradient(90deg, ${THEME.colors.primary}80, ${THEME.colors.primary})`,
      }}
    />
  </div>
);

// Custom Slider Component
const CustomSlider: React.FC<{
  value: number;
  onChange: (value: number) => void;
  min: number;
  max: number;
  step: number;
}> = ({ value, onChange, min, max, step }) => (
  <input
    type="range"
    value={value}
    onChange={(e) => onChange(Number(e.target.value))}
    min={min}
    max={max}
    step={step}
    className="w-full h-2 rounded-full appearance-none cursor-pointer"
    style={{
      background: `linear-gradient(to right, ${THEME.colors.primary} 0%, ${THEME.colors.primary} ${((value - min) / (max - min)) * 100}%, ${THEME.colors.borderMuted} ${((value - min) / (max - min)) * 100}%, ${THEME.colors.borderMuted} 100%)`,
    }}
  />
);

export default function ArxivManagement() {
  const [isTracking, setIsTracking] = useState(false);
  const [isIngesting, setIsIngesting] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);
  const [trackingResult, setTrackingResult] = useState<TrackResult | null>(null);
  const [stats, setStats] = useState<StatsResult | null>(null);
  const [extractionResult, setExtractionResult] = useState<ExtractionResult | null>(null);
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState('');
  const [activeTab, setActiveTab] = useState('tracking');

  // Form states
  const [selectedCategories, setSelectedCategories] = useState<string[]>(['cs.AI', 'cs.LG', 'cs.CV', 'quant-ph']);
  const [daysBack, setDaysBack] = useState(1);
  const [maxResults, setMaxResults] = useState(50);
  const [updateDatabase, setUpdateDatabase] = useState(true);
  const [extractEntities, setExtractEntities] = useState(true);
  const [downloadPdfs, setDownloadPdfs] = useState(false);

  // Ingest Papers search workflow states
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<ArXivPaper[] | null>(null);
  const [selectedPaperIds, setSelectedPaperIds] = useState<string[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [ingestionResult, setIngestionResult] = useState<IngestionResult | null>(null);

  // Extraction form states
  const [extractPaperIds, setExtractPaperIds] = useState('');
  const [extractTopics, setExtractTopics] = useState(true);
  const [extractKeyphrases, setExtractKeyphrases] = useState(true);
  const [extractCitations, setExtractCitations] = useState(true);
  const [extractSummaries, setExtractSummaries] = useState(true);
  const [updateKG, setUpdateKG] = useState(true);

  const popularCategories = [
    'cs.AI', 'cs.LG', 'cs.CV', 'cs.CL', 'cs.RO',
    'quant-ph', 'stat.ML', 'math.OC', 'physics.data-an', 'eess.IV'
  ];

  const tabs = [
    { id: 'tracking', label: 'Track Changes', icon: TrendingUp },
    { id: 'ingest', label: 'Ingest Papers', icon: Upload },
    { id: 'extract', label: 'Extract Features', icon: Brain },
    { id: 'stats', label: 'Statistics', icon: BarChart3 },
  ];

  // Handle tracking changes
  const handleTrackChanges = async () => {
    setIsTracking(true);
    setMessage(`Tracking changes for ${selectedCategories.length} categories...`);
    setProgress(10);

    try {
      setProgress(30);
      const result = await apiClient.postWithLongTimeout<TrackResult>('/arxiv/tracking/track-categories', {
        categories: selectedCategories,
        days_back: daysBack,
        update_database: updateDatabase
      });

      setProgress(70);
      setTrackingResult(result);

      if (result.result.applied && updateDatabase) {
        setMessage(`✅ Tracking completed! Database updated with ${result.result.summary.new} new papers.`);
      } else if (!result.result.applied && updateDatabase) {
        setMessage(`⚠️ Found ${result.result.summary.new} new papers but database update is disabled.`);
      } else {
        setMessage(`✅ Tracking completed! Found ${result.result.summary.new} new, ${result.result.summary.updated} updated, ${result.result.summary.deleted} deleted papers.`);
      }
      setProgress(100);

      await fetchStats();
    } catch (error: any) {
      console.error('Tracking failed:', error);
      setProgress(0);
      if (error.response?.status === 401) {
        setMessage('❌ Authentication failed. Please refresh the page and try again.');
      } else {
        setMessage(`❌ Tracking failed: ${error.response?.data?.detail || error.message}`);
      }
    } finally {
      setIsTracking(false);
    }
  };

  // Handle searching arXiv papers
  const handleSearchPapers = async () => {
    if (!searchQuery.trim()) {
      setMessage('Please enter a search query');
      return;
    }

    setIsSearching(true);
    setMessage(`Searching arXiv for "${searchQuery}"...`);
    setProgress(10);
    setSearchResults(null);
    setSelectedPaperIds([]);
    setIngestionResult(null);

    try {
      setProgress(40);
      const results = await apiClient.postWithLongTimeout<ArXivPaper[]>('/arxiv/search', {
        query: searchQuery,
        max_results: maxResults,
        categories: selectedCategories.length > 0 ? selectedCategories : null
      });

      setProgress(100);
      setSearchResults(results);
      setMessage(`✅ Found ${results.length} papers matching "${searchQuery}"`);
    } catch (error: any) {
      console.error('Search failed:', error);
      setProgress(0);
      if (error.response?.status === 401) {
        setMessage('❌ Authentication failed. Please refresh the page and try again.');
      } else {
        setMessage(`❌ Search failed: ${error.response?.data?.detail || error.message}`);
      }
    } finally {
      setIsSearching(false);
    }
  };

  // Handle ingesting selected papers
  const handleIngestSelected = async () => {
    if (selectedPaperIds.length === 0) {
      setMessage('Please select at least one paper to ingest');
      return;
    }

    setIsIngesting(true);
    setMessage(`Ingesting ${selectedPaperIds.length} papers...`);
    setProgress(10);

    try {
      setProgress(40);
      const result = await apiClient.postWithLongTimeout<IngestionResult>('/arxiv/ingest', {
        paper_ids: selectedPaperIds,
        download_pdfs: downloadPdfs,
        extract_content: extractEntities,
        batch_size: 10
      });

      setProgress(100);
      setIngestionResult(result);
      setMessage(`✅ ${result.message} - ${result.paper_count} papers queued for processing`);
      
      // Clear selection after successful ingestion
      setSelectedPaperIds([]);
    } catch (error: any) {
      console.error('Ingestion failed:', error);
      setProgress(0);
      if (error.response?.status === 401) {
        setMessage('❌ Authentication failed. Please refresh the page and try again.');
      } else {
        setMessage(`❌ Ingestion failed: ${error.response?.data?.detail || error.message}`);
      }
    } finally {
      setIsIngesting(false);
    }
  };

  // Toggle paper selection
  const togglePaperSelection = (paperId: string) => {
    setSelectedPaperIds(prev => 
      prev.includes(paperId) 
        ? prev.filter(id => id !== paperId)
        : [...prev, paperId]
    );
  };

  // Select/deselect all papers
  const toggleSelectAll = () => {
    if (searchResults) {
      if (selectedPaperIds.length === searchResults.length) {
        setSelectedPaperIds([]);
      } else {
        setSelectedPaperIds(searchResults.map(p => p.id));
      }
    }
  };


  // Fetch statistics
  const fetchStats = async () => {
    try {
      const result = await apiClient.get<StatsResult>('/arxiv/tracking/stats');
      setStats(result);
    } catch (error: any) {
      console.error('Failed to fetch stats:', error);
    }
  };

  // Clean up old state
  const handleCleanup = async () => {
    try {
      await apiClient.post('/arxiv/tracking/cleanup', null, {
        params: { days: 90 }
      });
      setMessage('Cleanup completed');
      await fetchStats();
    } catch (error: any) {
      console.error('Cleanup failed:', error);
      setMessage(`Cleanup failed: ${error.message}`);
    }
  };

  // Handle feature extraction
  const handleExtractFeatures = async () => {
    setIsExtracting(true);
    setMessage('Extracting features...');
    setProgress(0);

    try {
      const paperIds = extractPaperIds
        .split('\n')
        .map(id => id.trim())
        .filter(id => id.length > 0);

      if (paperIds.length === 0) {
        setMessage('Please enter at least one paper ID');
        setIsExtracting(false);
        return;
      }

      const result = await apiClient.postWithLongTimeout<ExtractionResult>('/arxiv/extraction/extract-features', {
        paper_ids: paperIds,
        extract_entities: extractEntities,
        extract_topics: extractTopics,
        extract_citations: extractCitations,
        extract_keyphrases: extractKeyphrases,
        extract_summaries: extractSummaries,
        update_knowledge_graph: updateKG
      });

      setExtractionResult(result);
      setMessage(`Successfully extracted features from ${result.processed_count} papers`);
      setProgress(100);
    } catch (error: any) {
      console.error('Extraction failed:', error);
      setMessage(`Extraction failed: ${error.response?.data?.detail || error.message}`);
    } finally {
      setIsExtracting(false);
    }
  };

  // Handle bulk extraction
  const handleBulkExtract = async () => {
    setIsExtracting(true);
    setMessage('Bulk extracting features...');
    setProgress(0);

    try {
      const result = await apiClient.postWithLongTimeout<any>('/arxiv/extraction/bulk-extract', {
        categories: selectedCategories,
        days_back: daysBack,
        max_papers: maxResults,
        extraction_options: {
          extract_entities: extractEntities,
          extract_topics: extractTopics,
          extract_citations: extractCitations,
          extract_keyphrases: extractKeyphrases,
          extract_summaries: extractSummaries,
          update_knowledge_graph: updateKG
        }
      });

      setExtractionResult({
        status: result.status,
        message: result.message,
        processed_count: result.papers_processed,
        results: result.results || []
      });

      setMessage(`Bulk extraction completed: ${result.papers_processed} papers processed`);
      setProgress(100);
    } catch (error: any) {
      console.error('Bulk extraction failed:', error);
      setMessage(`Bulk extraction failed: ${error.response?.data?.detail || error.message}`);
    } finally {
      setIsExtracting(false);
    }
  };

  // Handle local PDF extraction
  const handleExtractLocalPdfs = async () => {
    setIsExtracting(true);
    setMessage('Extracting features from local PDF files...');
    setProgress(0);

    try {
      const { useAuthStore } = await import('@/stores/authStore');
      const authStore = useAuthStore.getState();

      if (!authStore.token) {
        setMessage('No authentication token found. Please log in first.');
        setIsExtracting(false);
        return;
      }

      setProgress(10);

      const response = await apiClient.postWithLongTimeout<{
        data?: {
          status: string;
          message: string;
          processed_count: number;
          results?: Array<any>;
        };
        status?: string;
        message?: string;
        processed_count?: number;
        results?: Array<any>;
      }>('/arxiv/local/extract-local-features', {
        paper_ids: null,
        extract_entities: extractEntities,
        extract_topics: extractTopics,
        extract_citations: extractCitations,
        extract_keyphrases: extractKeyphrases,
        extract_summaries: extractSummaries,
        process_full_content: true,
        update_knowledge_graph: updateKG
      });

      setProgress(80);

      const data = response.data || response;

      setExtractionResult({
        status: data.status ?? 'unknown',
        message: data.message ?? 'Extraction completed',
        processed_count: data.processed_count ?? 0,
        results: data.results || []
      });

      setMessage(`✅ Successfully extracted features from ${data.processed_count} local PDF files`);
      setProgress(100);
    } catch (error: any) {
      console.error('Local PDF extraction failed:', error);

      const status = error.response?.status || error.status;
      const detail = error.response?.data?.detail || error.message || error.toString();

      if (status === 401) {
        setMessage('❌ Authentication expired. Please refresh the page and log in again.');
      } else if (status === 403) {
        setMessage('❌ Access denied. You do not have permission to extract PDFs.');
      } else if (status === 404) {
        setMessage('❌ No local PDF files found. Please ensure PDF files are in the data directory.');
      } else if (status === 500) {
        setMessage('❌ Server error. Please check the backend logs for details.');
      } else {
        setMessage(`❌ Extraction failed: ${detail}`);
      }
      setProgress(0);
    } finally {
      setIsExtracting(false);
    }
  };

  // Initial stats fetch
  React.useEffect(() => {
    fetchStats();
  }, []);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="space-y-6 pt-6">
        <div className="flex items-center gap-4 pl-4">
          <Activity className="h-7 w-7" style={{ color: THEME.colors.primary }} />
          <h1 className="text-2xl font-mono font-bold tracking-tight" style={{ color: THEME.colors.primary }}>
            ARXIV MANAGEMENT TERMINAL_
          </h1>
        </div>
        <p className="text-white/50 font-mono text-sm pl-12">
          Track and ingest arXiv papers with knowledge graph integration
        </p>
      </div>

      {/* Terminal Chrome Tabs */}
      <div
        className="rounded-xl overflow-hidden"
        style={{
          background: THEME.colors.surface,
          border: `1px solid ${THEME.colors.border}`,
          boxShadow: '0 4px 24px rgba(0, 0, 0, 0.4)',
        }}
      >
        {/* Tab Bar */}
        <div
          className="flex items-center gap-2 px-5 py-4"
          style={{ borderBottom: `1px solid ${THEME.colors.border}`, background: THEME.colors.borderSubtle }}
        >
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className="flex items-center gap-2 px-4 py-2 rounded-lg font-mono text-sm transition-all"
                style={{
                  background: isActive ? THEME.colors.surface : 'transparent',
                  color: isActive ? THEME.colors.primary : THEME.colors.textMuted,
                  borderWidth: '1px',
                  borderStyle: 'solid',
                  borderColor: isActive ? `${THEME.colors.primary}30` : 'transparent',
                }}
              >
                <Icon className="h-4 w-4" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Tab Content */}
        <div className="p-10 pt-8 pl-12">
          {/* Track Changes Tab */}
          {activeTab === 'tracking' && (
            <div className="space-y-10">
              <div className="space-y-2">
                <h3 className="text-lg font-mono font-semibold text-white flex items-center gap-2">
                  <TrendingUp className="h-5 w-5" style={{ color: THEME.colors.accent }} />
                  Track ArXiv Changes
                </h3>
                <p className="text-sm font-mono text-gray-500">
                  Detect new, updated, and deleted papers in selected categories
                </p>
              </div>

              {/* Categories Selection */}
              <div className="space-y-5">
                <label className="text-sm font-mono text-gray-400 block">Categories to Track</label>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-x-6 gap-y-4">
                  {popularCategories.map((category) => (
                    <div key={category} className="flex items-center gap-2">
                      <ToggleSwitch
                        checked={selectedCategories.includes(category)}
                        onCheckedChange={(checked) => {
                          if (checked) {
                            setSelectedCategories([...selectedCategories, category]);
                          } else {
                            setSelectedCategories(selectedCategories.filter(c => c !== category));
                          }
                        }}
                      />
                      <span className="text-sm font-mono text-gray-300">{category}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Days Back Slider */}
              <div className="space-y-5">
                <label className="text-sm font-mono text-gray-400 block">
                  Days to look back: <span style={{ color: THEME.colors.primary }}>{daysBack}</span>
                </label>
                <CustomSlider
                  value={daysBack}
                  onChange={setDaysBack}
                  min={1}
                  max={30}
                  step={1}
                />
              </div>

              {/* Update Database Toggle */}
              <div className="flex items-center gap-3">
                <ToggleSwitch
                  id="update-db"
                  checked={updateDatabase}
                  onCheckedChange={setUpdateDatabase}
                />
                <label htmlFor="update-db" className="text-sm font-mono text-gray-300">
                  Update database with changes
                </label>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-4">
                <button
                  onClick={handleTrackChanges}
                  disabled={isTracking || selectedCategories.length === 0}
                  className="flex items-center gap-2 px-5 py-2.5 rounded-lg font-mono text-sm transition-all disabled:opacity-40"
                  style={{
                    background: `${THEME.colors.primary}20`,
                    borderWidth: '1px',
                    borderStyle: 'solid',
                    borderColor: `${THEME.colors.primary}50`,
                    color: THEME.colors.primary,
                  }}
                >
                  {isTracking ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Tracking...
                    </>
                  ) : (
                    <>
                      <RefreshCw className="h-4 w-4" />
                      Track Changes
                    </>
                  )}
                </button>

                <button
                  onClick={handleCleanup}
                  className="flex items-center gap-2 px-5 py-2.5 rounded-lg font-mono text-sm transition-all"
                  style={{
                    background: 'transparent',
                    borderWidth: '1px',
                    borderStyle: 'solid',
                    borderColor: THEME.colors.border,
                    color: THEME.colors.textMuted,
                  }}
                >
                  Cleanup Old State
                </button>
              </div>

              {/* Progress */}
              {(isTracking || message) && (
                <div className="space-y-3">
                  <ProgressBar value={progress} />
                  <p className="text-sm font-mono text-gray-400">{message}</p>
                </div>
              )}

              {/* Results */}
              {trackingResult && (
                <div className="space-y-4">
                    <div
                      className="flex items-start gap-3 p-4 rounded-lg"
                      style={{
                        background: `${THEME.colors.primary}10`,
                        border: `1px solid ${THEME.colors.primary}30`,
                      }}
                    >
                      <CheckCircle className="h-5 w-5 mt-0.5" style={{ color: THEME.colors.primary }} />
                      <p className="text-sm font-mono" style={{ color: THEME.colors.primary }}>
                        {trackingResult.result.applied ? (
                          <>
                            Successfully tracked and updated database!
                            Found {trackingResult.result.papers_found} papers with {trackingResult.result.changes_detected} changes.
                          </>
                        ) : (
                          <>
                            Tracking completed (read-only).
                            Found {trackingResult.result.papers_found} papers with {trackingResult.result.changes_detected} changes.
                          </>
                        )}
                    </p>
                  </div>

                  <div className="grid grid-cols-3 gap-4">
                    {[
                      { label: 'New Papers', value: trackingResult.result.summary.new, color: THEME.colors.primary },
                      { label: 'Updated', value: trackingResult.result.summary.updated, color: THEME.colors.secondary },
                      { label: 'Deleted', value: trackingResult.result.summary.deleted, color: THEME.colors.error },
                    ].map((stat) => (
                      <div
                        key={stat.label}
                        className="p-4 rounded-lg"
                        style={{ background: THEME.colors.borderSubtle, border: `1px solid ${THEME.colors.borderMuted}` }}
                      >
                        <div className="text-2xl font-mono font-bold" style={{ color: stat.color }}>
                          {stat.value}
                        </div>
                        <p className="text-sm font-mono text-gray-500">{stat.label}</p>
                      </div>
                    ))}
                  </div>

                  {trackingResult.result.applied && (
                    <div
                      className="flex items-start gap-3 p-4 rounded-lg"
                      style={{
                        background: `${THEME.colors.secondary}10`,
                        border: `1px solid ${THEME.colors.secondary}30`,
                      }}
                    >
                      <Database className="h-5 w-5 mt-0.5" style={{ color: THEME.colors.secondary }} />
                      <p className="text-sm font-mono" style={{ color: THEME.colors.secondary }}>
                        Papers have been added to PostgreSQL and entities/relationships have been extracted to Neo4j knowledge graph.
                        Visit{' '}
                        <a
                          href="http://localhost:7474/browser/"
                          target="_blank"
                          rel="noopener noreferrer"
                          className="underline"
                        >
                          Neo4j Browser
                        </a>{' '}
                        to explore the knowledge graph.
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Ingest Papers Tab */}
          {activeTab === 'ingest' && (
            <div className="space-y-10">
              <div className="space-y-2">
                <h3 className="text-lg font-mono font-semibold text-white flex items-center gap-2">
                  <Upload className="h-5 w-5" style={{ color: THEME.colors.secondary }} />
                  Ingest ArXiv Papers
                </h3>
                <p className="text-sm font-mono text-gray-500">
                  Search and ingest papers from arXiv with knowledge graph extraction
                </p>
              </div>

              {/* Search Form */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <label className="text-sm font-mono text-gray-400">Search Query</label>
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSearchPapers()}
                    placeholder="e.g., quantum computing, machine learning"
                    className="w-full px-4 py-2.5 rounded-lg font-mono text-sm text-white placeholder:text-gray-600 focus:outline-none"
                    style={{
                      background: THEME.colors.borderSubtle,
                      border: `1px solid ${THEME.colors.borderMuted}`,
                    }}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-mono text-gray-400">
                    Max Results: <span style={{ color: THEME.colors.primary }}>{maxResults}</span>
                  </label>
                  <CustomSlider
                    value={maxResults}
                    onChange={setMaxResults}
                    min={1}
                    max={100}
                    step={1}
                  />
                </div>
              </div>

              {/* Options */}
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <ToggleSwitch
                    id="extract-entities"
                    checked={extractEntities}
                    onCheckedChange={setExtractEntities}
                  />
                  <label htmlFor="extract-entities" className="text-sm font-mono text-gray-300">
                    Extract entities to knowledge graph
                  </label>
                </div>
                <div className="flex items-center gap-3">
                  <ToggleSwitch
                    id="download-pdfs"
                    checked={downloadPdfs}
                    onCheckedChange={setDownloadPdfs}
                  />
                  <label htmlFor="download-pdfs" className="text-sm font-mono text-gray-300">
                    Download PDF files
                  </label>
                </div>
              </div>

              {/* Search Button */}
              <button
                onClick={handleSearchPapers}
                disabled={isSearching || !searchQuery.trim()}
                className="w-full flex items-center justify-center gap-2 px-5 py-3 rounded-lg font-mono text-sm transition-all disabled:opacity-40"
                style={{
                  background: `${THEME.colors.secondary}20`,
                  borderWidth: '1px',
                  borderStyle: 'solid',
                  borderColor: `${THEME.colors.secondary}50`,
                  color: THEME.colors.secondary,
                }}
              >
                {isSearching ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Searching...
                  </>
                ) : (
                  <>
                    <Search className="h-4 w-4" />
                    Search ArXiv Papers
                  </>
                )}
              </button>

              {/* Progress and Message */}
              {(isSearching || isIngesting || message) && (
                <div className="space-y-3">
                  <ProgressBar value={progress} />
                  <p className="text-sm font-mono text-gray-400">{message}</p>
                </div>
              )}

              {/* Search Results */}
              {searchResults && searchResults.length > 0 && (
                <div className="space-y-4">
                  {/* Results Header with Select All */}
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-mono text-gray-400">
                      {searchResults.length} papers found • {selectedPaperIds.length} selected
                    </h4>
                    <button
                      onClick={toggleSelectAll}
                      className="flex items-center gap-2 px-3 py-1.5 rounded font-mono text-xs transition-all"
                      style={{
                        background: 'transparent',
                        border: `1px solid ${THEME.colors.border}`,
                        color: THEME.colors.textMuted,
                      }}
                    >
                      {selectedPaperIds.length === searchResults.length ? (
                        <>
                          <Square className="h-3 w-3" />
                          Deselect All
                        </>
                      ) : (
                        <>
                          <CheckSquare className="h-3 w-3" />
                          Select All
                        </>
                      )}
                    </button>
                  </div>

                  {/* Paper List */}
                  <div 
                    className="space-y-3 max-h-96 overflow-y-auto pr-2"
                    style={{ scrollbarWidth: 'thin', scrollbarColor: `${THEME.colors.primary}40 ${THEME.colors.borderSubtle}` }}
                  >
                    {searchResults.map((paper) => (
                      <div
                        key={paper.id}
                        onClick={() => togglePaperSelection(paper.id)}
                        className="p-4 rounded-lg cursor-pointer transition-all"
                        style={{
                          background: selectedPaperIds.includes(paper.id) ? `${THEME.colors.primary}10` : THEME.colors.borderSubtle,
                          border: `1px solid ${selectedPaperIds.includes(paper.id) ? `${THEME.colors.primary}40` : THEME.colors.borderMuted}`,
                        }}
                      >
                        <div className="flex items-start gap-3">
                          <div className="pt-1">
                            {selectedPaperIds.includes(paper.id) ? (
                              <CheckSquare className="h-5 w-5" style={{ color: THEME.colors.primary }} />
                            ) : (
                              <Square className="h-5 w-5 text-gray-600" />
                            )}
                          </div>
                          <div className="flex-1 min-w-0">
                            <h5 className="text-sm font-mono text-white font-medium leading-snug">
                              {paper.title}
                            </h5>
                            <p className="text-xs font-mono text-gray-500 mt-1">
                              {paper.authors.slice(0, 3).join(', ')}
                              {paper.authors.length > 3 && ` +${paper.authors.length - 3} more`}
                            </p>
                            <p className="text-xs font-mono text-gray-600 mt-2 line-clamp-2">
                              {paper.abstract.slice(0, 200)}...
                            </p>
                            <div className="flex items-center gap-2 mt-2">
                              <span 
                                className="text-xs font-mono px-2 py-0.5 rounded"
                                style={{ background: `${THEME.colors.secondary}20`, color: THEME.colors.secondary }}
                              >
                                {paper.id}
                              </span>
                              {paper.categories.slice(0, 2).map((cat) => (
                                <span 
                                  key={cat}
                                  className="text-xs font-mono px-2 py-0.5 rounded"
                                  style={{ background: `${THEME.colors.accent}20`, color: THEME.colors.accent }}
                                >
                                  {cat}
                                </span>
                              ))}
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Ingest Selected Button */}
                  {selectedPaperIds.length > 0 && (
                    <button
                      onClick={handleIngestSelected}
                      disabled={isIngesting}
                      className="w-full flex items-center justify-center gap-2 px-5 py-3 rounded-lg font-mono text-sm transition-all disabled:opacity-40"
                      style={{
                        background: `${THEME.colors.primary}20`,
                        borderWidth: '1px',
                        borderStyle: 'solid',
                        borderColor: `${THEME.colors.primary}50`,
                        color: THEME.colors.primary,
                      }}
                    >
                      {isIngesting ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Ingesting {selectedPaperIds.length} papers...
                        </>
                      ) : (
                        <>
                          <Database className="h-4 w-4" />
                          Ingest {selectedPaperIds.length} Selected Paper{selectedPaperIds.length > 1 ? 's' : ''}
                        </>
                      )}
                    </button>
                  )}
                </div>
              )}

              {/* Ingestion Success */}
              {ingestionResult && (
                  <div
                    className="flex items-start gap-3 p-4 rounded-lg"
                    style={{
                      background: `${THEME.colors.primary}10`,
                      border: `1px solid ${THEME.colors.primary}30`,
                    }}
                  >
                    <CheckCircle className="h-5 w-5 mt-0.5" style={{ color: THEME.colors.primary }} />
                    <div>
                      <p className="text-sm font-mono" style={{ color: THEME.colors.primary }}>
                        {ingestionResult.message}
                      </p>
                    <p className="text-xs font-mono text-gray-500 mt-1">
                      {ingestionResult.paper_count} papers queued for background processing.
                      Check the Statistics tab to monitor progress.
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Extract Features Tab */}
          {activeTab === 'extract' && (
            <div className="space-y-10">
              <div className="space-y-2">
                <h3 className="text-lg font-mono font-semibold text-white flex items-center gap-2">
                  <Brain className="h-5 w-5" style={{ color: THEME.colors.accent }} />
                  Extract Features from Papers
                </h3>
                <p className="text-sm font-mono text-gray-500">
                  Extract entities, topics, key phrases, summaries, and citations from ArXiv papers
                </p>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-mono text-gray-400">Paper IDs (one per line)</label>
                <textarea
                  placeholder="e.g.,&#10;2301.07041&#10;2302.08869&#10;2303.12345"
                  value={extractPaperIds}
                  onChange={(e) => setExtractPaperIds(e.target.value)}
                  className="w-full h-32 px-4 py-3 rounded-lg font-mono text-sm text-white placeholder:text-gray-600 focus:outline-none resize-none"
                  style={{
                    background: THEME.colors.borderSubtle,
                    border: `1px solid ${THEME.colors.borderMuted}`,
                  }}
                />
              </div>

              <div className="space-y-4">
                <h4 className="text-sm font-mono text-gray-400">Features to Extract:</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {[
                    { id: 'entities', label: 'Entities', icon: FileText, checked: extractEntities, onChange: setExtractEntities },
                    { id: 'topics', label: 'Topics', icon: BookOpen, checked: extractTopics, onChange: setExtractTopics },
                    { id: 'keyphrases', label: 'Key Phrases', icon: Hash, checked: extractKeyphrases, onChange: setExtractKeyphrases },
                    { id: 'citations', label: 'Citations', icon: Link2, checked: extractCitations, onChange: setExtractCitations },
                  ].map((feature) => {
                    const Icon = feature.icon;
                    return (
                      <div key={feature.id} className="flex items-center gap-3">
                        <ToggleSwitch
                          id={feature.id}
                          checked={feature.checked}
                          onCheckedChange={feature.onChange}
                        />
                        <label htmlFor={feature.id} className="flex items-center gap-2 text-sm font-mono text-gray-300">
                          <Icon className="h-4 w-4 text-gray-500" />
                          {feature.label}
                        </label>
                      </div>
                    );
                  })}
                </div>
                <div className="flex items-center gap-3">
                  <ToggleSwitch
                    id="summaries"
                    checked={extractSummaries}
                    onCheckedChange={setExtractSummaries}
                  />
                  <label htmlFor="summaries" className="text-sm font-mono text-gray-300">
                    Generate Summaries
                  </label>
                </div>
                <div className="flex items-center gap-3">
                  <ToggleSwitch
                    id="update-kg"
                    checked={updateKG}
                    onCheckedChange={setUpdateKG}
                  />
                  <label htmlFor="update-kg" className="text-sm font-mono text-gray-300">
                    Update Knowledge Graph
                  </label>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-4">
                <button
                  onClick={handleExtractFeatures}
                  disabled={isExtracting || extractPaperIds.trim().length === 0}
                  className="flex items-center gap-2 px-5 py-2.5 rounded-lg font-mono text-sm transition-all disabled:opacity-40"
                  style={{
                    background: `${THEME.colors.accent}20`,
                    borderWidth: '1px',
                    borderStyle: 'solid',
                    borderColor: `${THEME.colors.accent}50`,
                    color: THEME.colors.accent,
                  }}
                >
                  {isExtracting ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Extracting...
                    </>
                  ) : (
                    <>
                      <Brain className="h-4 w-4" />
                      Extract Features
                    </>
                  )}
                </button>

                <button
                  onClick={handleBulkExtract}
                  disabled={isExtracting}
                  className="flex items-center gap-2 px-5 py-2.5 rounded-lg font-mono text-sm transition-all disabled:opacity-40"
                  style={{
                    background: 'transparent',
                    borderWidth: '1px',
                    borderStyle: 'solid',
                    borderColor: THEME.colors.border,
                    color: THEME.colors.textMuted,
                  }}
                >
                  Bulk Extract from Categories
                </button>

                <button
                  onClick={handleExtractLocalPdfs}
                  disabled={isExtracting}
                  className="flex items-center gap-2 px-5 py-2.5 rounded-lg font-mono text-sm transition-all disabled:opacity-40"
                  style={{
                    background: THEME.colors.borderSubtle,
                    borderWidth: '1px',
                    borderStyle: 'solid',
                    borderColor: THEME.colors.border,
                    color: THEME.colors.textMuted,
                  }}
                >
                  Extract from Local PDFs
                </button>
              </div>

              {(isExtracting || message) && (
                <div className="space-y-3">
                  <ProgressBar value={progress} />
                  <p className="text-sm font-mono text-gray-400">{message}</p>
                </div>
              )}

              {extractionResult && (
                <div className="space-y-4">
                  <div
                    className="flex items-start gap-3 p-4 rounded-lg"
                    style={{
                      background: `${THEME.colors.primary}10`,
                      border: `1px solid ${THEME.colors.primary}30`,
                    }}
                  >
                    <CheckCircle className="h-5 w-5 mt-0.5" style={{ color: THEME.colors.primary }} />
                    <p className="text-sm font-mono" style={{ color: THEME.colors.primary }}>
                      {extractionResult.message}
                    </p>
                  </div>

                  <div className="space-y-3">
                    {extractionResult.results.map((result, index) => (
                      <div
                        key={index}
                        className="p-4 rounded-lg"
                        style={{ background: THEME.colors.borderSubtle, border: `1px solid ${THEME.colors.borderMuted}` }}
                      >
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex-1 min-w-0 mr-3">
                            <h4 className="text-sm font-mono font-medium text-white truncate">
                              {result.title}
                            </h4>
                            <p className="text-xs font-mono text-gray-500">{result.paper_id}</p>
                          </div>
                          <span
                            className="text-xs font-mono px-2 py-1 rounded"
                            style={{
                              background: result.extraction_status === 'completed' ? `${THEME.colors.primary}20` : `${THEME.colors.error}20`,
                              color: result.extraction_status === 'completed' ? THEME.colors.primary : THEME.colors.error,
                            }}
                          >
                            {result.extraction_status}
                          </span>
                        </div>

                        {result.error && (
                          <p className="text-xs font-mono text-red-400 mt-2">Error: {result.error}</p>
                        )}

                        {result.extraction_status === 'completed' && (
                          <div className="space-y-2 mt-3">
                            {result.features.topics && Array.isArray(result.features.topics) && (
                              <div>
                                <p className="text-xs font-mono text-gray-500 mb-1">Topics:</p>
                                <div className="flex flex-wrap gap-1">
                                  {result.features.topics.map((topic, i) => (
                                    <span
                                      key={i}
                                      className="text-xs font-mono px-2 py-0.5 rounded"
                                      style={{ background: THEME.colors.borderMuted, color: THEME.colors.textMuted }}
                                    >
                                      {topic}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            )}
                            {result.features.keyphrases && Array.isArray(result.features.keyphrases) && (
                              <div>
                                <p className="text-xs font-mono text-gray-500 mb-1">Key Phrases:</p>
                                <p className="text-xs font-mono text-gray-400 truncate">
                                  {result.features.keyphrases.join(', ')}
                                </p>
                              </div>
                            )}
                            {result.features.summary && typeof result.features.summary === 'string' && (
                              <div>
                                <p className="text-xs font-mono text-gray-500 mb-1">Summary:</p>
                                <p className="text-xs font-mono text-gray-400 line-clamp-3">
                                  {result.features.summary}
                                </p>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Statistics Tab */}
          {activeTab === 'stats' && (
            <div className="space-y-10">
              {stats && (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  {[
                    { label: 'Total Papers Tracked', value: stats.statistics.total_papers_tracked, color: THEME.colors.textMuted },
                    { label: 'Active Papers', value: stats.statistics.active_papers, color: THEME.colors.primary },
                    { label: 'Categories Tracked', value: stats.statistics.categories_tracked, color: THEME.colors.secondary },
                    { label: 'New This Week', value: stats.statistics.recent_changes_week?.new || 0, color: THEME.colors.accent },
                  ].map((stat) => (
                    <div
                      key={stat.label}
                      className="p-5 rounded-lg"
                      style={{ background: THEME.colors.borderSubtle, border: `1px solid ${THEME.colors.borderMuted}` }}
                    >
                      <div className="text-3xl font-mono font-bold" style={{ color: stat.color }}>
                        {stat.value}
                      </div>
                      <p className="text-sm font-mono text-gray-500 mt-1">{stat.label}</p>
                    </div>
                  ))}
                </div>
              )}

              <div
                className="p-5 rounded-lg"
                style={{ background: THEME.colors.borderSubtle, border: `1px solid ${THEME.colors.borderMuted}` }}
              >
                <h3 className="text-lg font-mono font-semibold text-white mb-4">Top Categories</h3>
                <div className="space-y-3">
                  {stats?.statistics.top_categories?.map(([category, count]) => (
                    <div
                      key={category}
                      className="flex items-center justify-between py-2"
                      style={{ borderBottom: `1px solid ${THEME.colors.borderMuted}` }}
                    >
                      <span
                        className="text-sm font-mono px-2 py-1 rounded"
                        style={{ background: THEME.colors.borderMuted, color: THEME.colors.textMuted }}
                      >
                        {category}
                      </span>
                      <span className="text-sm font-mono" style={{ color: THEME.colors.primary }}>
                        {count} papers
                      </span>
                    </div>
                  ))}
                  {(!stats?.statistics.top_categories || stats.statistics.top_categories.length === 0) && (
                    <p className="text-sm font-mono text-gray-500">No categories tracked yet</p>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
