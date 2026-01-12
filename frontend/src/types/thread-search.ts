/**
 * Thread and Message Search Types
 * 
 * Types for full-text search functionality across threads and messages
 */

// ============================================================================
// Enums
// ============================================================================

export type ThreadSearchSortOrder = 
  | 'relevance'
  | 'date_desc'
  | 'date_asc'
  | 'message_count'
  | 'last_activity';

export type MessageSearchSortOrder = 
  | 'relevance'
  | 'date_desc'
  | 'date_asc';

export type ThreadStatus = 'active' | 'resolved' | 'archived';
export type MessageRole = 'user' | 'assistant' | 'system' | 'tool';

// ============================================================================
// Filter Types
// ============================================================================

export interface ThreadSearchFilter {
  conversation_id?: string;
  workspace_id?: string;
  status?: ThreadStatus[];
  created_by_id?: string;
  date_from?: string;
  date_to?: string;
  min_message_count?: number;
}

export interface MessageSearchFilter {
  thread_id?: string;
  conversation_id?: string;
  workspace_id?: string;
  user_id?: string;
  roles?: MessageRole[];
  date_from?: string;
  date_to?: string;
  has_citations?: boolean;
}

// ============================================================================
// Request Types
// ============================================================================

export interface ThreadSearchRequest {
  query: string;
  filters?: ThreadSearchFilter;
  sort_order?: ThreadSearchSortOrder;
  limit?: number;
  offset?: number;
  include_snippets?: boolean;
  include_messages?: boolean;
}

export interface MessageSearchRequest {
  query: string;
  filters?: MessageSearchFilter;
  sort_order?: MessageSearchSortOrder;
  limit?: number;
  offset?: number;
  include_context?: boolean;
}

// ============================================================================
// Result Types
// ============================================================================

export interface ThreadSearchResult {
  thread_id: string;
  title: string | null;
  summary: string | null;
  status: ThreadStatus;
  conversation_id: string;
  relevance_score: number;
  message_count: number;
  last_message_at: string;
  created_at: string;
  highlighted_title?: string;
  highlighted_summary?: string;
  matching_message_count?: number;
}

export interface MessageSearchResult {
  message_id: string;
  thread_id: string;
  content: string;
  role: MessageRole;
  user_id: string | null;
  relevance_score: number;
  created_at: string;
  highlighted_content?: string;
  thread_title?: string;
  conversation_id?: string;
  citation_count: number;
}

export interface CombinedSearchResult {
  result_type: 'thread' | 'message';
  id: string;
  relevance_score: number;
  title?: string;
  content?: string;
  snippet: string;
  thread_id?: string;
  conversation_id?: string;
  created_at: string;
}

// ============================================================================
// Response Types
// ============================================================================

export interface ThreadSearchResponse {
  query: string;
  search_id: string;
  results: ThreadSearchResult[];
  total_results: number;
  returned_results: number;
  search_time_ms: number;
  limit: number;
  offset: number;
  has_more: boolean;
  filters_applied?: Record<string, unknown>;
}

export interface MessageSearchResponse {
  query: string;
  search_id: string;
  results: MessageSearchResult[];
  total_results: number;
  returned_results: number;
  search_time_ms: number;
  limit: number;
  offset: number;
  has_more: boolean;
  filters_applied?: Record<string, unknown>;
}

export interface CombinedSearchResponse {
  query: string;
  search_id: string;
  results: CombinedSearchResult[];
  total_results: number;
  search_time_ms: number;
  has_more: boolean;
}

export interface SearchSuggestionsResponse {
  query: string;
  suggestions: string[];
}

export interface SearchHealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  search_functional: boolean;
  gin_indexes: Array<{
    name: string;
    definition: string;
  }>;
  index_count: number;
  error?: string;
}

// ============================================================================
// UI State Types
// ============================================================================

export interface ThreadSearchState {
  query: string;
  results: ThreadSearchResult[];
  isLoading: boolean;
  error: string | null;
  totalResults: number;
  hasMore: boolean;
  searchTime: number;
  filters: ThreadSearchFilter;
  sortOrder: ThreadSearchSortOrder;
}

export interface MessageSearchState {
  query: string;
  results: MessageSearchResult[];
  isLoading: boolean;
  error: string | null;
  totalResults: number;
  hasMore: boolean;
  searchTime: number;
  filters: MessageSearchFilter;
  sortOrder: MessageSearchSortOrder;
}

export interface CombinedSearchState {
  query: string;
  results: CombinedSearchResult[];
  isLoading: boolean;
  error: string | null;
  totalResults: number;
  hasMore: boolean;
  searchTime: number;
}
