/**
 * Diagnostics Service for RAG retrieval pipeline instrumentation.
 * Communicates with backend /api/v1/diagnostics/* endpoints.
 */

import axios, { AxiosInstance } from 'axios';

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

// --- Client setup ---

const API_PREFIX = '/api/v1';

const getAuthContext = (): {
  token: string | null;
  organizationId: string | null;
} => {
  if (typeof window === 'undefined') {
    return { token: null, organizationId: null };
  }
  try {
    const authStorage = localStorage.getItem('auth-storage');
    if (authStorage) {
      const auth = JSON.parse(authStorage);
      return {
        token: auth.state?.token || null,
        organizationId:
          auth.state?.organization?.id ||
          auth.state?.user?.organization_id ||
          null,
      };
    }
  } catch {
    // Fall through
  }
  return { token: null, organizationId: null };
};

const diagClient: AxiosInstance = axios.create({
  baseURL: '',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

diagClient.interceptors.request.use((config) => {
  if (typeof window === 'undefined') return config;
  const { token, organizationId } = getAuthContext();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  if (organizationId) config.headers['X-Organization-ID'] = organizationId;
  return config;
});

// --- Service ---

export const diagnosticsService = {
  async getTrace(
    traceId: string
  ): Promise<{ trace: RetrievalTrace; bottleneck_report: BottleneckReport }> {
    const response = await diagClient.get(
      `${API_PREFIX}/diagnostics/traces/${traceId}`
    );
    return response.data;
  },

  async getRecentTraces(
    limit = 50,
    offset = 0
  ): Promise<{ traces: TraceSummary[]; count: number }> {
    const response = await diagClient.get(`${API_PREFIX}/diagnostics/traces`, {
      params: { limit, offset },
    });
    return response.data;
  },

  async getAggregateStats(hours = 24): Promise<AggregateStats> {
    const response = await diagClient.get(
      `${API_PREFIX}/diagnostics/aggregate`,
      { params: { hours } }
    );
    return response.data;
  },

  async experimentWeights(
    query: string,
    configurations: WeightConfig[],
    maxDocs = 5
  ): Promise<{ query: string; results: WeightExperimentResult[] }> {
    const response = await diagClient.post(
      `${API_PREFIX}/diagnostics/weight-experiment`,
      {
        query,
        max_docs: maxDocs,
        configurations,
      }
    );
    return response.data;
  },
};
