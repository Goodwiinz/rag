/**
 * Diagnostics Service for RAG retrieval pipeline instrumentation.
 * Communicates with backend /api/v1/diagnostics/* endpoints.
 */

import { api } from '@/services/api-client';

// --- Types ---

export interface SourceDiagnostics {
  source_type: string;
  search_time_ms: number;
  result_count: number;
  total_available: number;
  success: boolean;
  error: string | null;
  top_scores: number[];
  avg_score: number;
}

export interface FusionDiagnostics {
  input_count: number;
  output_count: number;
  multi_source_count: number;
  weights_used: Record<string, number>;
  score_distribution: Record<string, number>;
  fusion_time_ms: number;
}

export interface RerankDiagnostics {
  enabled: boolean;
  rerank_time_ms: number;
  input_count: number;
  output_count: number;
  score_deltas: Array<{
    doc_id: string;
    before: number;
    after: number;
    delta: number;
  }>;
  fallback_used: boolean;
  error: string | null;
}

export interface ContextDiagnostics {
  docs_retrieved: number;
  docs_with_content: number;
  total_chars_before_truncation: number;
  total_chars_after_truncation: number;
  truncated_docs: Array<{ doc_id: string; before: number; after: number }>;
  truncation_ratio: number;
  char_limit: number;
}

export interface RetrievalTrace {
  trace_id: string;
  query: string;
  timestamp: string;
  total_time_ms: number;
  sources: SourceDiagnostics[];
  fusion: FusionDiagnostics | null;
  rerank: RerankDiagnostics | null;
  context: ContextDiagnostics | null;
  final_result_count: number;
  search_type: string;
  evaluation_id: string | null;
  evaluation_scores: Record<string, number> | null;
}

export interface Finding {
  stage: string;
  severity: 'high' | 'medium' | 'low';
  title: string;
  detail: string;
  recommendation: string;
}

export interface BottleneckReport {
  trace_id: string;
  findings: Finding[];
  stage_health: Record<string, 'green' | 'yellow' | 'red'>;
  overall_health: 'green' | 'yellow' | 'red';
}

export interface TraceSummary {
  trace_id: string;
  query: string;
  timestamp: string;
  total_time_ms: number;
  final_result_count: number;
  search_type: string;
  source_count: number;
  has_evaluation: boolean;
}

export interface AggregateStats {
  period_hours: number;
  total_traces: number;
  avg_time_ms: number;
  avg_result_count: number;
  source_stats: Record<
    string,
    { avg_time_ms: number; max_time_ms: number; query_count: number }
  >;
  source_failure_count: number;
  truncation_stats: {
    avg_ratio: number;
    max_ratio: number;
    traces_with_truncation: number;
  };
  error?: string;
}

export interface WeightConfig {
  fulltext: number;
  vector: number;
  knowledge_graph: number;
}

export interface WeightExperimentResult {
  weights: WeightConfig;
  result_count: number;
  top_scores: number[];
  trace_id: string;
  total_time_ms: number;
}

// --- Service ---

const API_PREFIX = '';

export const diagnosticsService = {
  async getTrace(
    traceId: string
  ): Promise<{ trace: RetrievalTrace; bottleneck_report: BottleneckReport }> {
    return api.get(`${API_PREFIX}/diagnostics/traces/${traceId}`);
  },

  async getRecentTraces(
    limit = 50,
    offset = 0
  ): Promise<{ traces: TraceSummary[]; count: number }> {
    const params = new URLSearchParams();
    params.append('limit', limit.toString());
    params.append('offset', offset.toString());
    return api.get(`${API_PREFIX}/diagnostics/traces?${params.toString()}`);
  },

  async getAggregateStats(hours = 24): Promise<AggregateStats> {
    return api.get(`${API_PREFIX}/diagnostics/aggregate?hours=${hours}`);
  },

  async experimentWeights(
    query: string,
    configurations: WeightConfig[],
    maxDocs = 5
  ): Promise<{ query: string; results: WeightExperimentResult[] }> {
    return api.post(`${API_PREFIX}/diagnostics/weight-experiment`, {
      query,
      max_docs: maxDocs,
      configurations,
    });
  },
};
