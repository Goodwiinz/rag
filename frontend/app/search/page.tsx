'use client';

import React, { useState, useCallback, useMemo, useEffect } from 'react';
import { searchService } from '@/services/searchService';
import { SearchInterface } from '@/components/search/SearchInterface';
import { ResultsPanel } from '@/components/search/ResultsPanel';
import { SearchResult, SearchRequest, QueryHistory, QuerySuggestions } from '@/types/search';
import {
  MagnifyingGlassIcon,
  DocumentTextIcon,
  ClockIcon,
  SparklesIcon,
  ExclamationTriangleIcon,
  LightBulbIcon,
} from '@heroicons/react/24/outline';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { getAnalytics } from '@/lib/analytics';

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

  // Track page view
  useEffect(() => {
    try {
      const analytics = getAnalytics();
      analytics.trackPageView('/search', 'Semantic Search');
    } catch (error) {
      // Analytics not initialized, silently ignore
    }
  }, []);

  const handleSearch = useCallback(async (query: string, filters?: SearchFilters) => {
    if (!query.trim()) return;

    setIsLoading(true);
    setError(null);

    // Track search query
    try {
      const analytics = getAnalytics();
      analytics.trackSearch(query, 0, 'semantic');
      analytics.trackFeatureUsage('search', 'query_submitted', {
        queryLength: query.length,
        hasFilters: !!filters && Object.keys(filters).length > 0
      });
    } catch (error) {
      // Analytics not initialized, silently ignore
    }

    try {
      const hasFilters = filters && Object.keys(filters).length > 0;
      const searchRequest: SearchRequest = {
        query: query.trim(),
        filters: hasFilters ? {
          ...filters,
          // Convert file types to document file types if needed
          file_types: filters.file_types as any,
        } : undefined,
        limit: filters?.max_results || 10,
      };

      const response = await searchService.search(searchRequest);

      if (response.success && response.data) {
        setSearchResult(response.data);

        // Track successful search
        try {
          const analytics = getAnalytics();
          analytics.trackSearch(query, response.data.results.length, 'semantic');
          analytics.trackFeatureUsage('search', 'success', {
            resultCount: response.data.results.length,
            responseTime: response.data.metadata?.response_time || 0
          });
        } catch (error) {
          // Analytics not initialized, silently ignore
        }

        // Add to search history
        try {
          await searchService.addToHistory(query.trim(), response.data.id);
        } catch (historyError) {
          console.warn('Failed to add to search history:', historyError);
        }
      } else {
        setError(response.message || 'Search failed');
        setSearchResult(null);

        // Track search error
        try {
          const analytics = getAnalytics();
          analytics.trackError(new Error(response.message || 'Search failed'), 'search');
          analytics.trackFeatureUsage('search', 'failed', {
            error: response.message
          });
        } catch (error) {
          // Analytics not initialized, silently ignore
        }
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An unexpected error occurred';
      setError(errorMessage);
      setSearchResult(null);

      // Track unexpected error
      try {
        const analytics = getAnalytics();
        analytics.trackError(err instanceof Error ? err : new Error(errorMessage), 'search_unexpected');
      } catch (error) {
        // Analytics not initialized, silently ignore
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  const handleGetSuggestions = useCallback(async (query: string): Promise<QuerySuggestions> => {
    try {
      const response = await searchService.getQuerySuggestions(query, 5);
      if (response.success && response.data) {
        return response.data;
      }
    } catch (error) {
      console.warn('Failed to get suggestions:', error);
    }

    // Return empty suggestions if API fails
    return {
      suggestions: [],
      related_queries: [],
      auto_complete: [],
    };
  }, []);

  const handleGetHistory = useCallback(async (): Promise<QueryHistory[]> => {
    try {
      const response = await searchService.getSearchHistory(50);
      if (response.success && response.data) {
        return response.data;
      }
    } catch (error) {
      console.warn('Failed to get search history:', error);
    }

    return [];
  }, []);

  const handleSaveSearch = useCallback(async (query: string, name: string): Promise<void> => {
    // This would typically call a saved searches API endpoint
    // For now, we'll just store it in localStorage as a placeholder
    try {
      const savedSearches = JSON.parse(localStorage.getItem('savedSearches') || '[]');
      const newSavedSearch = {
        id: Date.now().toString(),
        name,
        query,
        created_at: new Date().toISOString(),
      };
      savedSearches.push(newSavedSearch);
      localStorage.setItem('savedSearches', JSON.stringify(savedSearches));
    } catch (error) {
      console.error('Failed to save search:', error);
      throw error;
    }
  }, []);

  const handleSourceClick = useCallback((source: any) => {
    // Handle source reference click - could open document preview
    console.log('Source clicked:', source);
    // You might want to open a preview modal or navigate to document view
  }, []);

  const handleDocumentPreview = useCallback((documentId: string) => {
    // Handle document preview - could open preview modal
    console.log('Document preview requested:', documentId);
    // You might want to open a preview modal or navigate to document view
  }, []);

  const handleShare = useCallback((result: SearchResult) => {
    // Handle sharing functionality
    if (navigator.share) {
      navigator.share({
        title: 'Search Result',
        text: `Check out this search result for: ${result.query}`,
        url: window.location.href,
      });
    } else {
      // Fallback: copy to clipboard
      navigator.clipboard.writeText(window.location.href);
    }
  }, []);

  const handleExport = useCallback((result: SearchResult) => {
    // Handle export functionality
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

  const handleFeedback = useCallback((result: SearchResult, rating: number, comment?: string) => {
    // Handle feedback submission
    console.log('Feedback submitted:', { resultId: result.id, rating, comment });
    // This would typically call a feedback API endpoint
  }, []);

  return (
    <div className="min-h-screen bg-background">
      {/* Subtle Background Pattern */}
      <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none">
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:24px_24px]"></div>
        <div className="absolute left-0 right-0 top-0 -z-10 m-auto h-[310px] w-[310px] rounded-full bg-primary/20 opacity-20 blur-[100px]"></div>
      </div>

      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header & Search Section */}
        <div className="sticky top-4 z-30 mb-8">
          <div className="absolute -inset-4 bg-background/80 backdrop-blur-xl border-b border-border/40 -z-10 rounded-b-3xl shadow-sm opacity-0 data-[stuck=true]:opacity-100 transition-opacity duration-200" />

          {!searchResult && !isLoading && (
            <div className="text-center mb-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
              <h1 className="text-4xl font-bold tracking-tight text-foreground mb-3">
                What are you looking for?
              </h1>
              <p className="text-lg text-muted-foreground max-w-2xl mx-auto font-light">
                Search across all your documents with intelligent semantic understanding.
              </p>
            </div>
          )}

          <SearchInterface
            onSearch={handleSearch}
            onGetSuggestions={handleGetSuggestions}
            onGetHistory={handleGetHistory}
            onSaveSearch={handleSaveSearch}
            loading={isLoading}
            placeholder="Ask a question or search for keywords..."
            autoFocus={true}
            className="w-full max-w-3xl mx-auto"
          />
        </div>

        {/* Main Content Area */}
        <div className="relative min-h-[400px]">
          {/* Loading State */}
          {isLoading && (
            <div className="max-w-3xl mx-auto space-y-8 animate-in fade-in duration-500">
              <div className="space-y-4">
                <div className="h-8 w-3/4 bg-muted/50 rounded-lg animate-pulse" />
                <div className="space-y-2">
                  <div className="h-4 w-full bg-muted/30 rounded animate-pulse" />
                  <div className="h-4 w-full bg-muted/30 rounded animate-pulse" />
                  <div className="h-4 w-5/6 bg-muted/30 rounded animate-pulse" />
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-32 bg-muted/30 rounded-xl border border-border/50 animate-pulse" />
                ))}
              </div>
            </div>
          )}

          {/* Results */}
          {searchResult && !isLoading && (
            <div className="animate-in fade-in slide-in-from-bottom-8 duration-500">
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
            </div>
          )}

          {/* Empty State / Initial View */}
          {!searchResult && !isLoading && !error && (
            <div className="mt-12 grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl mx-auto animate-in fade-in slide-in-from-bottom-8 duration-700 delay-100">
              <Card className="bg-card/50 border-border/50 hover:border-primary/20 transition-colors">
                <CardContent className="p-6">
                  <div className="flex items-center space-x-3 mb-3">
                    <div className="p-2 bg-blue-500/10 rounded-lg">
                      <SparklesIcon className="h-5 w-5 text-blue-600" />
                    </div>
                    <h3 className="font-semibold text-foreground">AI Analysis</h3>
                  </div>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    Get instant answers synthesized from multiple documents, complete with citations and confidence scores.
                  </p>
                </CardContent>
              </Card>

              <Card className="bg-card/50 border-border/50 hover:border-primary/20 transition-colors">
                <CardContent className="p-6">
                  <div className="flex items-center space-x-3 mb-3">
                    <div className="p-2 bg-purple-500/10 rounded-lg">
                      <MagnifyingGlassIcon className="h-5 w-5 text-purple-600" />
                    </div>
                    <h3 className="font-semibold text-foreground">Semantic Search</h3>
                  </div>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    Find what you mean, not just what you say. Our system understands context and intent behind your queries.
                  </p>
                </CardContent>
              </Card>

              <div className="md:col-span-2">
                <div className="text-center space-y-4 mt-8">
                  <p className="text-sm font-medium text-muted-foreground uppercase tracking-wider">Try asking</p>
                  <div className="flex flex-wrap justify-center gap-2">
                    {['Market trends analysis', 'Q4 Project updates', 'Technical architecture specs', 'Client meeting notes'].map((suggestion) => (
                      <button
                        key={suggestion}
                        onClick={() => handleSearch(suggestion)}
                        className="px-4 py-2 bg-muted/30 hover:bg-muted text-muted-foreground hover:text-foreground border border-border/50 rounded-full text-sm transition-all duration-200"
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Error State */}
          {error && (
            <Alert variant="destructive" className="max-w-2xl mx-auto mt-8 animate-in fade-in zoom-in-95">
              <ExclamationTriangleIcon className="h-5 w-5" />
              <AlertTitle>Search Error</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
        </div>
      </div>
    </div>
  );
}