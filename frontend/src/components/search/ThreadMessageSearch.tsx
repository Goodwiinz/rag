'use client';

/**
 * Thread and Message Search Component
 * 
 * Full-text search UI for searching threads and messages
 * with filtering, highlighting, and real-time results.
 */

import React, { useState, useCallback, useEffect, useRef } from 'react';
import { Search, X, Clock, MessageSquare, Filter, Loader2, ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { threadSearchService } from '@/services/threadSearchService';
import { THEME } from '@/theme/constants';
import type {
  ThreadSearchResult,
  MessageSearchResult,
  CombinedSearchResult,
  ThreadSearchSortOrder,
  MessageSearchSortOrder,
  ThreadStatus,
} from '@/types/thread-search';

// Terminal Observatory theme colors
// Using THEME.colors instead of local constants


interface ThreadMessageSearchProps {
  workspaceId?: string;
  conversationId?: string;
  onSelectThread?: (threadId: string) => void;
  onSelectMessage?: (messageId: string, threadId: string) => void;
  className?: string;
}

type SearchMode = 'combined' | 'threads' | 'messages';

export function ThreadMessageSearch({
  workspaceId,
  conversationId,
  onSelectThread,
  onSelectMessage,
  className,
}: ThreadMessageSearchProps) {
  // State
  const [query, setQuery] = useState('');
  const [searchMode, setSearchMode] = useState<SearchMode>('combined');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Results
  const [combinedResults, setCombinedResults] = useState<CombinedSearchResult[]>([]);
  const [threadResults, setThreadResults] = useState<ThreadSearchResult[]>([]);
  const [messageResults, setMessageResults] = useState<MessageSearchResult[]>([]);
  
  // Pagination
  const [hasMore, setHasMore] = useState(false);
  const [offset, setOffset] = useState(0);
  const [totalResults, setTotalResults] = useState(0);
  const [searchTime, setSearchTime] = useState(0);
  
  // Filters
  const [threadSortOrder, setThreadSortOrder] = useState<ThreadSearchSortOrder>('relevance');
  const [messageSortOrder, setMessageSortOrder] = useState<MessageSearchSortOrder>('relevance');
  const [statusFilter, setStatusFilter] = useState<ThreadStatus[]>([]);
  const [showFilters, setShowFilters] = useState(false);
  
  // Suggestions
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<NodeJS.Timeout | null>(null);
  const limit = 20;

  // Debounced search
  const performSearch = useCallback(async (searchQuery: string, newOffset = 0) => {
    if (!searchQuery.trim() || searchQuery.length < 2) {
      setCombinedResults([]);
      setThreadResults([]);
      setMessageResults([]);
      setTotalResults(0);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      if (searchMode === 'combined') {
        const response = await threadSearchService.combinedSearch({
          query: searchQuery,
          workspace_id: workspaceId,
          conversation_id: conversationId,
          limit,
        });
        setCombinedResults(response.results);
        setTotalResults(response.total_results);
        setHasMore(response.has_more);
        setSearchTime(response.search_time_ms);
      } else if (searchMode === 'threads') {
        const response = await threadSearchService.searchThreads({
          query: searchQuery,
          filters: {
            workspace_id: workspaceId,
            conversation_id: conversationId,
            status: statusFilter.length > 0 ? statusFilter : undefined,
          },
          sort_order: threadSortOrder,
          limit,
          offset: newOffset,
        });
        if (newOffset === 0) {
          setThreadResults(response.results);
        } else {
          setThreadResults(prev => [...prev, ...response.results]);
        }
        setTotalResults(response.total_results);
        setHasMore(response.has_more);
        setSearchTime(response.search_time_ms);
      } else {
        const response = await threadSearchService.searchMessages({
          query: searchQuery,
          filters: {
            workspace_id: workspaceId,
            conversation_id: conversationId,
          },
          sort_order: messageSortOrder,
          limit,
          offset: newOffset,
        });
        if (newOffset === 0) {
          setMessageResults(response.results);
        } else {
          setMessageResults(prev => [...prev, ...response.results]);
        }
        setTotalResults(response.total_results);
        setHasMore(response.has_more);
        setSearchTime(response.search_time_ms);
      }
      setOffset(newOffset);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed');
    } finally {
      setIsLoading(false);
    }
  }, [searchMode, workspaceId, conversationId, threadSortOrder, messageSortOrder, statusFilter]);

  // Debounced input handler
  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setQuery(value);
    
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }
    
    debounceRef.current = setTimeout(() => {
      performSearch(value, 0);
    }, 300);
  }, [performSearch]);

  // Fetch suggestions
  const fetchSuggestions = useCallback(async (q: string) => {
    if (q.length < 2) {
      setSuggestions([]);
      return;
    }
    
    try {
      const response = await threadSearchService.getSearchSuggestions({
        query: q,
        workspace_id: workspaceId,
        limit: 5,
      });
      setSuggestions(response.suggestions);
    } catch {
      // Silently fail suggestions
    }
  }, [workspaceId]);

  // Load more results
  const handleLoadMore = useCallback(() => {
    performSearch(query, offset + limit);
  }, [query, offset, performSearch]);

  // Clear search
  const handleClear = useCallback(() => {
    setQuery('');
    setCombinedResults([]);
    setThreadResults([]);
    setMessageResults([]);
    setTotalResults(0);
    setOffset(0);
    inputRef.current?.focus();
  }, []);

  // Re-search when mode or filters change
  useEffect(() => {
    if (query.trim()) {
      performSearch(query, 0);
    }
  }, [searchMode, threadSortOrder, messageSortOrder, statusFilter]);

  // Render highlighted text
  const renderHighlighted = (text: string | null | undefined) => {
    if (!text) return null;
    
    // Split by highlight tags and render
    const parts = text.split(/(<mark>|<\/mark>)/);
    let inMark = false;
    
    return parts.map((part, i) => {
      if (part === '<mark>') {
        inMark = true;
        return null;
      }
      if (part === '</mark>') {
        inMark = false;
        return null;
      }
      if (inMark) {
        return (
          <span key={i} className="bg-amber-500/30 text-amber-300 px-0.5 rounded">
            {part}
          </span>
        );
      }
      return <span key={i}>{part}</span>;
    });
  };

  // Get role badge color
  const getRoleBadgeColor = (role: string) => {
    switch (role) {
      case 'user': return 'bg-blue-500/20 text-blue-400';
      case 'assistant': return 'bg-green-500/20 text-green-400';
      case 'system': return 'bg-purple-500/20 text-purple-400';
      case 'tool': return 'bg-orange-500/20 text-orange-400';
      default: return 'bg-gray-500/20 text-gray-400';
    }
  };

  // Get status badge color
  const getStatusBadgeColor = (status: string) => {
    switch (status) {
      case 'active': return 'bg-green-500/20 text-green-400';
      case 'resolved': return 'bg-blue-500/20 text-blue-400';
      case 'archived': return 'bg-gray-500/20 text-gray-400';
      default: return 'bg-gray-500/20 text-gray-400';
    }
  };

  return (
    <div className={cn('flex flex-col gap-4', className)}>
      {/* Search Input */}
      <div className="relative">
        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <Search 
              className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4" 
              style={{ color: THEME.colors.primary }}
            />
            <Input
              ref={inputRef}
              type="text"
              value={query}
              onChange={handleInputChange}
              onFocus={() => query.length >= 2 && setShowSuggestions(true)}
              onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
              placeholder="Search threads and messages..."
              className="pl-10 pr-10 bg-black/40 border-gray-700 focus:border-green-500 text-gray-100 placeholder:text-gray-500"
            />
            {query && (
              <button
                onClick={handleClear}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
          
          {/* Mode Selector */}
          <Select value={searchMode} onValueChange={(v) => setSearchMode(v as SearchMode)}>
            <SelectTrigger className="w-32 bg-black/40 border-gray-700">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="combined">All</SelectItem>
              <SelectItem value="threads">Threads</SelectItem>
              <SelectItem value="messages">Messages</SelectItem>
            </SelectContent>
          </Select>
          
          {/* Filter Button */}
          <Popover open={showFilters} onOpenChange={setShowFilters}>
            <PopoverTrigger asChild>
              <Button 
                variant="outline" 
                size="icon"
                className="bg-black/40 border-gray-700 hover:bg-gray-800"
                aria-label="Toggle filters"
              >
                <Filter className="h-4 w-4" />
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-64 bg-gray-900 border-gray-700">
              <div className="space-y-4">
                <h4 className="font-medium text-sm text-gray-300">Filters</h4>
                
                {searchMode === 'threads' && (
                  <>
                    <div>
                      <label className="text-xs text-gray-500 mb-1 block">Sort By</label>
                      <Select value={threadSortOrder} onValueChange={(v) => setThreadSortOrder(v as ThreadSearchSortOrder)}>
                        <SelectTrigger className="bg-black/40 border-gray-700">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="relevance">Relevance</SelectItem>
                          <SelectItem value="date_desc">Newest First</SelectItem>
                          <SelectItem value="date_asc">Oldest First</SelectItem>
                          <SelectItem value="message_count">Most Messages</SelectItem>
                          <SelectItem value="last_activity">Recent Activity</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    
                    <div>
                      <label className="text-xs text-gray-500 mb-1 block">Status</label>
                      <div className="flex flex-wrap gap-1">
                        {(['active', 'resolved', 'archived'] as ThreadStatus[]).map(status => (
                          <Badge
                            key={status}
                            variant="outline"
                            className={cn(
                              'cursor-pointer',
                              statusFilter.includes(status) 
                                ? getStatusBadgeColor(status) 
                                : 'bg-gray-800 text-gray-500'
                            )}
                            onClick={() => {
                              setStatusFilter(prev => 
                                prev.includes(status)
                                  ? prev.filter(s => s !== status)
                                  : [...prev, status]
                              );
                            }}
                          >
                            {status}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  </>
                )}
                
                {searchMode === 'messages' && (
                  <div>
                    <label className="text-xs text-gray-500 mb-1 block">Sort By</label>
                    <Select value={messageSortOrder} onValueChange={(v) => setMessageSortOrder(v as MessageSearchSortOrder)}>
                      <SelectTrigger className="bg-black/40 border-gray-700">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="relevance">Relevance</SelectItem>
                        <SelectItem value="date_desc">Newest First</SelectItem>
                        <SelectItem value="date_asc">Oldest First</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                )}
              </div>
            </PopoverContent>
          </Popover>
        </div>
        
        {/* Suggestions Dropdown */}
        {showSuggestions && suggestions.length > 0 && (
          <div className="absolute top-full left-0 right-0 mt-1 bg-gray-900 border border-gray-700 rounded-md shadow-lg z-10">
            {suggestions.map((suggestion, i) => (
              <button
                key={i}
                className="w-full px-4 py-2 text-left text-sm text-gray-300 hover:bg-gray-800 first:rounded-t-md last:rounded-b-md"
                onClick={() => {
                  setQuery(suggestion);
                  performSearch(suggestion, 0);
                  setShowSuggestions(false);
                }}
              >
                {suggestion}
              </button>
            ))}
          </div>
        )}
      </div>
      
      {/* Search Stats */}
      {totalResults > 0 && (
        <div className="flex items-center gap-4 text-xs text-gray-500">
          <span>{totalResults} results</span>
          <span className="flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {searchTime.toFixed(0)}ms
          </span>
        </div>
      )}
      
      {/* Loading State */}
      {isLoading && (
        <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin" style={{ color: THEME.colors.primary }} />
        </div>
      )}
      
      {/* Error State */}
      {error && (
        <div className="text-red-400 text-sm p-4 bg-red-900/20 border border-red-800 rounded-md">
          {error}
        </div>
      )}
      
      {/* Results */}
      {!isLoading && !error && (
        <div className="space-y-2">
          {/* Combined Results */}
          {searchMode === 'combined' && combinedResults.map((result) => (
            <div
              key={`${result.result_type}-${result.id}`}
              className="p-3 bg-black/40 border border-gray-700 rounded-md hover:border-gray-600 cursor-pointer transition-colors"
              onClick={() => {
                if (result.result_type === 'thread') {
                  onSelectThread?.(result.id);
                } else if (result.thread_id) {
                  onSelectMessage?.(result.id, result.thread_id);
                }
              }}
            >
              <div className="flex items-start gap-3">
                <div className="mt-1">
                  {result.result_type === 'thread' ? (
                    <MessageSquare className="h-4 w-4 text-cyan-400" />
                  ) : (
                    <MessageSquare className="h-4 w-4 text-gray-500" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge variant="outline" className="text-xs bg-gray-800 text-gray-400">
                      {result.result_type}
                    </Badge>
                    {result.title && (
                      <span className="text-sm font-medium text-gray-200 truncate">
                        {result.title}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-400 line-clamp-2">
                    {result.snippet}
                  </p>
                  <div className="flex items-center gap-2 mt-1 text-xs text-gray-500">
                    <span>Score: {(result.relevance_score * 100).toFixed(0)}%</span>
                    <span>{new Date(result.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
              </div>
            </div>
          ))}
          
          {/* Thread Results */}
          {searchMode === 'threads' && threadResults.map((result) => (
            <div
              key={result.thread_id}
              className="p-3 bg-black/40 border border-gray-700 rounded-md hover:border-gray-600 cursor-pointer transition-colors"
              onClick={() => onSelectThread?.(result.thread_id)}
            >
              <div className="flex items-start gap-3">
                  <MessageSquare className="h-4 w-4 mt-1" style={{ color: THEME.colors.secondary }} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-medium text-gray-200">
                      {result.highlighted_title 
                        ? renderHighlighted(result.highlighted_title)
                        : result.title || 'Untitled Thread'
                      }
                    </span>
                    <Badge variant="outline" className={cn('text-xs', getStatusBadgeColor(result.status))}>
                      {result.status}
                    </Badge>
                  </div>
                  {result.highlighted_summary && (
                    <p className="text-sm text-gray-400 line-clamp-2 mb-1">
                      {renderHighlighted(result.highlighted_summary)}
                    </p>
                  )}
                  <div className="flex items-center gap-3 text-xs text-gray-500">
                    <span className="flex items-center gap-1">
                      <MessageSquare className="h-3 w-3" />
                      {result.message_count} messages
                    </span>
                    {result.matching_message_count !== undefined && result.matching_message_count > 0 && (
                      <span style={{ color: THEME.colors.accent }}>
                        {result.matching_message_count} matching
                      </span>
                    )}
                    <span>Score: {(result.relevance_score * 10).toFixed(0)}%</span>
                  </div>
                </div>
              </div>
            </div>
          ))}
          
          {/* Message Results */}
          {searchMode === 'messages' && messageResults.map((result) => (
            <div
              key={result.message_id}
              className="p-3 bg-black/40 border border-gray-700 rounded-md hover:border-gray-600 cursor-pointer transition-colors"
              onClick={() => onSelectMessage?.(result.message_id, result.thread_id)}
            >
              <div className="flex items-start gap-3">
                <div className="mt-1">
                  <Badge variant="outline" className={cn('text-xs', getRoleBadgeColor(result.role))}>
                    {result.role}
                  </Badge>
                </div>
                <div className="flex-1 min-w-0">
                  {result.thread_title && (
                    <div className="text-xs text-gray-500 mb-1">
                      in <span className="text-gray-400">{result.thread_title}</span>
                    </div>
                  )}
                  <p className="text-sm text-gray-300 line-clamp-3">
                    {result.highlighted_content 
                      ? renderHighlighted(result.highlighted_content)
                      : result.content
                    }
                  </p>
                  <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
                    <span>Score: {(result.relevance_score * 10).toFixed(0)}%</span>
                    {result.citation_count > 0 && (
                      <span style={{ color: THEME.colors.primary }}>
                        {result.citation_count} citations
                      </span>
                    )}
                    <span>{new Date(result.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
              </div>
            </div>
          ))}
          
          {/* Empty State */}
          {query.length >= 2 && !isLoading && totalResults === 0 && (
            <div className="text-center py-8 text-gray-500">
              No results found for "{query}"
            </div>
          )}
          
          {/* Load More Button */}
          {hasMore && !isLoading && (
            <Button
              variant="outline"
              className="w-full bg-black/40 border-gray-700 hover:bg-gray-800"
              onClick={handleLoadMore}
            >
              <ChevronDown className="h-4 w-4 mr-2" />
              Load More
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

export default ThreadMessageSearch;
