'use client';

import { ResultsPanel } from '@/components/search/ResultsPanel';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { getAnalytics } from '@/lib/analytics';
import { searchService } from '@/services/searchService';
import { QueryHistory, QuerySuggestions, SearchRequest, SearchResult } from '@/types/search';
import { useCallback, useEffect, useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search,
  Sparkles,
  Database,
  Zap,
  Terminal,
  ArrowRight,
  Filter,
  Clock,
  FileText,
  Brain,
  Command,
  AlertTriangle,
  Loader2
} from 'lucide-react';

// Terminal Observatory Theme Constants
const PHOSPHOR_GREEN = '#00ff9f';
const AMBER = '#ffb700';

// Local interface to match SearchInterface's expected filter type
interface SearchFilters {
  modalities?: ('text' | 'image' | 'audio' | 'video')[];
  document_ids?: string[];
  date_range?: {
    start: string;
    end: string;
  };
  file_types?: ('pdf' | 'txt' | 'jpg' | 'png' | 'mp3' | 'mp4')[];
  min_confidence?: number;
  max_results?: number;
}

export default function SearchPage() {
  const [searchResult, setSearchResult] = useState<SearchResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [terminalText, setTerminalText] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [mounted, setMounted] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Terminal typing effect for header
  useEffect(() => {
    if (!mounted) return;
    const fullText = 'SEMANTIC SEARCH TERMINAL';
    let index = 0;
    const interval = setInterval(() => {
      if (index <= fullText.length) {
        setTerminalText(fullText.slice(0, index));
        index++;
      } else {
        clearInterval(interval);
      }
    }, 40);
    return () => clearInterval(interval);
  }, [mounted]);

  // Track page view
  useEffect(() => {
    try {
      const analytics = getAnalytics();
      analytics.trackPageView('/search', 'Semantic Search');
    } catch (error) {
      // Analytics not initialized, silently ignore
    }
  }, []);

  const handleSearch = useCallback(async (searchQuery?: string) => {
    const q = searchQuery || query;
    if (!q.trim()) return;

    setIsLoading(true);
    setError(null);

    try {
      const analytics = getAnalytics();
      analytics.trackSearch(q, 0, 'semantic');
    } catch (error) {}

    try {
      const searchRequest: SearchRequest = {
        query: q.trim(),
        limit: 10,
      };

      const response = await searchService.search(searchRequest);

      if (response.success && response.data) {
        setSearchResult(response.data);
        try {
          await searchService.addToHistory(q.trim(), response.data.id);
        } catch (historyError) {
          console.warn('Failed to add to search history:', historyError);
        }
      } else {
        setError(response.message || 'Search failed');
        setSearchResult(null);
      }
    } catch (err: any) {
      console.error('Search error:', err);
      let errorMessage = 'An unexpected error occurred';
      if (err?.response?.data?.error) {
        errorMessage = err.response.data.error.message || err.response.data.error;
      } else if (err?.response?.data?.detail) {
        errorMessage = err.response.data.detail;
      } else if (err?.message) {
        errorMessage = err.message;
      }
      setError(errorMessage);
      setSearchResult(null);
    } finally {
      setIsLoading(false);
    }
  }, [query]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSearch();
    }
  };

  const handleSourceClick = useCallback((source: any) => {
    console.log('Source clicked:', source);
  }, []);

  const handleDocumentPreview = useCallback((documentId: string) => {
    console.log('Document preview requested:', documentId);
  }, []);

  const handleShare = useCallback((result: SearchResult) => {
    if (navigator.share) {
      navigator.share({
        title: 'Search Result',
        text: `Check out this search result for: ${result.query}`,
        url: window.location.href,
      });
    } else {
      navigator.clipboard.writeText(window.location.href);
    }
  }, []);

  const handleExport = useCallback((result: SearchResult) => {
    const exportData = {
      query: result.query,
      answer: result.answer,
      sources: result.answer.sources,
      metrics: result.metrics,
      timestamp: new Date().toISOString(),
    };
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `search-result-${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, []);

  const handleFeedback = useCallback((result: SearchResult, rating: number, comment?: string) => {
    console.log('Feedback submitted:', { resultId: result.id, rating, comment });
  }, []);

  const suggestedQueries = [
    { icon: Database, label: 'Find all papers about transformers', cmd: 'transformers architecture' },
    { icon: Brain, label: 'Explain RAG systems', cmd: 'retrieval augmented generation' },
    { icon: FileText, label: 'Recent document uploads', cmd: 'recently uploaded documents' },
    { icon: Zap, label: 'Performance optimization', cmd: 'system performance metrics' },
  ];

  const features = [
    {
      icon: Sparkles,
      title: 'AI SYNTHESIS',
      description: 'Multi-document answer generation with source citations',
      color: PHOSPHOR_GREEN,
    },
    {
      icon: Search,
      title: 'SEMANTIC MATCH',
      description: 'Context-aware search beyond keyword matching',
      color: AMBER,
    },
    {
      icon: Database,
      title: 'KNOWLEDGE GRAPH',
      description: 'Entity relationships and document connections',
      color: '#00d4ff',
    },
  ];

  if (!mounted) return null;

  return (
    <div className="min-h-screen bg-[#0a0a0f] relative overflow-hidden">
      {/* CRT Scanlines Overlay */}
      <div
        className="fixed inset-0 pointer-events-none z-50 opacity-[0.03]"
        style={{
          background: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0, 255, 159, 0.03) 2px, rgba(0, 255, 159, 0.03) 4px)',
        }}
      />

      {/* Grid Background */}
      <div className="fixed inset-0 pointer-events-none">
        <div
          className="absolute inset-0 opacity-[0.04]"
          style={{
            backgroundImage: `
              linear-gradient(${PHOSPHOR_GREEN}20 1px, transparent 1px),
              linear-gradient(90deg, ${PHOSPHOR_GREEN}20 1px, transparent 1px)
            `,
            backgroundSize: '50px 50px',
          }}
        />
        {/* Ambient Glow */}
        <div
          className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[800px] h-[400px] rounded-full blur-[150px] opacity-20"
          style={{ background: `radial-gradient(ellipse, ${PHOSPHOR_GREEN}40, transparent 70%)` }}
        />
      </div>

      <div className="relative z-10 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Terminal Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="text-center mb-10"
        >
          {/* Terminal Title */}
          <div className="inline-flex items-center gap-3 mb-4">
            <div
              className="p-2 rounded border"
              style={{
                borderColor: `${PHOSPHOR_GREEN}40`,
                background: `${PHOSPHOR_GREEN}10`,
              }}
            >
              <Terminal className="w-5 h-5" style={{ color: PHOSPHOR_GREEN }} />
            </div>
            <h1
              className="text-2xl md:text-3xl font-mono font-bold tracking-wide"
              style={{ color: PHOSPHOR_GREEN }}
            >
              {terminalText}
              <span className="animate-pulse">_</span>
            </h1>
          </div>

          <p className="text-white/50 font-mono text-sm max-w-xl mx-auto">
            Query your knowledge base with natural language. AI-powered semantic understanding.
          </p>
        </motion.div>

        {/* Search Terminal Window */}
        <motion.div
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.4, delay: 0.2 }}
          className="mb-10"
        >
          {/* Terminal Window Chrome */}
          <div
            className="rounded-lg border overflow-hidden"
            style={{
              borderColor: `${PHOSPHOR_GREEN}30`,
              background: 'rgba(13, 13, 18, 0.8)',
              boxShadow: `0 0 40px ${PHOSPHOR_GREEN}10, inset 0 1px 0 rgba(255,255,255,0.05)`,
            }}
          >
            {/* Title Bar */}
            <div
              className="flex items-center justify-between px-4 py-2 border-b"
              style={{ borderColor: `${PHOSPHOR_GREEN}20`, background: 'rgba(0,0,0,0.3)' }}
            >
              <div className="flex items-center gap-2">
                <div className="flex gap-1.5">
                  <div className="w-3 h-3 rounded-full bg-red-500/80" />
                  <div className="w-3 h-3 rounded-full bg-yellow-500/80" />
                  <div className="w-3 h-3 rounded-full bg-green-500/80" />
                </div>
                <span className="text-white/40 text-xs font-mono ml-3">search_terminal.exe</span>
              </div>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setShowFilters(!showFilters)}
                  className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs font-mono transition-all ${
                    showFilters
                      ? 'text-[#00ff9f] bg-[#00ff9f]/10 border border-[#00ff9f]/30'
                      : 'text-white/40 hover:text-white/60'
                  }`}
                >
                  <Filter className="w-3 h-3" />
                  FILTERS
                </button>
                <span className="text-white/30 text-xs font-mono flex items-center gap-1">
                  <Command className="w-3 h-3" />K
                </span>
              </div>
            </div>

            {/* Search Input Area */}
            <div className="p-4">
              <div className="flex items-center gap-3">
                <span style={{ color: PHOSPHOR_GREEN }} className="font-mono text-lg">{'>'}</span>
                <input
                  ref={inputRef}
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Enter your query..."
                  className="flex-1 bg-transparent text-white/90 font-mono text-base placeholder:text-white/30 focus:outline-none"
                  autoFocus
                />
                <button
                  onClick={() => handleSearch()}
                  disabled={isLoading || !query.trim()}
                  className="flex items-center gap-2 px-4 py-2 rounded font-mono text-sm transition-all disabled:opacity-40"
                  style={{
                    background: query.trim() ? `${PHOSPHOR_GREEN}20` : 'transparent',
                    borderWidth: '1px',
                    borderStyle: 'solid',
                    borderColor: query.trim() ? `${PHOSPHOR_GREEN}50` : 'rgba(255,255,255,0.1)',
                    color: query.trim() ? PHOSPHOR_GREEN : 'rgba(255,255,255,0.3)',
                  }}
                >
                  {isLoading ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <>
                      <span>EXECUTE</span>
                      <ArrowRight className="w-4 h-4" />
                    </>
                  )}
                </button>
              </div>

              {/* Filters Panel */}
              <AnimatePresence>
                {showFilters && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    className="overflow-hidden"
                  >
                    <div
                      className="mt-4 pt-4 border-t flex flex-wrap gap-2"
                      style={{ borderColor: `${PHOSPHOR_GREEN}15` }}
                    >
                      {['PDF', 'Text', 'Image', 'Audio', 'Video'].map((type) => (
                        <button
                          key={type}
                          className="px-3 py-1.5 rounded border text-xs font-mono text-white/50 hover:text-white/80 hover:border-white/30 transition-all"
                          style={{ borderColor: 'rgba(255,255,255,0.1)' }}
                        >
                          {type}
                        </button>
                      ))}
                      <div className="w-px h-6 bg-white/10 mx-2" />
                      <button
                        className="px-3 py-1.5 rounded border text-xs font-mono text-white/50 hover:text-white/80 hover:border-white/30 transition-all flex items-center gap-1.5"
                        style={{ borderColor: 'rgba(255,255,255,0.1)' }}
                      >
                        <Clock className="w-3 h-3" />
                        Last 7 days
                      </button>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Keyboard Hints */}
              <div className="mt-3 flex items-center justify-between text-xs font-mono text-white/30">
                <span>Press ENTER to search</span>
                <span className="flex items-center gap-4">
                  <span className="flex items-center gap-1">
                    <span className="px-1.5 py-0.5 rounded bg-white/5 border border-white/10">ESC</span>
                    clear
                  </span>
                </span>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Main Content Area */}
        <div className="relative min-h-[300px]">
          {/* Loading State */}
          <AnimatePresence>
            {isLoading && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="space-y-6"
              >
                <div className="flex items-center gap-3 font-mono text-sm" style={{ color: PHOSPHOR_GREEN }}>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Processing query through neural network...</span>
                </div>
                <div className="space-y-3">
                  {[1, 2, 3].map((i) => (
                    <div
                      key={i}
                      className="h-16 rounded border animate-pulse"
                      style={{
                        borderColor: `${PHOSPHOR_GREEN}15`,
                        background: `linear-gradient(90deg, ${PHOSPHOR_GREEN}05 0%, ${PHOSPHOR_GREEN}10 50%, ${PHOSPHOR_GREEN}05 100%)`,
                      }}
                    />
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Results */}
          {searchResult && !isLoading && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4 }}
            >
              <ResultsPanel
                result={searchResult}
                loading={isLoading}
                error={error}
                onSourceClick={handleSourceClick}
                onDocumentPreview={handleDocumentPreview}
                onShare={handleShare}
                onExport={handleExport}
                onFeedback={handleFeedback}
                className="w-full"
              />
            </motion.div>
          )}

          {/* Initial State - Features & Suggestions */}
          {!searchResult && !isLoading && !error && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.5, delay: 0.3 }}
            >
              {/* Feature Cards */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-10">
                {features.map((feature, index) => (
                  <motion.div
                    key={feature.title}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.4, delay: 0.1 * index }}
                    className="group p-5 rounded-lg border transition-all duration-300 hover:scale-[1.02]"
                    style={{
                      borderColor: `${feature.color}20`,
                      background: `linear-gradient(135deg, ${feature.color}05 0%, transparent 50%)`,
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = `${feature.color}40`;
                      e.currentTarget.style.boxShadow = `0 0 30px ${feature.color}10`;
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = `${feature.color}20`;
                      e.currentTarget.style.boxShadow = 'none';
                    }}
                  >
                    <div
                      className="w-10 h-10 rounded-lg flex items-center justify-center mb-3"
                      style={{ background: `${feature.color}15` }}
                    >
                      <feature.icon className="w-5 h-5" style={{ color: feature.color }} />
                    </div>
                    <h3 className="font-mono font-semibold text-white/90 text-sm mb-2">
                      {feature.title}
                    </h3>
                    <p className="text-white/50 text-xs font-mono leading-relaxed">
                      {feature.description}
                    </p>
                  </motion.div>
                ))}
              </div>

              {/* Suggested Queries */}
              <div className="text-center">
                <div
                  className="inline-block px-3 py-1 rounded-full text-xs font-mono mb-6"
                  style={{
                    color: `${PHOSPHOR_GREEN}80`,
                    background: `${PHOSPHOR_GREEN}10`,
                    border: `1px solid ${PHOSPHOR_GREEN}20`,
                  }}
                >
                  SUGGESTED QUERIES
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-2xl mx-auto">
                  {suggestedQueries.map((suggestion, index) => (
                    <motion.button
                      key={suggestion.cmd}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.3, delay: 0.4 + index * 0.1 }}
                      onClick={() => {
                        setQuery(suggestion.cmd);
                        handleSearch(suggestion.cmd);
                      }}
                      className="group flex items-center gap-3 p-3 rounded-lg border text-left transition-all duration-200"
                      style={{
                        borderColor: 'rgba(255,255,255,0.08)',
                        background: 'rgba(255,255,255,0.02)',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.borderColor = `${PHOSPHOR_GREEN}30`;
                        e.currentTarget.style.background = `${PHOSPHOR_GREEN}05`;
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)';
                        e.currentTarget.style.background = 'rgba(255,255,255,0.02)';
                      }}
                    >
                      <div
                        className="w-8 h-8 rounded flex items-center justify-center transition-colors"
                        style={{ background: 'rgba(255,255,255,0.05)' }}
                      >
                        <suggestion.icon className="w-4 h-4 text-white/40 group-hover:text-[#00ff9f] transition-colors" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-white/70 text-sm font-mono truncate group-hover:text-white/90 transition-colors">
                          {suggestion.label}
                        </p>
                      </div>
                      <ArrowRight className="w-4 h-4 text-white/20 group-hover:text-[#00ff9f] group-hover:translate-x-1 transition-all" />
                    </motion.button>
                  ))}
                </div>
              </div>
            </motion.div>
          )}

          {/* Error State */}
          {error && (
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="max-w-2xl mx-auto"
            >
              <div
                className="p-4 rounded-lg border flex items-start gap-3"
                style={{
                  borderColor: 'rgba(239, 68, 68, 0.3)',
                  background: 'rgba(239, 68, 68, 0.05)',
                }}
              >
                <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
                <div>
                  <h3 className="font-mono text-red-400 font-semibold text-sm mb-1">SEARCH ERROR</h3>
                  <p className="text-white/60 text-sm font-mono">{error}</p>
                </div>
              </div>
            </motion.div>
          )}
        </div>
      </div>
    </div>
  );
}
