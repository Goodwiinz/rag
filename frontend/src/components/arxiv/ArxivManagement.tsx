"use client";

import { apiClient } from '@/services/apiClient';
import { cn } from '@/lib/utils';
import { 
  Activity, 
  BarChart3, 
  BookOpen, 
  Brain, 
  CheckCircle, 
  CheckSquare, 
  Database, 
  FileText, 
  Hash, 
  Link2, 
  Loader2, 
  RefreshCw, 
  Search, 
  Square, 
  TrendingUp, 
  Upload,
  ChevronRight,
  Terminal,
  AlertTriangle,
  Zap,
  Cpu,
  Globe,
  Layers
} from 'lucide-react';
import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

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

// Custom Toggle Switch Component
const ToggleSwitch: React.FC<{
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  id?: string;
  label?: string;
}> = ({ checked, onCheckedChange, id, label }) => (
  <div className="flex items-center gap-3 group cursor-pointer" onClick={() => onCheckedChange(!checked)}>
    <button
      id={id}
      type="button"
      role="switch"
      aria-checked={checked}
      className={cn(
        "relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-all duration-200 border",
        checked 
          ? "bg-[var(--phosphor-green)]/20 border-[var(--phosphor-green)]/50" 
          : "bg-[var(--terminal-surface)] border-[var(--terminal-border)] group-hover:border-[var(--terminal-border-muted)]"
      )}
    >
      <span
        className={cn(
          "pointer-events-none block h-3.5 w-3.5 rounded-full transition-transform duration-200 mt-[2px] ml-[2px]",
          checked 
            ? "translate-x-4 bg-[var(--phosphor-green)] shadow-[0_0_8px_var(--phosphor-green)]" 
            : "translate-x-0 bg-[var(--terminal-text-muted)]"
        )}
      />
    </button>
    {label && (
      <span className="text-[10px] font-mono font-bold text-[var(--terminal-text-dim)] uppercase tracking-wider group-hover:text-[var(--terminal-text)] transition-colors">
        {label}
      </span>
    )}
  </div>
);

// Custom Progress Bar
const ProgressBar: React.FC<{ value: number; label?: string }> = ({ value, label }) => (
  <div className="space-y-1.5 w-full">
    {label && (
      <div className="flex justify-between items-center text-[9px] font-mono text-[var(--terminal-text-muted)] uppercase tracking-widest">
        <span>{label}</span>
        <span className="text-[var(--phosphor-green)]">{Math.round(value)}%</span>
      </div>
    )}
    <div className="h-1 w-full rounded-full bg-[var(--terminal-border)] overflow-hidden">
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: `${value}%` }}
        transition={{ duration: 0.5, ease: "easeOut" }}
        className="h-full rounded-full bg-gradient-to-r from-[var(--phosphor-green-dim)] to-[var(--phosphor-green)] shadow-[0_0_10px_var(--phosphor-green-muted)]"
      />
    </div>
  </div>
);

// Custom Slider Component
const CustomSlider: React.FC<{
  value: number;
  onChange: (value: number) => void;
  min: number;
  max: number;
  step: number;
  label: string;
}> = ({ value, onChange, min, max, step, label }) => (
  <div className="space-y-3">
    <div className="flex justify-between items-center">
      <label className="text-[10px] font-mono font-bold text-[var(--terminal-text-muted)] uppercase tracking-widest">
        {label}
      </label>
      <span className="text-[10px] font-mono font-bold text-[var(--phosphor-green)] bg-[var(--phosphor-green)]/10 px-2 py-0.5 rounded border border-[var(--phosphor-green)]/20">
        {value}
      </span>
    </div>
    <div className="relative flex items-center h-6">
      <input
        type="range"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        min={min}
        max={max}
        step={step}
        className="w-full h-1 bg-[var(--terminal-border)] rounded-full appearance-none cursor-pointer accent-[var(--phosphor-green)] hover:accent-[var(--phosphor-green-dim)] transition-all"
      />
    </div>
  </div>
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
    { id: 'tracking', label: 'TRACK_CHANGES', icon: TrendingUp },
    { id: 'ingest', label: 'INGEST_PAPERS', icon: Upload },
    { id: 'extract', label: 'EXTRACT_FEATURES', icon: Brain },
    { id: 'stats', label: 'STATISTICS', icon: BarChart3 },
  ];

  // Fetch statistics
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
        setMessage(`COMPLETED: Database updated with ${result.result.summary.new} new papers.`);
      } else {
        setMessage(`COMPLETED: Found ${result.result.summary.new} new, ${result.result.summary.updated} updated papers.`);
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
    setMessage(`Searching arXiv for "${searchQuery}"...`);
    setProgress(10);
    setSearchResults(null);
    setSelectedPaperIds([]);

    try {
      setProgress(40);
      const results = await apiClient.postWithLongTimeout<ArXivPaper[]>('/arxiv/search', {
        query: searchQuery,
        max_results: maxResults,
        categories: selectedCategories.length > 0 ? selectedCategories : null
      });
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

  return (
    <div className="space-y-6 pt-4">
      {/* Header - Unified Style */}
      <div className="flex items-center justify-between px-2">
        <div className="flex items-center gap-4">
          <div className="p-2 rounded-lg bg-[var(--phosphor-green)]/10 border border-[var(--phosphor-green)]/20 shadow-[0_0_15px_rgba(0,255,159,0.1)]">
            <Activity className="h-6 w-6 text-[var(--phosphor-green)]" />
          </div>
          <div>
            <h1 className="text-xl font-mono font-bold text-[var(--terminal-text)] tracking-tighter uppercase">
              ARXIV_MANAGEMENT_TERMINAL
            </h1>
            <div className="flex items-center gap-2 mt-0.5">
              <div className="w-1.5 h-1.5 rounded-full bg-[var(--phosphor-green)] animate-pulse" />
              <span className="text-[9px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-[0.2em]">
                Neural Research Node :: Connection Optimal
              </span>
            </div>
          </div>
        </div>
        
        {stats && (
          <div className="hidden md:flex items-center gap-6 px-4 py-2 rounded-xl bg-[var(--terminal-surface)]/50 border border-[var(--terminal-border)]">
            <div className="flex flex-col items-end">
              <span className="text-[8px] font-mono text-[var(--terminal-text-muted)] uppercase tracking-widest">Global Tracked</span>
              <span className="text-sm font-mono font-bold text-[var(--phosphor-green)]">{stats.statistics.total_papers_tracked}</span>
            </div>
            <div className="w-px h-8 bg-[var(--terminal-border)]" />
            <div className="flex flex-col items-end">
              <span className="text-[8px] font-mono text-[var(--terminal-text-muted)] uppercase tracking-widest">Active Core</span>
              <span className="text-sm font-mono font-bold text-[var(--cyan)]">{stats.statistics.active_papers}</span>
            </div>
          </div>
        )}
      </div>

      {/* Main Terminal Chrome */}
      <div className="relative rounded-2xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)]/80 backdrop-blur-xl overflow-hidden shadow-2xl">
        {/* Tab Header */}
        <div className="flex items-center justify-between px-4 bg-[var(--terminal-elevated)]/50 border-b border-[var(--terminal-border)] h-12">
          <div className="flex h-full">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={cn(
                    "flex items-center gap-2 px-5 h-full font-mono text-[10px] font-bold uppercase tracking-wider transition-all relative",
                    isActive 
                      ? "text-[var(--phosphor-green)]" 
                      : "text-[var(--terminal-text-muted)] hover:text-[var(--terminal-text-dim)]"
                  )}
                >
                  <Icon className={cn("h-3.5 w-3.5", isActive ? "text-[var(--phosphor-green)]" : "text-[var(--terminal-text-muted)]")} />
                  {tab.label}
                  {isActive && (
                    <motion.div 
                      layoutId="activeTabArxiv"
                      className="absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--phosphor-green)] shadow-[0_0_10px_var(--phosphor-green)]"
                    />
                  )}
                </button>
              );
            })}
          </div>
          
          <div className="flex items-center gap-3">
            <span className="text-[9px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-tighter opacity-50">
              MODULE_ID: ARX-092
            </span>
          </div>
        </div>

        {/* Transmission Line Component (Vertical Decoration) */}
        <div className="absolute top-12 left-6 bottom-0 w-[1px] bg-gradient-to-b from-[var(--phosphor-green)]/20 via-[var(--terminal-border)] to-transparent pointer-events-none" />

        {/* Content Area */}
        <div className="p-8 pl-14">
          <AnimatePresence mode="wait">
            <motion.div
              key={activeTab}
              initial={{ opacity: 0, x: 10, filter: 'blur(10px)' }}
              animate={{ opacity: 1, x: 0, filter: 'blur(0px)' }}
              exit={{ opacity: 0, x: -10, filter: 'blur(10px)' }}
              transition={{ duration: 0.3 }}
              className="min-h-[400px]"
            >
              {/* Tab: Tracking */}
              {activeTab === 'tracking' && (
                <div className="space-y-8 max-w-4xl">
                  <div className="space-y-1">
                    <h3 className="text-sm font-mono font-bold text-[var(--terminal-text)] flex items-center gap-2 uppercase tracking-tight">
                      <TrendingUp className="h-4 w-4 text-[var(--amber-gold)]" />
                      Protocol: Detect_Global_Changes
                    </h3>
                    <p className="text-[11px] font-mono text-[var(--terminal-text-muted)] leading-relaxed">
                      Initialize category-wide system scans to synchronize with ArXiv repository updates.
                    </p>
                  </div>

                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                    {/* Left Column: Config */}
                    <div className="space-y-6">
                      <div className="p-5 rounded-xl bg-[var(--terminal-bg)]/50 border border-[var(--terminal-border)] space-y-5">
                        <label className="text-[10px] font-mono font-bold text-[var(--terminal-text-dim)] uppercase tracking-widest block mb-2">
                          Neural Category Filter
                        </label>
                        <div className="grid grid-cols-2 gap-3">
                          {popularCategories.map((category) => (
                            <div key={category} className="flex items-center gap-2">
                              <ToggleSwitch
                                checked={selectedCategories.includes(category)}
                                onCheckedChange={(checked) => {
                                  if (checked) setSelectedCategories([...selectedCategories, category]);
                                  else setSelectedCategories(selectedCategories.filter(c => c !== category));
                                }}
                                label={category}
                              />
                            </div>
                          ))}
                        </div>
                      </div>

                      <div className="p-5 rounded-xl bg-[var(--terminal-bg)]/50 border border-[var(--terminal-border)] space-y-6">
                        <CustomSlider
                          label="Temporal Depth (Days)"
                          value={daysBack}
                          onChange={setDaysBack}
                          min={1}
                          max={30}
                          step={1}
                        />
                        
                        <div className="pt-2">
                          <ToggleSwitch
                            id="update-db"
                            checked={updateDatabase}
                            onCheckedChange={setUpdateDatabase}
                            label="AUTO_UPDATE_DATABASE"
                          />
                        </div>
                      </div>

                      <div className="flex items-center gap-4">
                        <button
                          onClick={handleTrackChanges}
                          disabled={isTracking || selectedCategories.length === 0}
                          className={cn(
                            "flex items-center gap-2 px-6 py-2.5 rounded-lg font-mono text-[11px] font-bold uppercase transition-all shadow-lg",
                            "bg-[var(--phosphor-green)] text-[var(--terminal-bg)] hover:shadow-[0_0_20px_var(--phosphor-green-glow)] active:scale-95 disabled:opacity-40"
                          )}
                        >
                          {isTracking ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                          INITIALIZE_SCAN
                        </button>
                        
                        <button
                          onClick={fetchStats}
                          className="px-6 py-2.5 rounded-lg font-mono text-[11px] font-bold uppercase border border-[var(--terminal-border)] text-[var(--terminal-text-muted)] hover:bg-[var(--terminal-elevated)] transition-all"
                        >
                          REFRESH_METRICS
                        </button>
                      </div>
                    </div>

                    {/* Right Column: Status & Output */}
                    <div className="space-y-6">
                      <div className="p-5 rounded-xl bg-[var(--terminal-bg)] border border-[var(--terminal-border)] min-h-[300px] flex flex-col relative overflow-hidden">
                        {/* Status Overlay */}
                        <div className="flex items-center justify-between mb-4 border-b border-[var(--terminal-border)] pb-3">
                          <span className="text-[9px] font-mono font-bold text-[var(--terminal-text-dim)] uppercase tracking-widest">System_Console_Output</span>
                          <span className="flex items-center gap-1.5 text-[9px] font-mono text-[var(--phosphor-green)]">
                            <div className="w-1 h-1 rounded-full bg-[var(--phosphor-green)] animate-pulse" />
                            LIVE
                          </span>
                        </div>

                        {/* Progress */}
                        {(isTracking || message) && (
                          <div className="space-y-4 mb-6">
                            <ProgressBar value={progress} label="Scan_Synchronizing" />
                            <p className="text-[10px] font-mono text-[var(--terminal-text-dim)] bg-[var(--terminal-elevated)] p-2.5 rounded border border-[var(--terminal-border)] italic leading-relaxed">
                              {"> "} {message}
                            </p>
                          </div>
                        )}

                        {/* Results Panel */}
                        {trackingResult && !isTracking && (
                          <div className="space-y-4 animate-in fade-in slide-in-from-bottom-2">
                            <div className="grid grid-cols-3 gap-2">
                              {[
                                { label: 'NEW', value: trackingResult.result.summary.new, color: 'text-[var(--phosphor-green)]' },
                                { label: 'UPD', value: trackingResult.result.summary.updated, color: 'text-[var(--cyan)]' },
                                { label: 'DEL', value: trackingResult.result.summary.deleted, color: 'text-[var(--amber-gold)]' },
                              ].map((stat) => (
                                <div key={stat.label} className="p-3 rounded-lg bg-[var(--terminal-surface)] border border-[var(--terminal-border)] text-center">
                                  <div className={cn("text-xl font-mono font-bold", stat.color)}>{stat.value}</div>
                                  <div className="text-[8px] font-mono text-[var(--terminal-text-muted)] uppercase mt-1">{stat.label}</div>
                                </div>
                              ))}
                            </div>
                            
                            {trackingResult.result.applied && (
                              <div className="p-3 rounded-lg bg-[var(--phosphor-green)]/5 border border-[var(--phosphor-green)]/20 flex items-start gap-3">
                                <Database className="h-4 w-4 text-[var(--phosphor-green)] shrink-0 mt-0.5" />
                                <div className="space-y-1">
                                  <p className="text-[10px] font-mono text-[var(--terminal-text)] font-bold uppercase">KG_LINK_ESTABLISHED</p>
                                  <p className="text-[9px] font-mono text-[var(--terminal-text-muted)] leading-tight">
                                    Entity extraction completed. Nodes synchronized with Neo4j graph registry.
                                  </p>
                                </div>
                              </div>
                            )}
                          </div>
                        )}

                        {!isTracking && !message && !trackingResult && (
                          <div className="flex-1 flex flex-col items-center justify-center opacity-30">
                            <Terminal className="h-8 w-8 text-[var(--terminal-text-muted)] mb-3" />
                            <p className="text-[9px] font-mono text-[var(--terminal-text-muted)] uppercase tracking-[0.2em]">Awaiting Instruction</p>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Ingest Tab - Placeholder for visual parity */}
              {activeTab === 'ingest' && (
                <div className="space-y-8 max-w-4xl">
                  <div className="space-y-1">
                    <h3 className="text-sm font-mono font-bold text-[var(--terminal-text)] flex items-center gap-2 uppercase tracking-tight">
                      <Upload className="h-4 w-4 text-[var(--cyan)]" />
                      Protocol: Targeted_Node_Ingestion
                    </h3>
                    <p className="text-[11px] font-mono text-[var(--terminal-text-muted)] leading-relaxed">
                      Search and ingest specific research nodes directly into the RAG intelligence grid.
                    </p>
                  </div>

                  <div className="flex flex-col gap-6">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 p-6 rounded-xl bg-[var(--terminal-bg)]/50 border border-[var(--terminal-border)]">
                      <div className="space-y-2">
                        <label className="text-[10px] font-mono font-bold text-[var(--terminal-text-dim)] uppercase tracking-widest">Query Injection</label>
                        <div className="relative group">
                          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[var(--terminal-text-muted)] group-hover:text-[var(--phosphor-green)] transition-colors" />
                          <input
                            type="text"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && handleSearchPapers()}
                            placeholder="INJECT SEARCH QUERY..."
                            className="w-full pl-10 pr-4 py-2.5 rounded-lg bg-[var(--terminal-surface)] border border-[var(--terminal-border)] font-mono text-xs text-[var(--terminal-text)] placeholder:text-[var(--terminal-text-muted)] focus:outline-none focus:border-[var(--phosphor-green)]/50 transition-all"
                          />
                        </div>
                      </div>
                      <CustomSlider
                        label="Maximum Transmission Units"
                        value={maxResults}
                        onChange={setMaxResults}
                        min={1}
                        max={100}
                        step={1}
                      />
                    </div>

                    <div className="flex items-center gap-6 px-6 py-4 rounded-xl bg-[var(--terminal-bg)]/30 border border-[var(--terminal-border)] border-dashed">
                      <ToggleSwitch
                        checked={extractEntities}
                        onCheckedChange={setExtractEntities}
                        label="EXTRACT_ENTITIES"
                      />
                      <ToggleSwitch
                        checked={downloadPdfs}
                        onCheckedChange={setDownloadPdfs}
                        label="CACHE_SOURCE_PDF"
                      />
                    </div>

                    <button
                      onClick={handleSearchPapers}
                      disabled={isSearching || !searchQuery.trim()}
                      className="w-full flex items-center justify-center gap-2 px-5 py-3 rounded-lg font-mono text-[11px] font-bold uppercase transition-all bg-[var(--cyan)]/10 border border-[var(--cyan)]/30 text-[var(--cyan)] hover:bg-[var(--cyan)]/20 active:scale-[0.99] disabled:opacity-40"
                    >
                      {isSearching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                      EXECUTE_SEARCH_QUERY
                    </button>

                    {/* Progress */}
                    {(isSearching || isIngesting || message) && (
                      <ProgressBar value={progress} label="Transmitting_Data" />
                    )}

                    {/* Search Results Display */}
                    {searchResults && (
                      <div className="space-y-4 mt-4 max-h-[400px] overflow-y-auto terminal-scrollbar pr-2">
                        {searchResults.map((paper) => (
                          <div 
                            key={paper.id}
                            className="p-4 rounded-xl bg-[var(--terminal-bg)] border border-[var(--terminal-border)] hover:border-[var(--phosphor-green)]/30 transition-all group cursor-pointer"
                            onClick={() => setSelectedPaperIds(prev => 
                              prev.includes(paper.id) ? prev.filter(id => id !== paper.id) : [...prev, paper.id]
                            )}
                          >
                            <div className="flex items-start gap-4">
                              <div className={cn(
                                "mt-1 p-1.5 rounded bg-[var(--terminal-surface)] border border-[var(--terminal-border)] transition-colors",
                                selectedPaperIds.includes(paper.id) ? "text-[var(--phosphor-green)] border-[var(--phosphor-green)]/50" : "text-[var(--terminal-text-muted)]"
                              )}>
                                {selectedPaperIds.includes(paper.id) ? <CheckSquare className="h-4 w-4" /> : <Square className="h-4 w-4" />}
                              </div>
                              <div className="flex-1 space-y-2">
                                <h4 className="text-xs font-mono font-bold text-[var(--terminal-text)] group-hover:text-[var(--phosphor-green)] transition-colors">
                                  {paper.title}
                                </h4>
                                <p className="text-[10px] font-mono text-[var(--terminal-text-muted)] line-clamp-2 leading-relaxed">
                                  {paper.abstract}
                                </p>
                                <div className="flex items-center gap-2">
                                  <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-[var(--terminal-surface)] border border-[var(--terminal-border)] text-[var(--cyan)]">
                                    {paper.id}
                                  </span>
                                  {paper.categories.slice(0, 2).map(cat => (
                                    <span key={cat} className="text-[9px] font-mono px-2 py-0.5 rounded bg-[var(--terminal-surface)] border border-[var(--terminal-border)] text-[var(--amber-gold)]">
                                      {cat}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Stats Tab */}
              {activeTab === 'stats' && (
                <div className="space-y-10 max-w-5xl">
                  {stats && (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                      {[
                        { label: 'System_Papers', value: stats.statistics.total_papers_tracked, color: 'text-[var(--terminal-text)]', icon: FileText },
                        { label: 'Active_Transmissions', value: stats.statistics.active_papers, color: 'text-[var(--phosphor-green)]', icon: Activity },
                        { label: 'Domain_Clusters', value: stats.statistics.categories_tracked, color: 'text-[var(--cyan)]', icon: Layers },
                        { label: 'Temporal_Sync', value: stats.statistics.recent_changes_week?.new || 0, color: 'text-[var(--amber-gold)]', icon: Zap },
                      ].map((stat) => (
                        <div key={stat.label} className="p-5 rounded-xl bg-[var(--terminal-bg)]/50 border border-[var(--terminal-border)] relative overflow-hidden group hover:border-[var(--phosphor-green)]/30 transition-all">
                          <stat.icon className="absolute -right-2 -top-2 h-16 w-16 text-[var(--terminal-border)] opacity-20 group-hover:opacity-30 transition-all" />
                          <div className={cn("text-2xl font-mono font-bold mb-1", stat.color)}>{stat.value}</div>
                          <div className="text-[9px] font-mono text-[var(--terminal-text-muted)] uppercase tracking-widest">{stat.label}</div>
                        </div>
                      ))}
                    </div>
                  )}

                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <div className="p-6 rounded-xl bg-[var(--terminal-bg)]/50 border border-[var(--terminal-border)]">
                      <div className="flex items-center gap-2 mb-6">
                        <Cpu className="h-4 w-4 text-[var(--phosphor-green)]" />
                        <h3 className="text-xs font-mono font-bold text-[var(--terminal-text)] uppercase tracking-widest">Category_Distribution_Map</h3>
                      </div>
                      <div className="space-y-3">
                        {stats?.statistics.top_categories?.map(([category, count]) => (
                          <div key={category} className="space-y-1.5">
                            <div className="flex justify-between text-[10px] font-mono uppercase">
                              <span className="text-[var(--terminal-text-dim)]">{category}</span>
                              <span className="text-[var(--phosphor-green)] font-bold">{count}</span>
                            </div>
                            <div className="h-1 w-full bg-[var(--terminal-border)] rounded-full overflow-hidden">
                              <div 
                                className="h-full bg-[var(--phosphor-green)]/40 rounded-full"
                                style={{ width: `${(count / stats.statistics.total_papers_tracked) * 100}%` }}
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="p-6 rounded-xl bg-[var(--terminal-bg)]/50 border border-[var(--terminal-border)] flex flex-col items-center justify-center space-y-4">
                      <Globe className="h-12 w-12 text-[var(--terminal-border)] animate-pulse" />
                      <div className="text-center">
                        <p className="text-[10px] font-mono font-bold text-[var(--terminal-text-dim)] uppercase tracking-[0.3em] mb-1">Grid_Status_Active</p>
                        <p className="text-[9px] font-mono text-[var(--terminal-text-muted)] uppercase tracking-widest">Synchronization latency: optimal</p>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
