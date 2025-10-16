// Evaluation and Analytics Types
export interface EvaluationMetrics {
  query_id: string;
  rag_triad: {
    answer_relevancy: number; // 0-100
    faithfulness: number; // 0-100
    contextual_relevancy: number; // 0-100
  };
  performance: {
    latency_ms: number;
    documents_processed: number;
    tokens_processed: number;
    cache_hit_rate: number;
  };
  quality: {
    hallucination_score: number; // 0-100
    factual_accuracy: number; // 0-100
    coherence_score: number; // 0-100
  };
  user_feedback?: {
    helpfulness: number; // 1-5
    accuracy: number; // 1-5
    completeness: number; // 1-5
    comment?: string;
  };
  created_at: string;
}

export interface PerformanceAnalytics {
  time_range: {
    start: string;
    end: string;
  };
  total_queries: number;
  average_latency_ms: number;
  success_rate: number;
  quality_scores: {
    answer_relevancy_avg: number;
    faithfulness_avg: number;
    contextual_relevancy_avg: number;
  };
  modalities_processed: Record<string, number>;
  error_rates: Record<string, number>;
  user_satisfaction: {
    average_rating: number;
    total_feedback: number;
  };
}

export interface UsageAnalytics {
  user_id: string;
  time_range: {
    start: string;
    end: string;
  };
  documents_uploaded: number;
  queries_performed: number;
  storage_used_mb: number;
  processing_time_total_ms: number;
  top_queries: Array<{
    query: string;
    frequency: number;
  }>;
  file_type_distribution: Record<import('./document').Document['file_type'], number>;
  search_patterns: {
    average_query_length: number;
    peak_usage_hours: number[];
    session_duration_avg_ms: number;
  };
}

export interface UserFeedback {
  query_id: string;
  helpfulness: number; // 1-5
  accuracy: number; // 1-5
  completeness: number; // 1-5
  comment?: string;
}

