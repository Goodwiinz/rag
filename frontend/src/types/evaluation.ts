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

export interface UserFeedback {
  query_id: string;
  helpfulness: number; // 1-5
  accuracy: number; // 1-5
  completeness: number; // 1-5
  comment?: string;
}

export interface Evaluation {
  id: string;
  name: string;
  description?: string;
  evaluation_type: 'offline' | 'online' | 'ab_test' | 'manual';
  created_at: string;
  updated_at: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'draft';
  last_run?: {
    started_at: string;
    results_summary?: {
      average_score: number;
      pass_rate: number;
    };
  };
}

export interface EvaluationConfig {
  dataset_id?: string;
  metrics: string[];
  thresholds: Record<string, number>;
  sample_size?: number;
  parallel_execution?: boolean;
  timeout_seconds?: number;
}

export interface EvaluationResults {
  id: string;
  evaluation_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  started_at: string;
  completed_at?: string;
  metrics: Record<string, number>;
  details?: any;
}

export interface ComparisonData {
  evaluations: Evaluation[];
  comparison_metrics: Record<string, number[]>;
  winner?: string;
}
