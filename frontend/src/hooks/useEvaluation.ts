import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  EvaluationMetrics,
  Evaluation,
  EvaluationConfig
} from '@/types/evaluation';
import {
  PerformanceAnalytics,
  UsageAnalytics
} from '@/types/analytics';

// API Types
interface CreateEvaluationRequest {
  name: string;
  description?: string;
  dataset_id: string;
  evaluation_type: 'rag_triad' | 'performance' | 'quality' | 'comprehensive';
  config: {
    metrics: string[];
    thresholds?: Record<string, number>;
    sample_size?: number;
  };
}

interface EvaluationRun {
  id: string;
  evaluation_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  started_at: string;
  completed_at?: string;
  progress: number;
  results?: EvaluationMetrics[];
  error?: string;
}

interface EvaluationComparison {
  id: string;
  name: string;
  evaluations: string[];
  created_at: string;
  results: {
    evaluation_id: string;
    metrics: EvaluationMetrics[];
    summary: {
      average_score: number;
      best_metric: string;
      worst_metric: string;
    };
  }[];
}

// Base API URL
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// API client functions
const evaluationApi = {
  // Evaluations
  getEvaluations: async (): Promise<Evaluation[]> => {
    const response = await fetch(`${API_BASE_URL}/api/v1/evaluations`);
    if (!response.ok) throw new Error('Failed to fetch evaluations');
    return response.json();
  },

  getEvaluation: async (id: string): Promise<Evaluation> => {
    const response = await fetch(`${API_BASE_URL}/api/v1/evaluations/${id}`);
    if (!response.ok) throw new Error('Failed to fetch evaluation');
    return response.json();
  },

  createEvaluation: async (data: CreateEvaluationRequest): Promise<Evaluation> => {
    const response = await fetch(`${API_BASE_URL}/api/v1/evaluations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error('Failed to create evaluation');
    return response.json();
  },

  updateEvaluation: async (id: string, data: Partial<Evaluation>): Promise<Evaluation> => {
    const response = await fetch(`${API_BASE_URL}/api/v1/evaluations/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error('Failed to update evaluation');
    return response.json();
  },

  deleteEvaluation: async (id: string): Promise<void> => {
    const response = await fetch(`${API_BASE_URL}/api/v1/evaluations/${id}`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error('Failed to delete evaluation');
  },

  // Evaluation Runs
  runEvaluation: async (evaluationId: string): Promise<EvaluationRun> => {
    const response = await fetch(`${API_BASE_URL}/api/v1/evaluations/${evaluationId}/run`, {
      method: 'POST',
    });
    if (!response.ok) throw new Error('Failed to run evaluation');
    return response.json();
  },

  getEvaluationRuns: async (evaluationId: string): Promise<EvaluationRun[]> => {
    const response = await fetch(`${API_BASE_URL}/api/v1/evaluations/${evaluationId}/runs`);
    if (!response.ok) throw new Error('Failed to fetch evaluation runs');
    return response.json();
  },

  getEvaluationRun: async (evaluationId: string, runId: string): Promise<EvaluationRun> => {
    const response = await fetch(`${API_BASE_URL}/api/v1/evaluations/${evaluationId}/runs/${runId}`);
    if (!response.ok) throw new Error('Failed to fetch evaluation run');
    return response.json();
  },

  // Evaluation Results
  getEvaluationResults: async (evaluationId: string, runId: string): Promise<EvaluationMetrics[]> => {
    const response = await fetch(`${API_BASE_URL}/api/v1/evaluations/${evaluationId}/runs/${runId}/results`);
    if (!response.ok) throw new Error('Failed to fetch evaluation results');
    return response.json();
  },

  exportEvaluationResults: async (evaluationId: string, runId: string, format: 'csv' | 'json' | 'pdf'): Promise<Blob> => {
    const response = await fetch(`${API_BASE_URL}/api/v1/evaluations/${evaluationId}/runs/${runId}/export?format=${format}`);
    if (!response.ok) throw new Error('Failed to export evaluation results');
    return response.blob();
  },

  // Comparisons
  createComparison: async (data: { name: string; evaluations: string[] }): Promise<EvaluationComparison> => {
    const response = await fetch(`${API_BASE_URL}/api/v1/evaluations/comparisons`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error('Failed to create comparison');
    return response.json();
  },

  getComparisons: async (): Promise<EvaluationComparison[]> => {
    const response = await fetch(`${API_BASE_URL}/api/v1/evaluations/comparisons`);
    if (!response.ok) throw new Error('Failed to fetch comparisons');
    return response.json();
  },

  getComparison: async (id: string): Promise<EvaluationComparison> => {
    const response = await fetch(`${API_BASE_URL}/api/v1/evaluations/comparisons/${id}`);
    if (!response.ok) throw new Error('Failed to fetch comparison');
    return response.json();
  },
};

// Hooks

// Get all evaluations
export const useEvaluations = () => {
  return useQuery({
    queryKey: ['evaluations'],
    queryFn: evaluationApi.getEvaluations,
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes (renamed from cacheTime in v5)
  });
};

// Get single evaluation
export const useEvaluation = (id: string) => {
  return useQuery({
    queryKey: ['evaluation', id],
    queryFn: () => evaluationApi.getEvaluation(id),
    enabled: !!id,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });
};

// Create evaluation
export const useCreateEvaluation = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: evaluationApi.createEvaluation,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['evaluations'] });
    },
  });
};

// Update evaluation
export const useUpdateEvaluation = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Evaluation> }) =>
      evaluationApi.updateEvaluation(id, data),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['evaluations'] });
      queryClient.invalidateQueries({ queryKey: ['evaluation', id] });
    },
  });
};

// Delete evaluation
export const useDeleteEvaluation = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: evaluationApi.deleteEvaluation,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['evaluations'] });
    },
  });
};

// Run evaluation
export const useRunEvaluation = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (evaluationId: string) => evaluationApi.runEvaluation(evaluationId),
    onSuccess: (_, evaluationId) => {
      queryClient.invalidateQueries({ queryKey: ['evaluations'] });
      queryClient.invalidateQueries({ queryKey: ['evaluation', evaluationId] });
      queryClient.invalidateQueries({ queryKey: ['evaluation-runs', evaluationId] });
    },
  });
};

// Get evaluation runs
export const useEvaluationRuns = (evaluationId: string) => {
  return useQuery({
    queryKey: ['evaluation-runs', evaluationId],
    queryFn: () => evaluationApi.getEvaluationRuns(evaluationId),
    enabled: !!evaluationId,
    staleTime: 30 * 1000, // 30 seconds
    gcTime: 5 * 60 * 1000, // 5 minutes
    refetchInterval: 30 * 1000, // 30 seconds for real-time updates
  });
};

// Get single evaluation run
export const useEvaluationRun = (evaluationId: string, runId: string) => {
  return useQuery({
    queryKey: ['evaluation-run', evaluationId, runId],
    queryFn: () => evaluationApi.getEvaluationRun(evaluationId, runId),
    enabled: !!evaluationId && !!runId,
    staleTime: 30 * 1000,
    gcTime: 5 * 60 * 1000,
    refetchInterval: (query) => {
      // Refetch more frequently when running
      return query.state.data?.status === 'running' ? 5 * 1000 : 30 * 1000;
    },
  });
};

// Get evaluation results
export const useEvaluationResults = (evaluationId: string, runId: string) => {
  return useQuery({
    queryKey: ['evaluation-results', evaluationId, runId],
    queryFn: () => evaluationApi.getEvaluationResults(evaluationId, runId),
    enabled: !!evaluationId && !!runId,
    staleTime: 5 * 60 * 1000,
    gcTime: 15 * 60 * 1000,
    select: (data) => {
      // Process results for easier consumption
      return {
        raw: data,
        summary: calculateResultsSummary(data),
        ragTriadSummary: calculateRAGTriadSummary(data),
        performanceSummary: calculatePerformanceSummary(data),
        qualitySummary: calculateQualitySummary(data),
      };
    },
  });
};

// Export evaluation results
export const useExportEvaluationResults = () => {
  return useMutation({
    mutationFn: ({ evaluationId, runId, format }: {
      evaluationId: string;
      runId: string;
      format: 'csv' | 'json' | 'pdf';
    }) => evaluationApi.exportEvaluationResults(evaluationId, runId, format),
    onSuccess: (blob, { format }) => {
      // Create download link
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `evaluation-results.${format}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    },
  });
};

// Get comparisons
export const useComparisons = () => {
  return useQuery({
    queryKey: ['evaluation-comparisons'],
    queryFn: evaluationApi.getComparisons,
    staleTime: 5 * 60 * 1000,
    gcTime: 15 * 60 * 1000,
  });
};

// Get single comparison
export const useComparison = (id: string) => {
  return useQuery({
    queryKey: ['evaluation-comparison', id],
    queryFn: () => evaluationApi.getComparison(id),
    enabled: !!id,
    staleTime: 5 * 60 * 1000,
    gcTime: 15 * 60 * 1000,
    select: (data) => {
      return {
        ...data,
        chartData: formatComparisonData(data),
        insights: generateComparisonInsights(data),
      };
    },
  });
};

// Create comparison
export const useCreateComparison = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: evaluationApi.createComparison,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['evaluation-comparisons'] });
    },
  });
};

// Utility functions for data processing
const calculateResultsSummary = (results: EvaluationMetrics[]) => {
  if (results.length === 0) return null;

  const totalQueries = results.length;
  const avgAnswerRelevancy = results.reduce((sum, r) => sum + r.rag_triad.answer_relevancy, 0) / totalQueries;
  const avgFaithfulness = results.reduce((sum, r) => sum + r.rag_triad.faithfulness, 0) / totalQueries;
  const avgContextualRelevancy = results.reduce((sum, r) => sum + r.rag_triad.contextual_relevancy, 0) / totalQueries;
  const avgLatency = results.reduce((sum, r) => sum + r.performance.latency_ms, 0) / totalQueries;
  const avgHallucinationScore = results.reduce((sum, r) => sum + r.quality.hallucination_score, 0) / totalQueries;

  const passingAnswerRelevancy = results.filter(r => r.rag_triad.answer_relevancy >= 70).length;
  const passingFaithfulness = results.filter(r => r.rag_triad.faithfulness >= 90).length;
  const passingContextualRelevancy = results.filter(r => r.rag_triad.contextual_relevancy >= 70).length;

  return {
    totalQueries,
    ragTriad: {
      answerRelevancy: {
        average: Math.round(avgAnswerRelevancy * 100) / 100,
        passRate: Math.round((passingAnswerRelevancy / totalQueries) * 100),
      },
      faithfulness: {
        average: Math.round(avgFaithfulness * 100) / 100,
        passRate: Math.round((passingFaithfulness / totalQueries) * 100),
      },
      contextualRelevancy: {
        average: Math.round(avgContextualRelevancy * 100) / 100,
        passRate: Math.round((passingContextualRelevancy / totalQueries) * 100),
      },
    },
    performance: {
      averageLatency: Math.round(avgLatency),
    },
    quality: {
      averageHallucinationScore: Math.round(avgHallucinationScore * 100) / 100,
    },
  };
};

const calculateRAGTriadSummary = (results: EvaluationMetrics[]) => {
  if (results.length === 0) return null;

  const answerRelevancyScores = results.map(r => r.rag_triad.answer_relevancy);
  const faithfulnessScores = results.map(r => r.rag_triad.faithfulness);
  const contextualRelevancyScores = results.map(r => r.rag_triad.contextual_relevancy);

  return {
    answerRelevancy: {
      min: Math.min(...answerRelevancyScores),
      max: Math.max(...answerRelevancyScores),
      median: calculateMedian(answerRelevancyScores),
      p95: calculatePercentile(answerRelevancyScores, 95),
      distribution: calculateDistribution(answerRelevancyScores),
    },
    faithfulness: {
      min: Math.min(...faithfulnessScores),
      max: Math.max(...faithfulnessScores),
      median: calculateMedian(faithfulnessScores),
      p95: calculatePercentile(faithfulnessScores, 95),
      distribution: calculateDistribution(faithfulnessScores),
    },
    contextualRelevancy: {
      min: Math.min(...contextualRelevancyScores),
      max: Math.max(...contextualRelevancyScores),
      median: calculateMedian(contextualRelevancyScores),
      p95: calculatePercentile(contextualRelevancyScores, 95),
      distribution: calculateDistribution(contextualRelevancyScores),
    },
  };
};

const calculatePerformanceSummary = (results: EvaluationMetrics[]) => {
  if (results.length === 0) return null;

  const latencies = results.map(r => r.performance.latency_ms);
  const cacheHitRates = results.map(r => r.performance.cache_hit_rate);

  return {
    latency: {
      min: Math.min(...latencies),
      max: Math.max(...latencies),
      median: calculateMedian(latencies),
      p95: calculatePercentile(latencies, 95),
      p99: calculatePercentile(latencies, 99),
      average: latencies.reduce((a, b) => a + b, 0) / latencies.length,
    },
    cacheHitRate: {
      average: cacheHitRates.reduce((a, b) => a + b, 0) / cacheHitRates.length,
      min: Math.min(...cacheHitRates),
      max: Math.max(...cacheHitRates),
    },
  };
};

const calculateQualitySummary = (results: EvaluationMetrics[]) => {
  if (results.length === 0) return null;

  const hallucinationScores = results.map(r => r.quality.hallucination_score);
  const factualAccuracyScores = results.map(r => r.quality.factual_accuracy);
  const coherenceScores = results.map(r => r.quality.coherence_score);

  return {
    hallucinationScore: {
      average: hallucinationScores.reduce((a, b) => a + b, 0) / hallucinationScores.length,
      min: Math.min(...hallucinationScores),
      max: Math.max(...hallucinationScores),
      distribution: calculateDistribution(hallucinationScores),
    },
    factualAccuracy: {
      average: factualAccuracyScores.reduce((a, b) => a + b, 0) / factualAccuracyScores.length,
      min: Math.min(...factualAccuracyScores),
      max: Math.max(...factualAccuracyScores),
      distribution: calculateDistribution(factualAccuracyScores),
    },
    coherenceScore: {
      average: coherenceScores.reduce((a, b) => a + b, 0) / coherenceScores.length,
      min: Math.min(...coherenceScores),
      max: Math.max(...coherenceScores),
      distribution: calculateDistribution(coherenceScores),
    },
  };
};

const calculateMedian = (values: number[]): number => {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0
    ? ((sorted[mid - 1] ?? 0) + (sorted[mid] ?? 0)) / 2
    : sorted[mid] ?? 0;
};

const calculatePercentile = (values: number[], percentile: number): number => {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const index = Math.ceil((percentile / 100) * sorted.length) - 1;
  return sorted[Math.max(0, index)] ?? 0;
};

const calculateDistribution = (values: number[]): Array<{ range: string; count: number; percentage: number }> => {
  const ranges = [
    { min: 0, max: 50, label: '0-50' },
    { min: 50, max: 60, label: '50-60' },
    { min: 60, max: 70, label: '60-70' },
    { min: 70, max: 80, label: '70-80' },
    { min: 80, max: 90, label: '80-90' },
    { min: 90, max: 100, label: '90-100' },
  ];

  const total = values.length;
  return ranges.map(range => {
    const count = values.filter(v => v >= range.min && v < range.max).length;
    return {
      range: range.label,
      count,
      percentage: Math.round((count / total) * 100),
    };
  });
};

const formatComparisonData = (comparison: EvaluationComparison) => {
  return {
    labels: comparison.results.map(r => `Evaluation ${r.evaluation_id.slice(0, 8)}`),
    datasets: [
      {
        label: 'Average Answer Relevancy',
        data: comparison.results.map(r => r.summary.average_score),
        backgroundColor: 'rgba(75, 192, 192, 0.8)',
      },
    ],
  };
};

const generateComparisonInsights = (comparison: EvaluationComparison) => {
  const insights = [];
  const results = comparison.results;

  if (results.length > 1) {
    const best = results.reduce((best, current) =>
      current.summary.average_score > best.summary.average_score ? current : best
    );
    const worst = results.reduce((worst, current) =>
      current.summary.average_score < worst.summary.average_score ? current : worst
    );

    insights.push({
      type: 'performance',
      title: 'Best Performing Evaluation',
      description: `Evaluation ${best.evaluation_id.slice(0, 8)} achieved the highest average score of ${best.summary.average_score.toFixed(1)}%`,
    });

    insights.push({
      type: 'improvement',
      title: 'Improvement Opportunity',
      description: `There is a ${(best.summary.average_score - worst.summary.average_score).toFixed(1)}% difference between best and worst performing evaluations`,
    });
  }

  return insights;
};