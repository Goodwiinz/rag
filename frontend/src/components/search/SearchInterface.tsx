import React, { useState, useCallback, useEffect, useRef } from 'react';
import {
  MagnifyingGlassIcon,
  FunnelIcon,
  ClockIcon,
  BookmarkIcon,
  XMarkIcon,
  ChevronDownIcon,
  SparklesIcon,
  DocumentTextIcon,
} from '@heroicons/react/24/outline';
import {
  SearchRequest,
  SearchResult,
  QueryHistory,
  QuerySuggestions,
} from '@/types/search';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { IconButton } from '@/components/ui/icon-button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Card } from '@/components/ui/card';

interface SearchInterfaceProps {
  className?: string;
  onSearch: (
    query: string,
    filters?: SearchRequest['filters']
  ) => Promise<SearchResult | void>;
  onGetSuggestions?: (query: string) => Promise<QuerySuggestions>;
  onGetHistory?: () => Promise<QueryHistory[]>;
  onSaveSearch?: (query: string, name: string) => Promise<void>;
  loading?: boolean;
  placeholder?: string;
  autoFocus?: boolean;
}

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

export const SearchInterface: React.FC<SearchInterfaceProps> = ({
  className,
  onSearch,
  onGetSuggestions,
  onGetHistory,
  onSaveSearch,
  loading = false,
  placeholder = 'Search your documents...',
  autoFocus = false,
}) => {
  const [query, setQuery] = useState('');
  const [filters, setFilters] = useState<SearchFilters>({});
  const [showFilters, setShowFilters] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [showSavedSearches, setShowSavedSearches] = useState(false);
  const [suggestions, setSuggestions] = useState<QuerySuggestions | null>(null);
  const [history, setHistory] = useState<QueryHistory[]>([]);
  const [savedSearches, setSavedSearches] = useState<
    Array<{ id: string; name: string; query: string }>
  >([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedSuggestionIndex, setSelectedSuggestionIndex] = useState(-1);
  const [isSearching, setIsSearching] = useState(false);
  const [lastQuery, setLastQuery] = useState('');

  const searchInputRef = useRef<HTMLInputElement>(null);
  const suggestionsRef = useRef<HTMLDivElement>(null);
  const filtersRef = useRef<HTMLDivElement>(null);

  // File type options
  const fileTypeOptions = [
    { value: 'pdf', label: 'PDF Documents' },
    { value: 'txt', label: 'Text Files' },
    { value: 'jpg', label: 'JPEG Images' },
    { value: 'png', label: 'PNG Images' },
    { value: 'mp3', label: 'Audio Files' },
    { value: 'mp4', label: 'Video Files' },
  ];

  // Modality options
  const modalityOptions = [
    { value: 'text', label: 'Text Content' },
    { value: 'image', label: 'Images' },
    { value: 'audio', label: 'Audio' },
    { value: 'video', label: 'Video' },
  ];

  // Fetch suggestions when query changes
  useEffect(() => {
    if (query.trim().length >= 2 && onGetSuggestions) {
      const debounceTimer = setTimeout(async () => {
        try {
          const result = await onGetSuggestions(query);
          setSuggestions(result);
          setShowSuggestions(true);
          setSelectedSuggestionIndex(-1);
        } catch (error) {
          console.error('Failed to fetch suggestions:', error);
          setSuggestions(null);
        }
      }, 300);

      return () => clearTimeout(debounceTimer);
    } else {
      setSuggestions(null);
      setShowSuggestions(false);
      return undefined;
    }
  }, [query, onGetSuggestions]);

  // Fetch search history on mount
  useEffect(() => {
    if (onGetHistory) {
      onGetHistory()
        .then(setHistory)
        .catch((error) =>
          console.error('Failed to fetch search history:', error)
        );
    }
  }, [onGetHistory]);

  // Close suggestions when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        suggestionsRef.current &&
        !suggestionsRef.current.contains(event.target as Node)
      ) {
        setShowSuggestions(false);
      }
      if (
        filtersRef.current &&
        !filtersRef.current.contains(event.target as Node)
      ) {
        setShowFilters(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  // Global / keyboard shortcut for search focus
  useEffect(() => {
    const handleGlobalKeydown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (
        e.key === '/' &&
        target.tagName !== 'INPUT' &&
        target.tagName !== 'TEXTAREA'
      ) {
        e.preventDefault();
        searchInputRef.current?.focus();
      }
    };

    document.addEventListener('keydown', handleGlobalKeydown);
    return () => {
      document.removeEventListener('keydown', handleGlobalKeydown);
    };
  }, []);

  const handleSearch = useCallback(
    async (searchQuery: string = query) => {
      if (!searchQuery.trim()) return;

      setIsSearching(true);
      setLastQuery(searchQuery);
      setShowSuggestions(false);

      try {
        const activeFilters =
          Object.keys(filters).length > 0 ? filters : undefined;
        await onSearch(searchQuery.trim(), activeFilters);
      } catch (error) {
        console.error('Search failed:', error);
      } finally {
        setIsSearching(false);
      }
    },
    [query, filters, onSearch]
  );

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      handleSearch();
    },
    [handleSearch]
  );

  const handleSuggestionClick = useCallback(
    (suggestion: string) => {
      setQuery(suggestion);
      setShowSuggestions(false);
      handleSearch(suggestion);
    },
    [handleSearch]
  );

  const handleHistoryClick = useCallback(
    (historyItem: QueryHistory) => {
      setQuery(historyItem.query);
      setShowHistory(false);
      handleSearch(historyItem.query);
    },
    [handleSearch]
  );

  const handleSavedSearchClick = useCallback(
    (savedSearch: { query: string; name: string }) => {
      setQuery(savedSearch.query);
      setShowSavedSearches(false);
      handleSearch(savedSearch.query);
    },
    [handleSearch]
  );

  const handleSaveSearch = useCallback(async () => {
    if (!onSaveSearch || !query.trim()) return;

    const name = prompt('Enter a name for this search:');
    if (name && name.trim()) {
      try {
        await onSaveSearch(query.trim(), name.trim());
        const newSavedSearch = {
          id: Date.now().toString(),
          name: name.trim(),
          query: query.trim(),
        };
        setSavedSearches((prev) => [...prev, newSavedSearch]);
      } catch (error) {
        console.error('Failed to save search:', error);
      }
    }
  }, [query, onSaveSearch]);

  const handleFilterChange = useCallback(
    (key: keyof SearchFilters, value: any) => {
      setFilters((prev) => {
        const newFilters = { ...prev };
        if (
          value === undefined ||
          value === '' ||
          (Array.isArray(value) && value.length === 0)
        ) {
          delete newFilters[key];
        } else {
          newFilters[key] = value;
        }
        return newFilters;
      });
    },
    []
  );

  const clearFilters = useCallback(() => {
    setFilters({});
  }, []);

  const handleClear = useCallback(() => {
    setQuery('');
    setShowSuggestions(false);
    setSelectedSuggestionIndex(-1);
    searchInputRef.current?.focus();
  }, []);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (!showSuggestions || !suggestions) return;

      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          const totalSuggestions =
            suggestions.auto_complete.length +
            suggestions.related_queries.length;
          setSelectedSuggestionIndex((prev) =>
            prev < totalSuggestions - 1 ? prev + 1 : prev
          );
          break;
        case 'ArrowUp':
          e.preventDefault();
          setSelectedSuggestionIndex((prev) => (prev > -1 ? prev - 1 : -1));
          break;
        case 'Enter':
          e.preventDefault();
          const autoCompleteLength = suggestions.auto_complete.length;
          if (
            selectedSuggestionIndex >= 0 &&
            selectedSuggestionIndex < autoCompleteLength
          ) {
            const suggestion =
              suggestions.auto_complete[selectedSuggestionIndex];
            if (suggestion) {
              handleSuggestionClick(suggestion);
            }
          } else if (selectedSuggestionIndex >= autoCompleteLength) {
            const relatedIndex = selectedSuggestionIndex - autoCompleteLength;
            const relatedQuery = suggestions.related_queries[relatedIndex];
            if (relatedQuery?.query) {
              handleSuggestionClick(relatedQuery.query);
            }
          } else {
            handleSearch();
          }
          break;
        case 'Escape':
          if (showSuggestions) {
            setShowSuggestions(false);
            setSelectedSuggestionIndex(-1);
          } else if (query) {
            handleClear();
          }
          break;
      }
    },
    [
      showSuggestions,
      suggestions,
      selectedSuggestionIndex,
      handleSuggestionClick,
      handleSearch,
    ]
  );

  const hasActiveFilters = Object.keys(filters).length > 0;

  const toggleQuickFilter = (type: string, value: any) => {
    switch (type) {
      case 'file_type':
        const currentTypes = filters.file_types || [];
        if (currentTypes.includes(value)) {
          handleFilterChange(
            'file_types',
            currentTypes.filter((t) => t !== value)
          );
        } else {
          handleFilterChange('file_types', [...currentTypes, value]);
        }
        break;
      case 'date':
        if (filters.date_range) {
          handleFilterChange('date_range', undefined);
        } else {
          const end = new Date();
          const start = new Date();
          start.setDate(start.getDate() - 7);
          handleFilterChange('date_range', {
            start: start.toISOString().split('T')[0],
            end: end.toISOString().split('T')[0],
          });
        }
        break;
      case 'confidence':
        if (filters.min_confidence === 0.8) {
          handleFilterChange('min_confidence', undefined);
        } else {
          handleFilterChange('min_confidence', 0.8);
        }
        break;
    }
  };

  return (
    <div className={cn('w-full space-y-4', className)}>
      {/* Search Input */}
      <form onSubmit={handleSubmit} className="relative group z-20">
        <div className="relative">
          <MagnifyingGlassIcon className="absolute left-5 top-1/2 transform -translate-y-1/2 h-5 w-5 text-muted-foreground group-focus-within:text-primary transition-colors duration-200" />
          <Input
            ref={searchInputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => query.trim().length >= 2 && setShowSuggestions(true)}
            placeholder={placeholder}
            className="pl-14 pr-32 h-14 text-lg bg-background/50 backdrop-blur-xl shadow-sm hover:shadow-md focus-visible:ring-2 focus-visible:ring-primary/20 focus-visible:border-primary border-muted-foreground/20 rounded-2xl transition-all duration-200 placeholder:text-muted-foreground/50"
            disabled={isSearching}
            autoFocus={autoFocus}
            aria-label="Search query"
          />

          {/* Clear Button / Keyboard Hint */}
          {query ? (
            <IconButton
              icon={<XMarkIcon className="h-4 w-4" />}
              label="Clear search"
              onClick={handleClear}
              className="absolute right-28 top-1/2 transform -translate-y-1/2 h-8 w-8 text-muted-foreground hover:text-foreground hover:bg-muted"
            />
          ) : (
            <div
              className="absolute right-28 top-1/2 transform -translate-y-1/2 hidden sm:flex pointer-events-none select-none items-center gap-1 rounded border border-muted-foreground/30 bg-muted/20 px-1.5 font-mono text-[10px] font-medium text-muted-foreground opacity-70"
              aria-hidden="true"
            >
              <span className="text-xs">/</span>
            </div>
          )}

          {/* Search Actions */}
          <div className="absolute right-3 top-1/2 transform -translate-y-1/2 flex items-center space-x-1.5">
            {/* Filters Button */}
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={() => setShowFilters(!showFilters)}
              className={cn(
                'h-9 w-9 rounded-xl hover:bg-muted text-muted-foreground transition-colors',
                hasActiveFilters &&
                  'text-primary bg-primary/10 hover:bg-primary/20'
              )}
              title="Filters"
              aria-label={showFilters ? 'Close filters' : 'Toggle filters'}
              aria-expanded={showFilters}
            >
              <FunnelIcon className="h-5 w-5" />
            </Button>

            <div className="h-5 w-px bg-border/50 mx-1" />

            {/* Search Button */}
            <Button
              type="submit"
              size="icon"
              disabled={!query.trim() || isSearching}
              aria-label={isSearching ? 'Searching...' : 'Search'}
              className={cn(
                'h-9 w-9 rounded-xl transition-all duration-200',
                query.trim()
                  ? 'bg-primary text-primary-foreground hover:bg-primary/90 shadow-md hover:shadow-lg hover:scale-105'
                  : 'bg-muted text-muted-foreground'
              )}
            >
              {isSearching ? (
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-current border-t-transparent" />
              ) : (
                <SparklesIcon className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>

        {/* Suggestions Dropdown */}
        {showSuggestions && suggestions && (
          <div
            ref={suggestionsRef}
            className="absolute top-full left-0 right-0 z-50 mt-2 bg-popover/95 backdrop-blur-xl border border-border/50 rounded-2xl shadow-2xl max-h-[32rem] overflow-y-auto animate-in fade-in slide-in-from-top-2 duration-200 ring-1 ring-black/5"
          >
            {/* Auto-complete suggestions */}
            {suggestions.auto_complete.length > 0 && (
              <div className="p-2">
                <p className="px-3 py-2 text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
                  Suggestions
                </p>
                {suggestions.auto_complete.map((suggestion, index) => (
                  <button
                    key={index}
                    type="button"
                    onClick={() => handleSuggestionClick(suggestion)}
                    className={cn(
                      'w-full text-left px-3 py-2.5 text-sm rounded-xl transition-all duration-150 flex items-center space-x-3 group',
                      selectedSuggestionIndex === index
                        ? 'bg-accent text-accent-foreground'
                        : 'hover:bg-accent/50 text-foreground'
                    )}
                  >
                    <div
                      className={cn(
                        'p-1.5 rounded-lg transition-colors',
                        selectedSuggestionIndex === index
                          ? 'bg-background text-primary'
                          : 'bg-muted text-muted-foreground group-hover:bg-background group-hover:text-foreground'
                      )}
                    >
                      <MagnifyingGlassIcon className="h-4 w-4" />
                    </div>
                    <span className="font-medium">{suggestion}</span>
                  </button>
                ))}
              </div>
            )}

            {/* Related queries */}
            {suggestions.related_queries.length > 0 && (
              <div className="p-2 border-t border-border/50 bg-muted/30">
                <p className="px-3 py-2 text-[10px] font-bold text-muted-foreground uppercase tracking-wider flex items-center">
                  <SparklesIcon className="h-3 w-3 mr-1.5 text-primary" />
                  Related Topics
                </p>
                {suggestions.related_queries.map((related, index) => (
                  <button
                    key={related.query}
                    type="button"
                    onClick={() => handleSuggestionClick(related.query)}
                    className={cn(
                      'w-full text-left px-3 py-2.5 text-sm rounded-xl transition-all duration-150 flex items-center justify-between group',
                      selectedSuggestionIndex ===
                        suggestions.auto_complete.length + index
                        ? 'bg-accent text-accent-foreground'
                        : 'hover:bg-background hover:shadow-sm text-foreground'
                    )}
                  >
                    <span className="font-medium">{related.query}</span>
                    <Badge
                      variant="secondary"
                      className={cn(
                        'text-[10px] h-5 px-1.5 transition-colors font-mono',
                        selectedSuggestionIndex ===
                          suggestions.auto_complete.length + index
                          ? 'bg-background text-foreground'
                          : 'bg-muted text-muted-foreground'
                      )}
                    >
                      {Math.round(related.similarity * 100)}%
                    </Badge>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </form>

      {/* Quick Filters */}
      {!hasActiveFilters && !showFilters && (
        <div className="flex flex-wrap items-center justify-center gap-2 animate-in fade-in slide-in-from-top-1 duration-500">
          <button
            onClick={() => toggleQuickFilter('file_type', 'pdf')}
            className={cn(
              'px-3 py-1.5 rounded-full text-xs font-medium border transition-all duration-200 flex items-center space-x-1.5',
              filters.file_types?.includes('pdf')
                ? 'bg-primary/10 border-primary/20 text-primary'
                : 'bg-background border-border hover:border-primary/50 hover:bg-accent text-muted-foreground hover:text-foreground'
            )}
          >
            <DocumentTextIcon className="h-3.5 w-3.5" />
            <span>PDFs</span>
          </button>
          <button
            onClick={() => toggleQuickFilter('date', 'week')}
            className={cn(
              'px-3 py-1.5 rounded-full text-xs font-medium border transition-all duration-200 flex items-center space-x-1.5',
              filters.date_range
                ? 'bg-primary/10 border-primary/20 text-primary'
                : 'bg-background border-border hover:border-primary/50 hover:bg-accent text-muted-foreground hover:text-foreground'
            )}
          >
            <ClockIcon className="h-3.5 w-3.5" />
            <span>Last 7 Days</span>
          </button>
          <button
            onClick={() => toggleQuickFilter('confidence', 0.8)}
            className={cn(
              'px-3 py-1.5 rounded-full text-xs font-medium border transition-all duration-200 flex items-center space-x-1.5',
              filters.min_confidence === 0.8
                ? 'bg-primary/10 border-primary/20 text-primary'
                : 'bg-background border-border hover:border-primary/50 hover:bg-accent text-muted-foreground hover:text-foreground'
            )}
          >
            <SparklesIcon className="h-3.5 w-3.5" />
            <span>High Confidence</span>
          </button>
        </div>
      )}

      {/* Active Filters Display */}
      {hasActiveFilters && (
        <div className="flex items-center justify-between p-3 bg-muted/30 border border-border/50 rounded-xl animate-in fade-in slide-in-from-top-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-medium text-muted-foreground mr-1">
              Active:
            </span>
            {filters.modalities &&
              filters.modalities.map((m) => (
                <Badge
                  key={m}
                  variant="secondary"
                  className="bg-background border-border text-foreground px-2 py-0.5 text-xs font-normal"
                >
                  {m}
                  <button
                    type="button"
                    onClick={() =>
                      handleFilterChange(
                        'modalities',
                        filters.modalities?.filter((i) => i !== m)
                      )
                    }
                    className="ml-1.5 hover:text-destructive focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive rounded-sm"
                    aria-label={`Remove ${m} filter`}
                  >
                    ×
                  </button>
                </Badge>
              ))}
            {filters.file_types &&
              filters.file_types.map((f) => (
                <Badge
                  key={f}
                  variant="secondary"
                  className="bg-background border-border text-foreground px-2 py-0.5 text-xs font-normal"
                >
                  .{f}
                  <button
                    type="button"
                    onClick={() => toggleQuickFilter('file_type', f)}
                    className="ml-1.5 hover:text-destructive focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive rounded-sm"
                    aria-label={`Remove ${f} file type filter`}
                  >
                    ×
                  </button>
                </Badge>
              ))}
            {filters.date_range && (
              <Badge
                variant="secondary"
                className="bg-background border-border text-foreground px-2 py-0.5 text-xs font-normal"
              >
                Last 7 Days
                <button
                  type="button"
                  onClick={() => toggleQuickFilter('date', 'week')}
                  className="ml-1.5 hover:text-destructive focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive rounded-sm"
                  aria-label="Remove date range filter"
                >
                  ×
                </button>
              </Badge>
            )}
            {filters.min_confidence && (
              <Badge
                variant="secondary"
                className="bg-background border-border text-foreground px-2 py-0.5 text-xs font-normal"
              >
                High Confidence
                <button
                  type="button"
                  onClick={() => toggleQuickFilter('confidence', 0.8)}
                  className="ml-1.5 hover:text-destructive focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive rounded-sm"
                  aria-label="Remove confidence filter"
                >
                  ×
                </button>
              </Badge>
            )}
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={clearFilters}
            className="text-xs h-6 px-2 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
          >
            Clear all
          </Button>
        </div>
      )}

      {/* Filters Panel */}
      {showFilters && (
        <Card
          ref={filtersRef}
          className="absolute top-full left-0 right-0 z-40 mt-2 p-4 shadow-2xl border-border/50 bg-popover/95 backdrop-blur-xl rounded-2xl animate-in fade-in zoom-in-95 duration-200"
        >
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-foreground">
              Advanced Filters
            </h3>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowFilters(false)}
              className="h-8 w-8 p-0"
              aria-label="Close filters"
            >
              <XMarkIcon className="h-4 w-4" />
            </Button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-4">
              {/* Modality Filter */}
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wider">
                  Content Type
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {modalityOptions.map((option) => (
                    <label
                      key={option.value}
                      className="flex items-center space-x-2 cursor-pointer group"
                    >
                      <div className="relative flex items-center">
                        <input
                          type="checkbox"
                          checked={
                            filters.modalities?.includes(option.value as any) ||
                            false
                          }
                          onChange={(e) => {
                            const current = filters.modalities || [];
                            if (e.target.checked) {
                              handleFilterChange('modalities', [
                                ...current,
                                option.value as any,
                              ]);
                            } else {
                              handleFilterChange(
                                'modalities',
                                current.filter((m) => m !== option.value)
                              );
                            }
                          }}
                          className="peer h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary/20"
                        />
                      </div>
                      <span className="text-sm text-foreground group-hover:text-primary transition-colors">
                        {option.label}
                      </span>
                    </label>
                  ))}
                </div>
              </div>

              {/* File Type Filter */}
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wider">
                  File Type
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {fileTypeOptions.map((option) => (
                    <label
                      key={option.value}
                      className="flex items-center space-x-2 cursor-pointer group"
                    >
                      <input
                        type="checkbox"
                        checked={
                          filters.file_types?.includes(option.value as any) ||
                          false
                        }
                        onChange={(e) => {
                          const current = filters.file_types || [];
                          if (e.target.checked) {
                            handleFilterChange('file_types', [
                              ...current,
                              option.value as any,
                            ]);
                          } else {
                            handleFilterChange(
                              'file_types',
                              current.filter((f) => f !== option.value)
                            );
                          }
                        }}
                        className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary/20"
                      />
                      <span className="text-sm text-foreground group-hover:text-primary transition-colors">
                        {option.label}
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            </div>

            <div className="space-y-4">
              {/* Date Range Filter */}
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wider">
                  Date Range
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <div className="space-y-1">
                    <span className="text-[10px] text-muted-foreground">
                      Start
                    </span>
                    <Input
                      type="date"
                      value={filters.date_range?.start || ''}
                      onChange={(e) => {
                        const start = e.target.value;
                        const current = filters.date_range || {};
                        handleFilterChange('date_range', { ...current, start });
                      }}
                      className="text-sm h-9"
                      aria-label="Start date"
                    />
                  </div>
                  <div className="space-y-1">
                    <span className="text-[10px] text-muted-foreground">
                      End
                    </span>
                    <Input
                      type="date"
                      value={filters.date_range?.end || ''}
                      onChange={(e) => {
                        const end = e.target.value;
                        const current = filters.date_range || {};
                        handleFilterChange('date_range', { ...current, end });
                      }}
                      className="text-sm h-9"
                      aria-label="End date"
                    />
                  </div>
                </div>
              </div>

              {/* Confidence Filter */}
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wider">
                  Minimum Confidence
                </label>
                <Select
                  value={filters.min_confidence?.toString() || 'any'}
                  onValueChange={(value) =>
                    handleFilterChange(
                      'min_confidence',
                      value === 'any' ? undefined : parseFloat(value)
                    )
                  }
                >
                  <SelectTrigger
                    className="text-sm h-9"
                    aria-label="Minimum confidence"
                  >
                    <SelectValue placeholder="Any confidence" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="any">Any confidence</SelectItem>
                    <SelectItem value="0.9">90% and above</SelectItem>
                    <SelectItem value="0.8">80% and above</SelectItem>
                    <SelectItem value="0.7">70% and above</SelectItem>
                    <SelectItem value="0.6">60% and above</SelectItem>
                    <SelectItem value="0.5">50% and above</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Max Results Filter */}
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wider">
                  Maximum Results
                </label>
                <Select
                  value={filters.max_results?.toString() || 'default'}
                  onValueChange={(value) =>
                    handleFilterChange(
                      'max_results',
                      value === 'default' ? undefined : parseInt(value, 10)
                    )
                  }
                >
                  <SelectTrigger
                    className="text-sm h-9"
                    aria-label="Maximum results"
                  >
                    <SelectValue placeholder="Default" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="default">Default (10)</SelectItem>
                    <SelectItem value="5">5 results</SelectItem>
                    <SelectItem value="10">10 results</SelectItem>
                    <SelectItem value="20">20 results</SelectItem>
                    <SelectItem value="50">50 results</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>

          {/* Apply Filters Button */}
          <div className="flex space-x-2 pt-4 mt-4 border-t border-border/50">
            <Button
              onClick={() => {
                handleSearch();
                setShowFilters(false);
              }}
              className="flex-1"
            >
              Apply Filters
            </Button>
            <Button variant="outline" onClick={clearFilters}>
              Clear
            </Button>
          </div>
        </Card>
      )}

      {/* Search History Dialog */}
      <Dialog open={showHistory} onOpenChange={setShowHistory}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center space-x-2">
              <ClockIcon className="h-5 w-5" />
              <span>Search History</span>
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-2 max-h-96 overflow-y-auto">
            {history.length === 0 ? (
              <div className="text-center py-8">
                <DocumentTextIcon className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-500">No search history yet</p>
              </div>
            ) : (
              history.map((item) => (
                <button
                  key={item.id}
                  onClick={() => handleHistoryClick(item)}
                  className="w-full text-left p-3 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">
                        {item.query}
                      </p>
                      <p className="text-xs text-gray-500 mt-1">
                        {item.answer_preview}
                      </p>
                    </div>
                    <div className="ml-4 text-right">
                      <p className="text-xs text-gray-500">
                        {new Date(item.created_at).toLocaleDateString()}
                      </p>
                      <p className="text-xs text-gray-400">
                        {item.metrics.latency_ms}ms
                      </p>
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Saved Searches Dialog */}
      <Dialog open={showSavedSearches} onOpenChange={setShowSavedSearches}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center space-x-2">
              <BookmarkIcon className="h-5 w-5" />
              <span>Saved Searches</span>
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-2 max-h-96 overflow-y-auto">
            {savedSearches.length === 0 ? (
              <div className="text-center py-8">
                <BookmarkIcon className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-500">No saved searches yet</p>
                <p className="text-xs text-gray-400 mt-2">
                  Save a search to quickly access it later
                </p>
              </div>
            ) : (
              savedSearches.map((saved) => (
                <button
                  key={saved.id}
                  onClick={() => handleSavedSearchClick(saved)}
                  className="w-full text-left p-3 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-gray-900">
                        {saved.name}
                      </p>
                      <p className="text-xs text-gray-500 mt-1 truncate">
                        {saved.query}
                      </p>
                    </div>
                    <ChevronDownIcon className="h-4 w-4 text-gray-400" />
                  </div>
                </button>
              ))
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default SearchInterface;
