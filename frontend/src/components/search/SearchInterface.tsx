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
import { SearchRequest, SearchResult, QueryHistory, QuerySuggestions } from '@/types/search';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';

interface SearchInterfaceProps {
  className?: string;
  onSearch: (query: string, filters?: SearchRequest['filters']) => Promise<SearchResult>;
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
  placeholder = "Search your documents...",
  autoFocus = false,
}) => {
  const [query, setQuery] = useState('');
  const [filters, setFilters] = useState<SearchFilters>({});
  const [showFilters, setShowFilters] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [showSavedSearches, setShowSavedSearches] = useState(false);
  const [suggestions, setSuggestions] = useState<QuerySuggestions | null>(null);
  const [history, setHistory] = useState<QueryHistory[]>([]);
  const [savedSearches, setSavedSearches] = useState<Array<{ id: string; name: string; query: string }>>([]);
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
        .catch(error => console.error('Failed to fetch search history:', error));
    }
  }, [onGetHistory]);

  // Close suggestions when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (suggestionsRef.current && !suggestionsRef.current.contains(event.target as Node)) {
        setShowSuggestions(false);
      }
      if (filtersRef.current && !filtersRef.current.contains(event.target as Node)) {
        setShowFilters(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const handleSearch = useCallback(async (searchQuery: string = query) => {
    if (!searchQuery.trim()) return;

    setIsSearching(true);
    setLastQuery(searchQuery);
    setShowSuggestions(false);

    try {
      await onSearch(searchQuery.trim(), filters);
    } catch (error) {
      console.error('Search failed:', error);
    } finally {
      setIsSearching(false);
    }
  }, [query, filters, onSearch]);

  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    handleSearch();
  }, [handleSearch]);

  const handleSuggestionClick = useCallback((suggestion: string) => {
    setQuery(suggestion);
    setShowSuggestions(false);
    handleSearch(suggestion);
  }, [handleSearch]);

  const handleHistoryClick = useCallback((historyItem: QueryHistory) => {
    setQuery(historyItem.query);
    setShowHistory(false);
    handleSearch(historyItem.query);
  }, [handleSearch]);

  const handleSavedSearchClick = useCallback((savedSearch: { query: string; name: string }) => {
    setQuery(savedSearch.query);
    setShowSavedSearches(false);
    handleSearch(savedSearch.query);
  }, [handleSearch]);

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
        setSavedSearches(prev => [...prev, newSavedSearch]);
      } catch (error) {
        console.error('Failed to save search:', error);
      }
    }
  }, [query, onSaveSearch]);

  const handleFilterChange = useCallback((key: keyof SearchFilters, value: any) => {
    setFilters(prev => {
      const newFilters = { ...prev };
      if (value === undefined || value === '' || (Array.isArray(value) && value.length === 0)) {
        delete newFilters[key];
      } else {
        newFilters[key] = value;
      }
      return newFilters;
    });
  }, []);

  const clearFilters = useCallback(() => {
    setFilters({});
  }, []);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (!showSuggestions || !suggestions) return;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        const totalSuggestions = suggestions.auto_complete.length + suggestions.related_queries.length;
        setSelectedSuggestionIndex(prev =>
          prev < totalSuggestions - 1 ? prev + 1 : prev
        );
        break;
      case 'ArrowUp':
        e.preventDefault();
        setSelectedSuggestionIndex(prev => prev > -1 ? prev - 1 : -1);
        break;
      case 'Enter':
        e.preventDefault();
        const autoCompleteLength = suggestions.auto_complete.length;
        if (selectedSuggestionIndex >= 0 && selectedSuggestionIndex < autoCompleteLength) {
          const suggestion = suggestions.auto_complete[selectedSuggestionIndex];
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
        setShowSuggestions(false);
        setSelectedSuggestionIndex(-1);
        break;
    }
  }, [showSuggestions, suggestions, selectedSuggestionIndex, handleSuggestionClick, handleSearch]);

  const hasActiveFilters = Object.keys(filters).length > 0;

  return (
    <div className={cn("w-full space-y-4", className)}>
      {/* Search Input */}
      <form onSubmit={handleSubmit} className="relative">
        <div className="relative">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-muted-foreground" />
          <Input
            ref={searchInputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => query.trim().length >= 2 && setShowSuggestions(true)}
            placeholder={placeholder}
            className="pl-10 pr-24"
            disabled={isSearching}
            autoFocus={autoFocus}
          />

          {/* Search Actions */}
          <div className="absolute right-2 top-1/2 transform -translate-y-1/2 flex items-center space-x-1">
            {/* Filters Button */}
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setShowFilters(!showFilters)}
              className={cn(
                "h-8 w-8 p-0",
                hasActiveFilters && "text-blue-600"
              )}
            >
              <FunnelIcon className="h-4 w-4" />
            </Button>

            {/* History Button */}
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setShowHistory(true)}
              className="h-8 w-8 p-0"
            >
              <ClockIcon className="h-4 w-4" />
            </Button>

            {/* Save Search Button */}
            {query.trim() && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={handleSaveSearch}
                className="h-8 w-8 p-0"
              >
                <BookmarkIcon className="h-4 w-4" />
              </Button>
            )}

            {/* Search Button */}
            <Button
              type="submit"
              size="sm"
              disabled={!query.trim() || isSearching}
              className="h-8 px-3"
            >
              {isSearching ? (
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
              ) : (
                <MagnifyingGlassIcon className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>

        {/* Suggestions Dropdown */}
        {showSuggestions && suggestions && (
          <div
            ref={suggestionsRef}
            className="absolute top-full left-0 right-0 z-50 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-y-auto"
          >
            {/* Auto-complete suggestions */}
            {suggestions.auto_complete.length > 0 && (
              <div className="p-2">
                <p className="text-xs font-medium text-gray-500 mb-2">Suggestions</p>
                {suggestions.auto_complete.map((suggestion, index) => (
                  <button
                    key={index}
                    type="button"
                    onClick={() => handleSuggestionClick(suggestion)}
                    className={cn(
                      "w-full text-left px-3 py-2 text-sm rounded-md hover:bg-gray-100 flex items-center space-x-2",
                      selectedSuggestionIndex === index && "bg-blue-50 text-blue-700"
                    )}
                  >
                    <SparklesIcon className="h-4 w-4 text-gray-400" />
                    <span>{suggestion}</span>
                  </button>
                ))}
              </div>
            )}

            {/* Related queries */}
            {suggestions.related_queries.length > 0 && (
              <div className="p-2 border-t">
                <p className="text-xs font-medium text-gray-500 mb-2">Related queries</p>
                {suggestions.related_queries.map((related, index) => (
                  <button
                    key={related.query}
                    type="button"
                    onClick={() => handleSuggestionClick(related.query)}
                    className={cn(
                      "w-full text-left px-3 py-2 text-sm rounded-md hover:bg-gray-100 flex items-center justify-between",
                      selectedSuggestionIndex === suggestions.auto_complete.length + index && "bg-blue-50 text-blue-700"
                    )}
                  >
                    <span>{related.query}</span>
                    <Badge variant="secondary" className="text-xs">
                      {Math.round(related.similarity * 100)}%
                    </Badge>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </form>

      {/* Active Filters */}
      {hasActiveFilters && (
        <div className="flex items-center justify-between p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex items-center space-x-2">
            <FunnelIcon className="h-4 w-4 text-blue-600" />
            <span className="text-sm text-blue-800">Active filters:</span>
            <div className="flex flex-wrap gap-1">
              {filters.modalities && (
                <Badge variant="secondary" className="text-xs">
                  Modalities: {filters.modalities.join(', ')}
                </Badge>
              )}
              {filters.file_types && (
                <Badge variant="secondary" className="text-xs">
                  File types: {filters.file_types.join(', ')}
                </Badge>
              )}
              {filters.date_range && (
                <Badge variant="secondary" className="text-xs">
                  Date: {filters.date_range.start} to {filters.date_range.end}
                </Badge>
              )}
              {filters.min_confidence && (
                <Badge variant="secondary" className="text-xs">
                  Min confidence: {filters.min_confidence}
                </Badge>
              )}
              {filters.max_results && (
                <Badge variant="secondary" className="text-xs">
                  Max results: {filters.max_results}
                </Badge>
              )}
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={clearFilters}
            className="text-blue-600 hover:text-blue-700"
          >
            Clear all
          </Button>
        </div>
      )}

      {/* Filters Panel */}
      {showFilters && (
        <div
          ref={filtersRef}
          className="bg-white border border-gray-200 rounded-lg shadow-lg p-4 z-40"
        >
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium text-gray-900">Search Filters</h3>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowFilters(false)}
            >
              <XMarkIcon className="h-4 w-4" />
            </Button>
          </div>

          <div className="space-y-4">
            {/* Modality Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Content Type
              </label>
              <div className="space-y-2">
                {modalityOptions.map((option) => (
                  <label key={option.value} className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={filters.modalities?.includes(option.value as any) || false}
                      onChange={(e) => {
                        const current = filters.modalities || [];
                        if (e.target.checked) {
                          handleFilterChange('modalities', [...current, option.value as any]);
                        } else {
                          handleFilterChange('modalities', current.filter(m => m !== option.value));
                        }
                      }}
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-700">{option.label}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* File Type Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                File Type
              </label>
              <div className="space-y-2">
                {fileTypeOptions.map((option) => (
                  <label key={option.value} className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={filters.file_types?.includes(option.value as any) || false}
                      onChange={(e) => {
                        const current = filters.file_types || [];
                        if (e.target.checked) {
                          handleFilterChange('file_types', [...current, option.value as any]);
                        } else {
                          handleFilterChange('file_types', current.filter(f => f !== option.value));
                        }
                      }}
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-700">{option.label}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Date Range Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Date Range
              </label>
              <div className="grid grid-cols-2 gap-2">
                <Input
                  type="date"
                  value={filters.date_range?.start || ''}
                  onChange={(e) => {
                    const start = e.target.value;
                    const current = filters.date_range || {};
                    handleFilterChange('date_range', { ...current, start });
                  }}
                  className="text-sm"
                />
                <Input
                  type="date"
                  value={filters.date_range?.end || ''}
                  onChange={(e) => {
                    const end = e.target.value;
                    const current = filters.date_range || {};
                    handleFilterChange('date_range', { ...current, end });
                  }}
                  className="text-sm"
                />
              </div>
            </div>

            {/* Confidence Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Minimum Confidence
              </label>
              <Select
                value={filters.min_confidence?.toString() || ''}
                onValueChange={(value) => handleFilterChange('min_confidence', value ? parseFloat(value) : undefined)}
              >
                <SelectTrigger className="text-sm">
                  <SelectValue placeholder="Any confidence" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">Any confidence</SelectItem>
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
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Maximum Results
              </label>
              <Select
                value={filters.max_results?.toString() || ''}
                onValueChange={(value) => handleFilterChange('max_results', value ? parseInt(value, 10) : undefined)}
              >
                <SelectTrigger className="text-sm">
                  <SelectValue placeholder="Default" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">Default (10)</SelectItem>
                  <SelectItem value="5">5 results</SelectItem>
                  <SelectItem value="10">10 results</SelectItem>
                  <SelectItem value="20">20 results</SelectItem>
                  <SelectItem value="50">50 results</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Apply Filters Button */}
            <div className="flex space-x-2 pt-2">
              <Button
                onClick={() => {
                  handleSearch();
                  setShowFilters(false);
                }}
                className="flex-1"
                size="sm"
              >
                Apply Filters
              </Button>
              <Button
                variant="outline"
                onClick={clearFilters}
                size="sm"
              >
                Clear
              </Button>
            </div>
          </div>
        </div>
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