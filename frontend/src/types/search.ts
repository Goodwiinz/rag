// Search and Query Types
export interface SearchRequest {
  query: string;
  filters?: {
    modalities?: ('text' | 'image' | 'audio' | 'video')[];
    document_ids?: string[];
    date_range?: {
      start: string;
      end: string;
    };
    file_types?: import('./document').Document['file_type'][];
  };
  limit?: number;
  offset?: number;
}

export interface SourceReference {
  document_id: string;
  document_title: string;
  snippet: string;
  confidence: number;
  page_number?: number;
  timestamp?: string;
  file_type: import('./document').Document['file_type'];
  url?: string; // For direct document access
}

export interface SearchAnswer {
  text: string;
  sources: SourceReference[];
  claims?: string[];
  confidence: number;
  coverage?: number;
  decisionTraceId?: string;
  answer_type: 'factual' | 'reasoning' | 'summarization' | 'comparison';
  language_detected: string;
}

export interface SearchResult {
  id: string;
  query: string;
  answer: SearchAnswer;
  entities: Entity[];
  relationships: Relationship[];
  metrics: SearchMetrics;
  processing_time_ms: number;
  created_at: string;
  user_id: string;
}

export interface SearchMetrics {
  latency_ms: number;
  retrieval_quality: number; // 0-100
  faithfulness_score: number; // 0-100
  contextual_relevancy: number; // 0-100
  hallucination_score: number; // 0-100
  answer_relevancy: number; // 0-100
  documents_retrieved: number;
  entities_found: number;
  relationships_found: number;
}

export interface QueryHistory {
  id: string;
  query: string;
  created_at: string;
  answer_preview: string; // First 100 characters
  has_answer: boolean;
  metrics: {
    latency_ms: number;
    quality_score: number;
  };
}

export interface QuerySuggestions {
  suggestions: string[];
  related_queries: Array<{
    query: string;
    similarity: number;
  }>;
  auto_complete: string[];
}

// Entity and Relationship Types (shared with knowledge graph)
export interface Entity {
  id: string;
  name: string;
  type: 'person' | 'organization' | 'location' | 'concept' | 'date' | 'product';
  confidence: number;
  description?: string;
  aliases: string[];
  mentions: number;
  first_seen: string;
  last_seen: string;
  document_ids: string[];
  metadata: Record<string, any>;
  position?: {
    x: number;
    y: number;
  };
  color?: string;
  size?: number;
}

export interface Relationship {
  id: string;
  source_entity_id: string;
  target_entity_id: string;
  relationship_type: string;
  confidence: number;
  context: string;
  document_ids: string[];
  first_seen: string;
  last_seen: string;
  weight: number;
  metadata: Record<string, any>;
}

// Query Processing Types
export interface QueryIntent {
  primary_intent: 'factual_lookup' | 'reasoning' | 'summarization' | 'comparison' | 'exploration';
  confidence: number;
  entities: Array<{
    name: string;
    type: string;
    confidence: number;
  }>;
  keywords: Array<{
    term: string;
    importance: number;
  }>;
  complexity: 'simple' | 'moderate' | 'complex';
  modality_preference: ('text' | 'image' | 'audio' | 'video')[];
  temporal_aspect: 'current' | 'historical' | 'future' | 'timeless';
  domain_specificity: 'general' | 'technical' | 'domain_expert';
  question_type?: 'what' | 'who' | 'when' | 'where' | 'why' | 'how' | 'which' | 'yes_no';
}

export interface QueryRewrite {
  original_query: string;
  rewritten_queries: Array<{
    query: string;
    strategy: 'expansion' | 'simplification' | 'temporal_adaptation' | 'domain_enhancement';
    confidence: number;
    reasoning: string;
  }>;
  expanded_terms: string[];
  removed_terms: string[];
  suggested_filters: Array<{
    type: 'modality' | 'date_range' | 'file_type' | 'entity';
    value: any;
    confidence: number;
  }>;
}

export interface HybridSearchConfig {
  vector_search: {
    enabled: boolean;
    weight: number;
    similarity_threshold: number;
    max_results: number;
  };
  graph_search: {
    enabled: boolean;
    weight: number;
    max_depth: number;
    relationship_types: string[];
  };
  keyword_search: {
    enabled: boolean;
    weight: number;
    fuzzy_threshold: number;
    max_results: number;
  };
  fusion_strategy: 'rrf' | 'weighted_average' | 'condorcet' | 'rank_biased';
  max_total_results: number;
}

export interface SearchStageResult {
  stage: 'vector' | 'graph' | 'keyword';
  results: any[];
  latency_ms: number;
  confidence_score: number;
  error?: string;
  metadata: Record<string, any>;
}

export interface ResultAggregation {
  final_results: any[];
  source_breakdown: {
    vector: number;
    graph: number;
    keyword: number;
    fused: number;
  };
  deduplication_stats: {
    initial_count: number;
    final_count: number;
    duplicates_removed: number;
  };
  aggregation_confidence: number;
  diversity_score: number;
  coverage_score: number;
  fusion_method: string;
}

export interface QueryPerformanceMetrics {
  total_latency_ms: number;
  stage_latencies: {
    intent_detection: number;
    query_rewriting: number;
    vector_search: number;
    graph_search: number;
    keyword_search: number;
    result_aggregation: number;
  };
  resource_usage: {
    memory_mb: number;
    cpu_percent: number;
    network_requests: number;
  };
  quality_metrics: {
    rag_triad_compliance: {
      answer_relevancy: number;
      faithfulness: number;
      contextual_relevancy: number;
    };
    hallucination_risk: number;
    confidence_score: number;
  };
  cache_performance: {
    cache_hit_rate: number;
    cache_misses: number;
    cache_hits: number;
  };
  bottlenecks: Array<{
    stage: string;
    issue: string;
    impact: 'low' | 'medium' | 'high';
    suggestion: string;
  }>;
}

export interface QueryProcessingState {
  current_stage: 'intent_detection' | 'query_rewriting' | 'search_execution' | 'result_aggregation' | 'completed' | 'failed';
  progress: number; // 0-100
  intent?: QueryIntent;
  rewrite?: QueryRewrite;
  search_results: SearchStageResult[];
  aggregation?: ResultAggregation;
  performance?: QueryPerformanceMetrics;
  error?: string;
  start_time: string;
  estimated_completion?: string;
}

export interface EnhancedSearchRequest extends SearchRequest {
  processing_config?: {
    enable_intent_detection: boolean;
    enable_query_rewriting: boolean;
    enable_hybrid_search: boolean;
    hybrid_config?: HybridSearchConfig;
    performance_monitoring: boolean;
  };
  user_context?: {
    previous_queries: string[];
    preferred_modalities: ('text' | 'image' | 'audio' | 'video')[];
    domain_expertise: string[];
  };
}

// WebSocket Message Types for Query Processing
export interface QueryProcessingUpdate {
  type: 'stage_started' | 'stage_progress' | 'stage_completed' | 'error' | 'completed';
  session_id: string;
  stage: string;
  progress: number;
  data?: any;
  error?: string;
  timestamp: string;
}

export interface QueryProcessingSession {
  session_id: string;
  query: string;
  state: QueryProcessingState;
  created_at: string;
  updated_at: string;
}

// Knowledge Graph Types
export interface GraphData {
  nodes: Entity[];
  edges: Relationship[];
  layout: 'force' | 'hierarchical' | 'circular';
  filters: GraphFilters;
}

export interface GraphFilters {
  entity_types?: Entity['type'][];
  min_confidence?: number;
  date_range?: {
    start: string;
    end: string;
  };
  document_ids?: string[];
}
