'use client';

import { ResultsPanel } from '@/components/search/ResultsPanel';
import { getAnalytics } from '@/lib/analytics';
import { cn } from '@/lib/utils';
import { searchService } from '@/services/searchService';
import { COLORS, THEME } from '@/theme/constants';
import { SearchRequest, SearchResult } from '@/types/search';
import { AnimatePresence, motion } from 'framer-motion';
import {
  ArrowRight,
  Brain,
  Clock,
  Database,
  FileText,
  Filter,
  RefreshCw,
  Search,
  Sparkles,
  Terminal,
  X,
  Zap,
} from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

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

const MODALITY_FILTERS = ['pdf', 'txt', 'image', 'audio', 'video'] as const;

export default function SearchPage() {
  const [searchResult, setSearchResult] = useState<SearchResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [terminalText, setTerminalText] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [activeFilters, setActiveFilters] = useState<string[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  const handleClear = () => {
    setQuery('');
    inputRef.current?.focus();
  };

  // Global '/' keyboard shortcut to focus search
  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      if (
        document.activeElement?.tagName === 'INPUT' ||
        document.activeElement?.tagName === 'TEXTAREA' ||
        (document.activeElement as HTMLElement)?.isContentEditable
      ) {
        return;
      }

      if (e.key === '/') {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };

    window.addEventListener('keydown', handleGlobalKeyDown);
    return () => window.removeEventListener('keydown', handleGlobalKeyDown);
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

  const toggleFilter = (filter: string) => {
    setActiveFilters((prev) =>
      prev.includes(filter)
        ? prev.filter((f) => f !== filter)
        : [...prev, filter]
    );
  };

  const toggleRecent = () => {
    toggleFilter('RECENT_7D');
  };

  const handleSearch = useCallback(
    async (searchQuery?: string) => {
      const q = searchQuery || query;
      if (!q.trim()) return;

      setIsLoading(true);
      setError(null);

      // Construct filters object
      const filters: SearchFilters = {};

      // Process file types/modalities
      const fileTypes = activeFilters.filter((f) =>
        MODALITY_FILTERS.includes(f as any)
      ) as any[];
      if (fileTypes.length > 0) {
        // Map 'image', 'audio', 'video' to modalities if needed by backend,
        // but here we align with the local interface which has file_types AND modalities
        // Assuming backend handles these. For now passing as file_types mostly.
        const mappedFileTypes: any[] = [];
        const mappedModalities: any[] = [];

        fileTypes.forEach((ft) => {
          if (['pdf', 'txt'].includes(ft)) mappedFileTypes.push(ft);
          if (['image', 'audio', 'video'].includes(ft))
            mappedModalities.push(ft);
          // Note: 'image', 'audio', 'video' are technically modalities but often treated as file categories in UI
          if (['image', 'audio', 'video'].includes(ft)) {
            // Also add to modalities for completeness if the type definition supports it
            mappedModalities.push(ft);
          }
        });

        if (mappedFileTypes.length > 0) filters.file_types = mappedFileTypes;
        if (mappedModalities.length > 0) filters.modalities = mappedModalities;
      }

      // Process Date Range
      if (activeFilters.includes('RECENT_7D')) {
        const endDate = new Date();
        const startDate = new Date();
        startDate.setDate(startDate.getDate() - 7);
        filters.date_range = {
          start: startDate.toISOString(),
          end: endDate.toISOString(),
        };
      }

      try {
        const analytics = getAnalytics();
        analytics.trackSearch(q, 0, 'semantic');
      } catch (error) {}

      try {
        const searchRequest: SearchRequest = {
          query: q.trim(),
          limit: 10,
          filters: filters as any, // Type assertion as backend types might be loose or strict
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
          errorMessage =
            err.response.data.error.message || err.response.data.error;
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
    },
    [query, activeFilters]
  );

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
    const blob = new Blob([JSON.stringify(exportData, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `search-result-${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, []);

  const handleFeedback = useCallback(
    (result: SearchResult, rating: number, comment?: string) => {
      console.log('Feedback submitted:', {
        resultId: result.id,
        rating,
        comment,
      });
    },
    []
  );

  const suggestedQueries = [
    {
      icon: Database,
      label: 'Papers about transformers',
      cmd: 'transformers architecture',
    },
    {
      icon: Brain,
      label: 'Explain RAG systems',
      cmd: 'retrieval augmented generation',
    },
    {
      icon: FileText,
      label: 'Recent uploads',
      cmd: 'recently uploaded documents',
    },
    {
      icon: Zap,
      label: 'Optimization metrics',
      cmd: 'system performance metrics',
    },
  ];

  const features = [
    {
      icon: Sparkles,
      title: 'AI SYNTHESIS',
      description: 'Multi-document answer generation with source citations',
      color: THEME.colors.primary,
    },
    {
      icon: Search,
      title: 'SEMANTIC MATCH',
      description: 'Context-aware search beyond keyword matching',
      color: THEME.colors.accent,
    },
    {
      icon: Database,
      title: 'KNOWLEDGE GRAPH',
      description: 'Entity relationships and document connections',
      color: THEME.colors.secondary,
    },
  ];

  if (!mounted) return null;

  return (
    <div className="min-h-screen bg-[var(--terminal-bg)] relative overflow-hidden flex flex-col">
      <div className="relative z-10 max-w-5xl mx-auto px-6 py-8 flex-1 overflow-y-auto terminal-scrollbar w-full">
        {/* Terminal Header */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)] p-6 shadow-xl mb-10"
        >
          <div className="flex items-center gap-4">
            <div
              className="w-12 h-12 rounded-lg flex items-center justify-center p-0.5"
              style={{
                background: `${THEME.colors.primary}1A`, // 10% opacity
                border: `1px solid ${THEME.colors.primary}33`, // 20% opacity
              }}
            >
              <Terminal
                className="w-6 h-6"
                style={{ color: THEME.colors.primary }}
              />
            </div>
            <div>
              <h1 className="text-xl font-mono font-bold text-[var(--terminal-text)] tracking-wider uppercase">
                {terminalText}_
              </h1>
              <p className="text-[10px] font-mono text-[var(--terminal-text-dim)] mt-0.5 uppercase tracking-[0.2em]">
                Neural Knowledge Base Ingress
              </p>
            </div>
          </div>
        </motion.div>

        {/* Search Console */}
        <motion.div
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.1 }}
          className="mb-10"
        >
          <div className="rounded-2xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)] shadow-2xl overflow-hidden">
            {/* Title Bar */}
            <div className="flex items-center justify-between px-5 py-2 border-b border-[var(--terminal-border)] bg-[var(--terminal-bg)]/30">
              <span className="text-[10px] font-mono text-[var(--terminal-text-dim)] font-bold tracking-widest uppercase">
                Query_Console.v2
              </span>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setShowFilters(!showFilters)}
                  className={cn(
                    'flex items-center gap-1.5 px-2 py-0.5 rounded border transition-all text-[9px] font-bold font-mono',
                    showFilters
                      ? 'border-[var(--phosphor-green)]/50 bg-[var(--phosphor-green)]/10 text-[var(--phosphor-green)]'
                      : 'border-transparent text-[var(--terminal-text-dim)] hover:text-[var(--terminal-text)]'
                  )}
                  aria-expanded={showFilters}
                  aria-controls="search-filter-panel"
                >
                  <Filter className="w-3 h-3" />
                  FILTERS{' '}
                  {activeFilters.length > 0 && `(${activeFilters.length})`}
                </button>
              </div>
            </div>

            {/* Input Area */}
            <div className="p-6">
              <div className="flex items-center gap-4">
                <div
                  className="font-mono text-lg font-bold opacity-50 shrink-0"
                  style={{ color: THEME.colors.primary }}
                >
                  {'>'}
                </div>
                <input
                  ref={inputRef}
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Inquire knowledge registry..."
                  className="flex-1 bg-transparent text-[var(--terminal-text)] font-mono text-base placeholder:text-[var(--terminal-text-muted)]/30 outline-none"
                  autoFocus
                />
                {query && (
                  <button
                    type="button"
                    onClick={handleClear}
                    className="p-1 hover:bg-[var(--terminal-border)] rounded-full transition-colors mr-2 text-[var(--terminal-text-muted)] hover:text-[var(--terminal-text)]"
                    aria-label="Clear search"
                    title="Clear search"
                  >
                    <X className="w-4 h-4" />
                  </button>
                )}
                <button
                  onClick={() => handleSearch()}
                  disabled={isLoading || !query.trim()}
                  className={cn(
                    'flex items-center gap-2 px-5 py-2 rounded-xl font-mono text-[10px] font-bold tracking-widest transition-all',
                    query.trim() && !isLoading
                      ? 'text-[var(--terminal-bg)] hover:shadow-[0_0_20px_var(--phosphor-green-glow)]'
                      : 'bg-[var(--terminal-elevated)] text-[var(--terminal-text-dim)] border border-[var(--terminal-border)] cursor-not-allowed'
                  )}
                  style={
                    query.trim() && !isLoading
                      ? { backgroundColor: THEME.colors.primary }
                      : {}
                  }
                >
                  {isLoading ? (
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <>
                      <span>EXECUTE</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </>
                  )}
                </button>
              </div>

              {/* Filters */}
              <AnimatePresence>
                {showFilters && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="overflow-hidden"
                  >
                    <div
                      className="mt-6 pt-6 border-t border-[var(--terminal-border)] flex flex-wrap gap-2"
                      id="search-filter-panel"
                      role="region"
                      aria-label="Search filters"
                    >
                      {MODALITY_FILTERS.map((type) => {
                        const isActive = activeFilters.includes(type);
                        return (
                          <button
                            key={type}
                            onClick={() => toggleFilter(type)}
                            className={cn(
                              'px-3 py-1 rounded-lg border text-[9px] font-mono font-bold transition-all uppercase',
                              isActive
                                ? 'text-[var(--terminal-bg)]'
                                : 'border-[var(--terminal-border)] text-[var(--terminal-text-dim)] hover:text-[var(--terminal-text)] hover:border-[var(--terminal-text-muted)]'
                            )}
                            style={
                              isActive
                                ? {
                                    backgroundColor: THEME.colors.primary,
                                    borderColor: THEME.colors.primary,
                                    color: COLORS.background,
                                  }
                                : {}
                            }
                            aria-pressed={isActive}
                          >
                            {type}
                          </button>
                        );
                      })}
                      <div className="w-px h-4 bg-[var(--terminal-border)] mx-2 self-center" />
                      <button
                        onClick={toggleRecent}
                        className={cn(
                          'px-3 py-1 rounded-lg border text-[9px] font-mono font-bold transition-all flex items-center gap-1.5 uppercase',
                          activeFilters.includes('RECENT_7D')
                            ? 'text-[var(--terminal-bg)]'
                            : 'border-[var(--terminal-border)] text-[var(--terminal-text-dim)] hover:text-[var(--terminal-text)] hover:border-[var(--terminal-text-muted)]'
                        )}
                        style={
                          activeFilters.includes('RECENT_7D')
                            ? {
                                backgroundColor: THEME.colors.primary,
                                borderColor: THEME.colors.primary,
                                color: COLORS.background,
                              }
                            : {}
                        }
                        aria-pressed={activeFilters.includes('RECENT_7D')}
                      >
                        <Clock className="w-3 h-3" />
                        RECENT_7D
                      </button>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </motion.div>

        {/* Display Area */}
        <div className="relative min-h-[400px]" aria-live="polite" aria-atomic="false">
          {isLoading && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="space-y-6"
            >
              <div
                className="flex items-center gap-3 font-mono text-[10px] font-bold tracking-widest"
                style={{ color: THEME.colors.primary }}
              >
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                <span className="animate-pulse">
                  NEURAL_SYNTHESIS_IN_PROGRESS...
                </span>
              </div>

              {/* Agent "Thinking" UI */}
              <div className="p-4 rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)]/50 backdrop-blur-sm">
                <div className="flex items-center gap-2 mb-2">
                  <Brain className="w-4 h-4 text-[var(--terminal-text-dim)]" />
                  <span className="text-xs font-mono text-[var(--terminal-text-dim)]">
                    Agent is processing query contexts...
                  </span>
                </div>
                <div className="h-1 w-full bg-[var(--terminal-elevated)] rounded-full overflow-hidden">
                  <motion.div
                    className="h-full bg-[var(--phosphor-green)]"
                    initial={{ x: '-100%' }}
                    animate={{ x: '100%' }}
                    transition={{
                      repeat: Infinity,
                      duration: 1.5,
                      ease: 'linear',
                    }}
                  />
                </div>
                <div className="mt-3 space-y-2">
                  <div className="h-3 w-3/4 bg-[var(--terminal-elevated)] rounded animate-pulse" />
                  <div className="h-3 w-1/2 bg-[var(--terminal-elevated)] rounded animate-pulse delay-75" />
                </div>
              </div>
            </motion.div>
          )}

          {searchResult && !isLoading && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
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

          {!searchResult && !isLoading && !error && (
            <div className="space-y-10">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {features.map((feature, index) => (
                  <motion.div
                    key={feature.title}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.05 }}
                    className="p-5 rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)] shadow-lg relative group overflow-hidden"
                  >
                    <div
                      className="absolute top-0 left-0 w-1 h-full opacity-20 transition-opacity"
                      style={{ backgroundColor: feature.color }}
                    />
                    <feature.icon
                      className="w-5 h-5 mb-4"
                      style={{ color: feature.color }}
                    />
                    <h3 className="font-mono text-xs font-bold text-[var(--terminal-text)] mb-2 uppercase tracking-wider">
                      {feature.title}
                    </h3>
                    <p className="text-[10px] font-mono text-[var(--terminal-text-dim)] leading-relaxed">
                      {feature.description}
                    </p>
                  </motion.div>
                ))}
              </div>

              <div className="text-center">
                <span className="text-[9px] font-mono font-bold text-[var(--terminal-text-dim)] uppercase tracking-[0.3em] mb-6 block">
                  Suggested Directives
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-2xl mx-auto">
                  {suggestedQueries.map((suggestion, index) => (
                    <motion.button
                      key={suggestion.cmd}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: 0.3 + index * 0.05 }}
                      onClick={() => {
                        setQuery(suggestion.cmd);
                        handleSearch(suggestion.cmd);
                      }}
                      className="group flex items-center gap-3 p-3 rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)] hover:border-[var(--phosphor-green)]/30 transition-all text-left"
                    >
                      <div className="w-8 h-8 rounded-lg bg-[var(--terminal-bg)] flex items-center justify-center shrink-0">
                        <suggestion.icon className="w-4 h-4 text-[var(--terminal-text-dim)] group-hover:text-[var(--phosphor-green)] transition-colors" />
                      </div>
                      <span className="flex-1 font-mono text-[11px] text-[var(--terminal-text-dim)] group-hover:text-[var(--terminal-text)] truncate transition-colors uppercase tracking-tight">
                        {suggestion.label}
                      </span>
                      <ArrowRight className="w-3.5 h-3.5 text-[var(--terminal-text-muted)] group-hover:text-[var(--phosphor-green)] transition-all group-hover:translate-x-0.5" />
                    </motion.button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
