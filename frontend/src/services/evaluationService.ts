import { EvaluationMetrics } from '@/types/evaluation';

// Types for API requests/responses
export interface EvaluationDataset {
  id: string;
  name: string;
  description?: string;
  file_count: number;
  query_count: number;
  created_at: string;
  updated_at: string;
}

export interface EvaluationTemplate {
  id: string;
  name: string;
  description: string;
  evaluation_type: 'rag_triad' | 'performance' | 'quality' | 'comprehensive';
  config: {
    metrics: string[];
    thresholds: Record<string, number>;
    sample_size?: number;
  };
  created_at: string;
}

export interface EvaluationSchedule {
  id: string;
  evaluation_id: string;
  schedule_type: 'interval' | 'cron';
  schedule_config: {
    interval_minutes?: number;
    cron_expression?: string;
    timezone?: string;
  };
  enabled: boolean;
  last_run?: string;
  next_run?: string;
  created_at: string;
}

export interface EvaluationBatch {
  id: string;
  name: string;
  evaluations: string[];
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number;
  started_at?: string;
  completed_at?: string;
  results?: Array<{
    evaluation_id: string;
    run_id: string;
    metrics: EvaluationMetrics[];
  }>;
}

export interface EvaluationAlert {
  id: string;
  name: string;
  description?: string;
  evaluation_id: string;
  conditions: Array<{
    metric: string;
    operator: 'gt' | 'lt' | 'eq' | 'gte' | 'lte';
    threshold: number;
  }>;
  enabled: boolean;
  notification_channels: string[];
  last_triggered?: string;
  created_at: string;
}

// Base API configuration
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const DEFAULT_HEADERS = {
  'Content-Type': 'application/json',
};

// Helper function for API requests
async function apiRequest<T>(
  url: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await fetch(url, {
    ...options,
    headers: {
      ...DEFAULT_HEADERS,
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.message || `HTTP error! status: ${response.status}`);
  }

  return response.json();
}

// Dataset Management
export const datasetService = {
  // Get all datasets
  getDatasets: (): Promise<EvaluationDataset[]> =>
    apiRequest(`${API_BASE_URL}/evaluations/datasets`),

  // Get single dataset
  getDataset: (id: string): Promise<EvaluationDataset> =>
    apiRequest(`${API_BASE_URL}/evaluations/datasets/${id}`),

  // Create dataset
  createDataset: (data: {
    name: string;
    description?: string;
    files: File[];
  }): Promise<EvaluationDataset> => {
    const formData = new FormData();
    formData.append('name', data.name);
    if (data.description) formData.append('description', data.description);
    data.files.forEach((file) => formData.append('files', file));

    return fetch(`${API_BASE_URL}/evaluations/datasets`, {
      method: 'POST',
      body: formData,
    }).then((res) => {
      if (!res.ok) throw new Error('Failed to create dataset');
      return res.json();
    });
  },

  // Update dataset
  updateDataset: (
    id: string,
    data: Partial<EvaluationDataset>
  ): Promise<EvaluationDataset> =>
    apiRequest(`${API_BASE_URL}/evaluations/datasets/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  // Delete dataset
  deleteDataset: (id: string): Promise<void> =>
    apiRequest(`${API_BASE_URL}/evaluations/datasets/${id}`, {
      method: 'DELETE',
    }),

  // Validate dataset
  validateDataset: (
    id: string
  ): Promise<{
    is_valid: boolean;
    errors: string[];
    warnings: string[];
    sample_queries: string[];
  }> => apiRequest(`${API_BASE_URL}/evaluations/datasets/${id}/validate`),
};

// Template Management
export const templateService = {
  // Get all templates
  getTemplates: (): Promise<EvaluationTemplate[]> =>
    apiRequest(`${API_BASE_URL}/evaluations/templates`),

  // Get single template
  getTemplate: (id: string): Promise<EvaluationTemplate> =>
    apiRequest(`${API_BASE_URL}/evaluations/templates/${id}`),

  // Create template
  createTemplate: (
    data: Omit<EvaluationTemplate, 'id' | 'created_at'>
  ): Promise<EvaluationTemplate> =>
    apiRequest(`${API_BASE_URL}/evaluations/templates`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // Update template
  updateTemplate: (
    id: string,
    data: Partial<EvaluationTemplate>
  ): Promise<EvaluationTemplate> =>
    apiRequest(`${API_BASE_URL}/evaluations/templates/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  // Delete template
  deleteTemplate: (id: string): Promise<void> =>
    apiRequest(`${API_BASE_URL}/evaluations/templates/${id}`, {
      method: 'DELETE',
    }),

  // Clone template
  cloneTemplate: (id: string, name: string): Promise<EvaluationTemplate> =>
    apiRequest(`${API_BASE_URL}/evaluations/templates/${id}/clone`, {
      method: 'POST',
      body: JSON.stringify({ name }),
    }),
};

// Evaluation Scheduling
export const scheduleService = {
  // Get all schedules
  getSchedules: (): Promise<EvaluationSchedule[]> =>
    apiRequest(`${API_BASE_URL}/evaluations/schedules`),

  // Get schedules for evaluation
  getEvaluationSchedules: (
    evaluationId: string
  ): Promise<EvaluationSchedule[]> =>
    apiRequest(`${API_BASE_URL}/evaluations/${evaluationId}/schedules`),

  // Create schedule
  createSchedule: (
    data: Omit<
      EvaluationSchedule,
      'id' | 'created_at' | 'last_run' | 'next_run'
    >
  ): Promise<EvaluationSchedule> =>
    apiRequest(`${API_BASE_URL}/evaluations/schedules`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // Update schedule
  updateSchedule: (
    id: string,
    data: Partial<EvaluationSchedule>
  ): Promise<EvaluationSchedule> =>
    apiRequest(`${API_BASE_URL}/evaluations/schedules/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  // Delete schedule
  deleteSchedule: (id: string): Promise<void> =>
    apiRequest(`${API_BASE_URL}/evaluations/schedules/${id}`, {
      method: 'DELETE',
    }),

  // Enable/disable schedule
  toggleSchedule: (id: string, enabled: boolean): Promise<EvaluationSchedule> =>
    apiRequest(`${API_BASE_URL}/evaluations/schedules/${id}/toggle`, {
      method: 'POST',
      body: JSON.stringify({ enabled }),
    }),

  // Run schedule manually
  runScheduleManually: (id: string): Promise<{ run_id: string }> =>
    apiRequest(`${API_BASE_URL}/evaluations/schedules/${id}/run`, {
      method: 'POST',
    }),
};

// Batch Evaluation Management
export const batchService = {
  // Get all batches
  getBatches: (): Promise<EvaluationBatch[]> =>
    apiRequest(`${API_BASE_URL}/evaluations/batches`),

  // Get single batch
  getBatch: (id: string): Promise<EvaluationBatch> =>
    apiRequest(`${API_BASE_URL}/evaluations/batches/${id}`),

  // Create batch
  createBatch: (data: {
    name: string;
    evaluations: string[];
  }): Promise<EvaluationBatch> =>
    apiRequest(`${API_BASE_URL}/evaluations/batches`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // Run batch
  runBatch: (id: string): Promise<EvaluationBatch> =>
    apiRequest(`${API_BASE_URL}/evaluations/batches/${id}/run`, {
      method: 'POST',
    }),

  // Cancel batch
  cancelBatch: (id: string): Promise<EvaluationBatch> =>
    apiRequest(`${API_BASE_URL}/evaluations/batches/${id}/cancel`, {
      method: 'POST',
    }),

  // Get batch results
  getBatchResults: (id: string): Promise<EvaluationBatch['results']> =>
    apiRequest(`${API_BASE_URL}/evaluations/batches/${id}/results`),

  // Export batch results
  exportBatchResults: (
    id: string,
    format: 'csv' | 'json' | 'pdf'
  ): Promise<Blob> =>
    fetch(
      `${API_BASE_URL}/evaluations/batches/${id}/export?format=${format}`
    ).then((res) => {
      if (!res.ok) throw new Error('Failed to export batch results');
      return res.blob();
    }),
};

// Alert Management
export const alertService = {
  // Get all alerts
  getAlerts: (): Promise<EvaluationAlert[]> =>
    apiRequest(`${API_BASE_URL}/evaluations/alerts`),

  // Get alerts for evaluation
  getEvaluationAlerts: (evaluationId: string): Promise<EvaluationAlert[]> =>
    apiRequest(`${API_BASE_URL}/evaluations/${evaluationId}/alerts`),

  // Create alert
  createAlert: (
    data: Omit<EvaluationAlert, 'id' | 'created_at' | 'last_triggered'>
  ): Promise<EvaluationAlert> =>
    apiRequest(`${API_BASE_URL}/evaluations/alerts`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // Update alert
  updateAlert: (
    id: string,
    data: Partial<EvaluationAlert>
  ): Promise<EvaluationAlert> =>
    apiRequest(`${API_BASE_URL}/evaluations/alerts/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  // Delete alert
  deleteAlert: (id: string): Promise<void> =>
    apiRequest(`${API_BASE_URL}/evaluations/alerts/${id}`, {
      method: 'DELETE',
    }),

  // Test alert
  testAlert: (id: string): Promise<{ success: boolean; message: string }> =>
    apiRequest(`${API_BASE_URL}/evaluations/alerts/${id}/test`, {
      method: 'POST',
    }),

  // Get alert history
  getAlertHistory: (
    id: string,
    limit?: number
  ): Promise<
    Array<{
      id: string;
      triggered_at: string;
      metric: string;
      value: number;
      threshold: number;
      notification_sent: boolean;
    }>
  > =>
    apiRequest(
      `${API_BASE_URL}/evaluations/alerts/${id}/history${limit ? `?limit=${limit}` : ''}`
    ),
};

// Metrics and Analytics
export const metricsService = {
  // Get RAG Triad metrics
  getRAGTriadMetrics: (filters: {
    evaluation_id?: string;
    time_range?: { start: string; end: string };
    granularity?: 'hour' | 'day' | 'week';
  }): Promise<{
    answer_relevancy: Array<{ timestamp: string; value: number }>;
    faithfulness: Array<{ timestamp: string; value: number }>;
    contextual_relevancy: Array<{ timestamp: string; value: number }>;
  }> =>
    apiRequest(`${API_BASE_URL}/evaluations/metrics/rag-triad`, {
      method: 'POST',
      body: JSON.stringify(filters),
    }),

  // Get performance metrics
  getPerformanceMetrics: (filters: {
    evaluation_id?: string;
    time_range?: { start: string; end: string };
    granularity?: 'hour' | 'day' | 'week';
  }): Promise<{
    latency: Array<{ timestamp: string; value: number }>;
    throughput: Array<{ timestamp: string; value: number }>;
    error_rate: Array<{ timestamp: string; value: number }>;
    cache_hit_rate: Array<{ timestamp: string; value: number }>;
  }> =>
    apiRequest(`${API_BASE_URL}/evaluations/metrics/performance`, {
      method: 'POST',
      body: JSON.stringify(filters),
    }),

  // Get quality metrics
  getQualityMetrics: (filters: {
    evaluation_id?: string;
    time_range?: { start: string; end: string };
    granularity?: 'hour' | 'day' | 'week';
  }): Promise<{
    hallucination_score: Array<{ timestamp: string; value: number }>;
    factual_accuracy: Array<{ timestamp: string; value: number }>;
    coherence_score: Array<{ timestamp: string; value: number }>;
  }> =>
    apiRequest(`${API_BASE_URL}/evaluations/metrics/quality`, {
      method: 'POST',
      body: JSON.stringify(filters),
    }),

  // Get real-time metrics
  getRealTimeMetrics: (): Promise<{
    timestamp: string;
    rag_triad: {
      answer_relevancy: number;
      faithfulness: number;
      contextual_relevancy: number;
    };
    performance: {
      latency_ms: number;
      throughput_qpm: number;
      error_rate: number;
      cpu_usage: number;
      memory_usage: number;
    };
    system: {
      active_evaluations: number;
      queued_jobs: number;
    };
  }> => apiRequest(`${API_BASE_URL}/evaluations/metrics/realtime`),

  // Get metrics summary
  getMetricsSummary: (
    evaluationId: string
  ): Promise<{
    total_queries: number;
    average_scores: {
      answer_relevancy: number;
      faithfulness: number;
      contextual_relevancy: number;
    };
    performance_summary: {
      average_latency: number;
      p95_latency: number;
      throughput: number;
    };
    quality_summary: {
      average_hallucination_score: number;
      factuality_rate: number;
    };
    trends: {
      answer_relevancy: 'improving' | 'declining' | 'stable';
      faithfulness: 'improving' | 'declining' | 'stable';
      contextual_relevancy: 'improving' | 'declining' | 'stable';
    };
  }> =>
    apiRequest(`${API_BASE_URL}/evaluations/${evaluationId}/metrics/summary`),
};

// Export and Reporting
export const exportService = {
  // Export evaluation results
  exportEvaluationResults: (
    evaluationId: string,
    runId: string,
    format: 'csv' | 'json' | 'pdf',
    options?: {
      include_raw_data?: boolean;
      include_charts?: boolean;
      sections?: string[];
    }
  ): Promise<Blob> => {
    const params = new URLSearchParams({ format });
    if (options?.include_raw_data) params.append('include_raw_data', 'true');
    if (options?.include_charts) params.append('include_charts', 'true');
    if (options?.sections)
      params.append('sections', options.sections.join(','));

    return fetch(
      `${API_BASE_URL}/evaluations/${evaluationId}/runs/${runId}/export?${params}`
    ).then((res) => {
      if (!res.ok) throw new Error('Failed to export results');
      return res.blob();
    });
  },

  // Generate evaluation report
  generateReport: (
    evaluationId: string,
    runId: string,
    template: 'standard' | 'detailed' | 'executive'
  ): Promise<Blob> =>
    fetch(
      `${API_BASE_URL}/evaluations/${evaluationId}/runs/${runId}/report?template=${template}`
    ).then((res) => {
      if (!res.ok) throw new Error('Failed to generate report');
      return res.blob();
    }),

  // Get export history
  getExportHistory: (
    evaluationId?: string
  ): Promise<
    Array<{
      id: string;
      type: 'evaluation' | 'batch' | 'comparison';
      format: string;
      created_at: string;
      file_size: number;
      download_url: string;
      expires_at: string;
    }>
  > =>
    apiRequest(
      `${API_BASE_URL}/evaluations/exports/history${evaluationId ? `?evaluation_id=${evaluationId}` : ''}`
    ),

  // Download exported file
  downloadExport: (exportId: string): Promise<Blob> =>
    fetch(`${API_BASE_URL}/evaluations/exports/${exportId}/download`).then(
      (res) => {
        if (!res.ok) throw new Error('Failed to download export');
        return res.blob();
      }
    ),
};

// WebSocket connection for real-time updates
export class EvaluationWebSocket {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private listeners: Map<string, Array<(payload: any) => void>> = new Map();

  constructor(private url: string) {}

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(this.url);

        this.ws.onopen = () => {
          this.reconnectAttempts = 0;
          console.log('Evaluation WebSocket connected');
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
          } catch (error) {
            console.error('Error parsing WebSocket message:', error);
          }
        };

        this.ws.onclose = () => {
          console.log('Evaluation WebSocket disconnected');
          this.handleReconnect();
        };

        this.ws.onerror = (error) => {
          console.error('Evaluation WebSocket error:', error);
          reject(error);
        };
      } catch (error) {
        reject(error);
      }
    });
  }

  private handleMessage(data: any) {
    const { type, payload } = data;
    const listeners = this.listeners.get(type) || [];
    listeners.forEach((listener) => listener(payload));
  }

  private handleReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      setTimeout(
        () => {
          this.reconnectAttempts++;
          console.log(
            `Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})`
          );
          this.connect().catch(console.error);
        },
        this.reconnectDelay * Math.pow(2, this.reconnectAttempts)
      );
    }
  }

  subscribe(type: string, listener: (payload: any) => void) {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, []);
    }
    this.listeners.get(type)!.push(listener);
  }

  unsubscribe(type: string, listener: (payload: any) => void) {
    const listeners = this.listeners.get(type);
    if (listeners) {
      const index = listeners.indexOf(listener);
      if (index > -1) {
        listeners.splice(index, 1);
      }
    }
  }

  send(data: any) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

// Create WebSocket instance
export const evaluationWebSocket = new EvaluationWebSocket(
  `${process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000'}/ws/evaluations`
);

// Main evaluation service export
export const evaluationService = {
  datasets: datasetService,
  templates: templateService,
  schedules: scheduleService,
  batches: batchService,
  alerts: alertService,
  metrics: metricsService,
  exports: exportService,
  websocket: evaluationWebSocket,
};

export default evaluationService;
