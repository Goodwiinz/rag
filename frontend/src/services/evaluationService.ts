import { api } from '@/services/api-client';
import { EvaluationMetrics } from '@/types/evaluation';
import { getPublicWebSocketOrigin } from '@/utils/publicEndpoints';

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

const EVAL_BASE = '/evaluations';

// Dataset Management
export const datasetService = {
  // Get all datasets
  getDatasets: (): Promise<EvaluationDataset[]> =>
    api.get(`${EVAL_BASE}/datasets`),

  // Get single dataset
  getDataset: (id: string): Promise<EvaluationDataset> =>
    api.get(`${EVAL_BASE}/datasets/${id}`),

  // Create dataset
  createDataset: async (data: {
    name: string;
    description?: string;
    files: File[];
  }): Promise<EvaluationDataset> => {
    const formData = new FormData();
    formData.append('name', data.name);
    if (data.description) formData.append('description', data.description);
    data.files.forEach((file) => formData.append('files', file));

    return api.request<EvaluationDataset>(`${EVAL_BASE}/datasets`, {
      method: 'POST',
      body: formData,
    });
  },

  // Update dataset
  updateDataset: (
    id: string,
    data: Partial<EvaluationDataset>
  ): Promise<EvaluationDataset> =>
    api.put(`${EVAL_BASE}/datasets/${id}`, data),

  // Delete dataset
  deleteDataset: (id: string): Promise<void> =>
    api.delete(`${EVAL_BASE}/datasets/${id}`),

  // Validate dataset
  validateDataset: (
    id: string
  ): Promise<{
    is_valid: boolean;
    errors: string[];
    warnings: string[];
    sample_queries: string[];
  }> => api.get(`${EVAL_BASE}/datasets/${id}/validate`),
};

// Template Management
export const templateService = {
  // Get all templates
  getTemplates: (): Promise<EvaluationTemplate[]> =>
    api.get(`${EVAL_BASE}/templates`),

  // Get single template
  getTemplate: (id: string): Promise<EvaluationTemplate> =>
    api.get(`${EVAL_BASE}/templates/${id}`),

  // Create template
  createTemplate: (
    data: Omit<EvaluationTemplate, 'id' | 'created_at'>
  ): Promise<EvaluationTemplate> =>
    api.post(`${EVAL_BASE}/templates`, data),

  // Update template
  updateTemplate: (
    id: string,
    data: Partial<EvaluationTemplate>
  ): Promise<EvaluationTemplate> =>
    api.put(`${EVAL_BASE}/templates/${id}`, data),

  // Delete template
  deleteTemplate: (id: string): Promise<void> =>
    api.delete(`${EVAL_BASE}/templates/${id}`),

  // Clone template
  cloneTemplate: (id: string, name: string): Promise<EvaluationTemplate> =>
    api.post(`${EVAL_BASE}/templates/${id}/clone`, { name }),
};

// Evaluation Scheduling
export const scheduleService = {
  // Get all schedules
  getSchedules: (): Promise<EvaluationSchedule[]> =>
    api.get(`${EVAL_BASE}/schedules`),

  // Get schedules for evaluation
  getEvaluationSchedules: (
    evaluationId: string
  ): Promise<EvaluationSchedule[]> =>
    api.get(`${EVAL_BASE}/${evaluationId}/schedules`),

  // Create schedule
  createSchedule: (
    data: Omit<
      EvaluationSchedule,
      'id' | 'created_at' | 'last_run' | 'next_run'
    >
  ): Promise<EvaluationSchedule> =>
    api.post(`${EVAL_BASE}/schedules`, data),

  // Update schedule
  updateSchedule: (
    id: string,
    data: Partial<EvaluationSchedule>
  ): Promise<EvaluationSchedule> =>
    api.put(`${EVAL_BASE}/schedules/${id}`, data),

  // Delete schedule
  deleteSchedule: (id: string): Promise<void> =>
    api.delete(`${EVAL_BASE}/schedules/${id}`),

  // Enable/disable schedule
  toggleSchedule: (id: string, enabled: boolean): Promise<EvaluationSchedule> =>
    api.post(`${EVAL_BASE}/schedules/${id}/toggle`, { enabled }),

  // Run schedule manually
  runScheduleManually: (id: string): Promise<{ run_id: string }> =>
    api.post(`${EVAL_BASE}/schedules/${id}/run`),
};

// Batch Evaluation Management
export const batchService = {
  // Get all batches
  getBatches: (): Promise<EvaluationBatch[]> =>
    api.get(`${EVAL_BASE}/batches`),

  // Get single batch
  getBatch: (id: string): Promise<EvaluationBatch> =>
    api.get(`${EVAL_BASE}/batches/${id}`),

  // Create batch
  createBatch: (data: {
    name: string;
    evaluations: string[];
  }): Promise<EvaluationBatch> =>
    api.post(`${EVAL_BASE}/batches`, data),

  // Run batch
  runBatch: (id: string): Promise<EvaluationBatch> =>
    api.post(`${EVAL_BASE}/batches/${id}/run`),

  // Cancel batch
  cancelBatch: (id: string): Promise<EvaluationBatch> =>
    api.post(`${EVAL_BASE}/batches/${id}/cancel`),

  // Get batch results
  getBatchResults: (id: string): Promise<EvaluationBatch['results']> =>
    api.get(`${EVAL_BASE}/batches/${id}/results`),

  // Export batch results
  exportBatchResults: (
    id: string,
    format: 'csv' | 'json' | 'pdf'
  ): Promise<Blob> =>
    api.request(`${EVAL_BASE}/batches/${id}/export?format=${format}`, {
      method: 'GET',
    }),
};

// Alert Management
export const alertService = {
  // Get all alerts
  getAlerts: (): Promise<EvaluationAlert[]> =>
    api.get(`${EVAL_BASE}/alerts`),

  // Get alerts for evaluation
  getEvaluationAlerts: (evaluationId: string): Promise<EvaluationAlert[]> =>
    api.get(`${EVAL_BASE}/${evaluationId}/alerts`),

  // Create alert
  createAlert: (
    data: Omit<EvaluationAlert, 'id' | 'created_at' | 'last_triggered'>
  ): Promise<EvaluationAlert> =>
    api.post(`${EVAL_BASE}/alerts`, data),

  // Update alert
  updateAlert: (
    id: string,
    data: Partial<EvaluationAlert>
  ): Promise<EvaluationAlert> =>
    api.put(`${EVAL_BASE}/alerts/${id}`, data),

  // Delete alert
  deleteAlert: (id: string): Promise<void> =>
    api.delete(`${EVAL_BASE}/alerts/${id}`),

  // Test alert
  testAlert: (id: string): Promise<{ success: boolean; message: string }> =>
    api.post(`${EVAL_BASE}/alerts/${id}/test`),

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
    api.get(
      `${EVAL_BASE}/alerts/${id}/history${limit ? `?limit=${limit}` : ''}`
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
    api.post(`${EVAL_BASE}/metrics/rag-triad`, filters),

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
    api.post(`${EVAL_BASE}/metrics/performance`, filters),

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
    api.post(`${EVAL_BASE}/metrics/quality`, filters),

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
  }> => api.get(`${EVAL_BASE}/metrics/realtime`),

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
    api.get(`${EVAL_BASE}/${evaluationId}/metrics/summary`),
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

    return api.request(
      `${EVAL_BASE}/${evaluationId}/runs/${runId}/export?${params}`,
      { method: 'GET' }
    );
  },

  // Generate evaluation report
  generateReport: (
    evaluationId: string,
    runId: string,
    template: 'standard' | 'detailed' | 'executive'
  ): Promise<Blob> =>
    api.request(
      `${EVAL_BASE}/${evaluationId}/runs/${runId}/report?template=${template}`,
      { method: 'GET' }
    ),

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
    api.get(
      `${EVAL_BASE}/exports/history${evaluationId ? `?evaluation_id=${evaluationId}` : ''}`
    ),

  // Download exported file
  downloadExport: (exportId: string): Promise<Blob> =>
    api.request(`${EVAL_BASE}/exports/${exportId}/download`, {
      method: 'GET',
    }),
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
  `${getPublicWebSocketOrigin()}/ws/evaluations`
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
