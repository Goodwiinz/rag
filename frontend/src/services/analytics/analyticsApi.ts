import axios, { AxiosInstance, AxiosResponse } from 'axios';
import {
  AnalyticsMetric,
  TimeSeriesData,
  GraphData,
  Dashboard,
  Widget,
  Report,
  AlertRule,
} from '@/store/analytics';
import { getPublicApiOrigin } from '@/utils/publicEndpoints';

// API Configuration
const API_BASE_URL = getPublicApiOrigin() || 'http://localhost:8000';
const ANALYTICS_API_PREFIX = '/analytics';

// API Response Types
interface ApiResponse<T> {
  success: boolean;
  data: T;
  message?: string;
  pagination?: {
    page: number;
    limit: number;
    total: number;
    totalPages: number;
  };
}

interface ApiError {
  success: false;
  error: string;
  code?: string;
  details?: any;
}

// Request Configuration
interface RequestConfig {
  params?: Record<string, any>;
  headers?: Record<string, string>;
  timeout?: number;
}

// Create Axios Instance
const createApiClient = (): AxiosInstance => {
  const client = axios.create({
    baseURL: `${API_BASE_URL}${ANALYTICS_API_PREFIX}`,
    timeout: 30000,
    headers: {
      'Content-Type': 'application/json',
    },
  });

  // Request Interceptor
  client.interceptors.request.use(
    (config) => {
      // Add authentication token if available
      const token = localStorage.getItem('authToken');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }

      // Add request timestamp
      config.metadata = { startTime: new Date() };

      return config;
    },
    (error) => {
      return Promise.reject(error);
    }
  );

  // Response Interceptor
  client.interceptors.response.use(
    (response: AxiosResponse) => {
      // Log response time for monitoring
      const endTime = new Date();
      const duration = endTime.getTime() - response.config.metadata?.startTime?.getTime();

      console.log(`API Response: ${response.config.method?.toUpperCase()} ${response.config.url} - ${duration}ms`);

      return response;
    },
    (error) => {
      // Handle common error scenarios
      if (error.response?.status === 401) {
        // Unauthorized - redirect to login
        window.location.href = '/login';
      } else if (error.response?.status === 429) {
        // Rate limited
        console.warn('API rate limit exceeded');
      }

      return Promise.reject(error);
    }
  );

  return client;
};

const apiClient = createApiClient();

// Base API Class
abstract class BaseApiService {
  protected client: AxiosInstance;

  constructor() {
    this.client = apiClient;
  }

  protected async request<T>(
    method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH',
    endpoint: string,
    data?: any,
    config?: RequestConfig
  ): Promise<T> {
    try {
      const response = await this.client.request<ApiResponse<T>>({
        method,
        url: endpoint,
        data,
        params: config?.params,
        headers: config?.headers,
        timeout: config?.timeout,
      });

      if (!response.data.success) {
        throw new Error(response.data.message || 'API request failed');
      }

      return response.data.data;
    } catch (error: any) {
      if (error.response?.data) {
        const apiError: ApiError = error.response.data;
        throw new Error(apiError.error || apiError.message || 'API request failed');
      }
      throw error;
    }
  }

  protected get<T>(endpoint: string, config?: RequestConfig): Promise<T> {
    return this.request<T>('GET', endpoint, undefined, config);
  }

  protected post<T>(endpoint: string, data?: any, config?: RequestConfig): Promise<T> {
    return this.request<T>('POST', endpoint, data, config);
  }

  protected put<T>(endpoint: string, data?: any, config?: RequestConfig): Promise<T> {
    return this.request<T>('PUT', endpoint, data, config);
  }

  protected patch<T>(endpoint: string, data?: any, config?: RequestConfig): Promise<T> {
    return this.request<T>('PATCH', endpoint, data, config);
  }

  protected delete<T>(endpoint: string, config?: RequestConfig): Promise<T> {
    return this.request<T>('DELETE', endpoint, undefined, config);
  }
}

// Metrics API Service
export class MetricsApiService extends BaseApiService {
  async getMetrics(timeRange?: { start: string; end: string }): Promise<AnalyticsMetric[]> {
    const params = timeRange ? { timeRange } : {};
    return this.get<AnalyticsMetric[]>('/metrics', { params });
  }

  async getMetric(metricId: string): Promise<AnalyticsMetric> {
    return this.get<AnalyticsMetric>(`/metrics/${metricId}`);
  }

  async getTimeSeriesData(
    metricId: string,
    timeRange?: { start: string; end: string },
    granularity?: 'minute' | 'hour' | 'day'
  ): Promise<TimeSeriesData[]> {
    const params = {
      ...(timeRange && { timeRange }),
      ...(granularity && { granularity }),
    };
    return this.get<TimeSeriesData[]>(`/metrics/${metricId}/timeseries`, { params });
  }

  async createMetric(metric: Omit<AnalyticsMetric, 'id'>): Promise<AnalyticsMetric> {
    return this.post<AnalyticsMetric>('/metrics', metric);
  }

  async updateMetric(metricId: string, updates: Partial<AnalyticsMetric>): Promise<AnalyticsMetric> {
    return this.patch<AnalyticsMetric>(`/metrics/${metricId}`, updates);
  }

  async deleteMetric(metricId: string): Promise<void> {
    return this.delete<void>(`/metrics/${metricId}`);
  }

  async getAggregatedMetrics(
    metricIds: string[],
    aggregation: 'sum' | 'average' | 'min' | 'max',
    timeRange?: { start: string; end: string }
  ): Promise<AnalyticsMetric> {
    const params = {
      metricIds,
      aggregation,
      ...(timeRange && { timeRange }),
    };
    return this.get<AnalyticsMetric>('/metrics/aggregate', { params });
  }
}

// Graph API Service
export class GraphApiService extends BaseApiService {
  async getGraphData(filters?: {
    nodeTypes?: string[];
    edgeTypes?: string[];
    timeRange?: { start: string; end: string };
    searchQuery?: string;
    limit?: number;
  }): Promise<GraphData> {
    const params = filters || {};
    return this.get<GraphData>('/graph', { params });
  }

  async getNode(nodeId: string): Promise<GraphNode> {
    return this.get<GraphNode>(`/graph/nodes/${nodeId}`);
  }

  async getEdge(edgeId: string): Promise<GraphEdge> {
    return this.get<GraphEdge>(`/graph/edges/${edgeId}`);
  }

  async searchNodes(query: string, limit?: number): Promise<GraphNode[]> {
    const params = { query, limit };
    return this.get<GraphNode[]>('/graph/nodes/search', { params });
  }

  async getNodeNeighbors(nodeId: string, depth?: number): Promise<GraphData> {
    const params = { depth };
    return this.get<GraphData>(`/graph/nodes/${nodeId}/neighbors`, { params });
  }

  async getGraphStatistics(): Promise<{
    totalNodes: number;
    totalEdges: number;
    nodeTypes: Record<string, number>;
    edgeTypes: Record<string, number>;
    density: number;
    averageDegree: number;
  }> {
    return this.get<any>('/graph/statistics');
  }

  async getGraphLayout(layout: 'force' | 'hierarchical' | 'circular'): Promise<{
    nodes: Array<{ id: string; x: number; y: number }>;
    edges: Array<{ id: string; source: string; target: string }>;
  }> {
    const params = { layout };
    return this.get<any>('/graph/layout', { params });
  }

  async detectCommunities(algorithm?: 'louvain' | 'label-propagation' | 'walktrap'): Promise<Record<string, string[]>> {
    const params = { algorithm };
    return this.get<Record<string, string[]>>('/graph/communities', { params });
  }

  async calculateCentrality(
    type: 'degree' | 'betweenness' | 'closeness' | 'eigenvector' | 'pagerank'
  ): Promise<Record<string, number>> {
    const params = { type };
    return this.get<Record<string, number>>('/graph/centrality', { params });
  }

  async findShortestPath(sourceId: string, targetId: string): Promise<string[]> {
    const params = { source: sourceId, target: targetId };
    return this.get<string[]>('/graph/shortest-path', { params });
  }
}

// Dashboard API Service
export class DashboardApiService extends BaseApiService {
  async getDashboards(): Promise<Dashboard[]> {
    return this.get<Dashboard[]>('/dashboards');
  }

  async getDashboard(dashboardId: string): Promise<Dashboard> {
    return this.get<Dashboard>(`/dashboards/${dashboardId}`);
  }

  async createDashboard(dashboard: Omit<Dashboard, 'id' | 'createdAt' | 'updatedAt'>): Promise<Dashboard> {
    return this.post<Dashboard>('/dashboards', dashboard);
  }

  async updateDashboard(dashboardId: string, updates: Partial<Dashboard>): Promise<Dashboard> {
    return this.patch<Dashboard>(`/dashboards/${dashboardId}`, updates);
  }

  async deleteDashboard(dashboardId: string): Promise<void> {
    return this.delete<void>(`/dashboards/${dashboardId}`);
  }

  async duplicateDashboard(dashboardId: string, name: string): Promise<Dashboard> {
    return this.post<Dashboard>(`/dashboards/${dashboardId}/duplicate`, { name });
  }

  async addWidget(dashboardId: string, widget: Omit<Widget, 'id' | 'lastUpdated' | 'isRefreshing'>): Promise<Widget> {
    return this.post<Widget>(`/dashboards/${dashboardId}/widgets`, widget);
  }

  async updateWidget(widgetId: string, updates: Partial<Widget>): Promise<Widget> {
    return this.patch<Widget>(`/widgets/${widgetId}`, updates);
  }

  async deleteWidget(widgetId: string): Promise<void> {
    return this.delete<void>(`/widgets/${widgetId}`);
  }

  async refreshWidget(widgetId: string): Promise<Widget> {
    return this.post<Widget>(`/widgets/${widgetId}/refresh`);
  }

  async getWidgetData(widgetId: string): Promise<any> {
    return this.get<any>(`/widgets/${widgetId}/data`);
  }
}

// Report API Service
export class ReportApiService extends BaseApiService {
  async getReports(): Promise<Report[]> {
    return this.get<Report[]>('/reports');
  }

  async getReport(reportId: string): Promise<Report> {
    return this.get<Report>(`/reports/${reportId}`);
  }

  async createReport(report: Omit<Report, 'id'>): Promise<Report> {
    return this.post<Report>('/reports', report);
  }

  async updateReport(reportId: string, updates: Partial<Report>): Promise<Report> {
    return this.patch<Report>(`/reports/${reportId}`, updates);
  }

  async deleteReport(reportId: string): Promise<void> {
    return this.delete<void>(`/reports/${reportId}`);
  }

  async generateReport(reportId: string, format?: 'pdf' | 'csv' | 'json'): Promise<{
    downloadUrl: string;
    expiresAt: string;
  }> {
    const params = { format };
    return this.post<any>(`/reports/${reportId}/generate`, undefined, { params });
  }

  async getReportTemplates(): Promise<Array<{
    id: string;
    name: string;
    description: string;
    config: any;
  }>> {
    return this.get<any[]>('/reports/templates');
  }

  async scheduleReport(reportId: string, schedule: {
    frequency: 'daily' | 'weekly' | 'monthly';
    time: string;
    enabled: boolean;
  }): Promise<void> {
    return this.post<void>(`/reports/${reportId}/schedule`, schedule);
  }

  async getReportHistory(reportId: string): Promise<Array<{
    id: string;
    generatedAt: string;
    format: string;
    status: 'completed' | 'failed' | 'pending';
    downloadUrl?: string;
  }>> {
    return this.get<any[]>(`/reports/${reportId}/history`);
  }
}

// Alert API Service
export class AlertApiService extends BaseApiService {
  async getAlertRules(): Promise<AlertRule[]> {
    return this.get<AlertRule[]>('/alerts/rules');
  }

  async createAlertRule(rule: Omit<AlertRule, 'id'>): Promise<AlertRule> {
    return this.post<AlertRule>('/alerts/rules', rule);
  }

  async updateAlertRule(ruleId: string, updates: Partial<AlertRule>): Promise<AlertRule> {
    return this.patch<AlertRule>(`/alerts/rules/${ruleId}`, updates);
  }

  async deleteAlertRule(ruleId: string): Promise<void> {
    return this.delete<void>(`/alerts/rules/${ruleId}`);
  }

  async toggleAlertRule(ruleId: string): Promise<AlertRule> {
    return this.patch<AlertRule>(`/alerts/rules/${ruleId}/toggle`);
  }

  async testAlertRule(ruleId: string): Promise<{
    triggered: boolean;
    value: number;
    threshold: number;
  }> {
    return this.post<any>(`/alerts/rules/${ruleId}/test`);
  }

  async getActiveAlerts(limit?: number): Promise<any[]> {
    const params = { limit };
    return this.get<any[]>('/alerts', { params });
  }

  async acknowledgeAlert(alertId: string): Promise<void> {
    return this.post<void>(`/alerts/${alertId}/acknowledge`);
  }

  async resolveAlert(alertId: string): Promise<void> {
    return this.post<void>(`/alerts/${alertId}/resolve`);
  }
}

// Export API Service
export class ExportApiService extends BaseApiService {
  async exportData(
    type: 'metrics' | 'graph' | 'reports' | 'dashboards',
    format: 'json' | 'csv' | 'xlsx' | 'pdf',
    filters?: Record<string, any>
  ): Promise<{
    downloadUrl: string;
    filename: string;
    expiresAt: string;
  }> {
    const params = { type, format, ...filters };
    return this.post<any>('/export', undefined, { params });
  }

  async getExportStatus(exportId: string): Promise<{
    status: 'pending' | 'processing' | 'completed' | 'failed';
    progress: number;
    downloadUrl?: string;
    error?: string;
  }> {
    return this.get<any>(`/export/${exportId}/status`);
  }

  async downloadExport(exportId: string): Promise<Blob> {
    const response = await this.client.get(`/export/${exportId}/download`, {
      responseType: 'blob',
    });
    return response.data;
  }
}

// Create and export API service instances
export const metricsApi = new MetricsApiService();
export const graphApi = new GraphApiService();
export const dashboardApi = new DashboardApiService();
export const reportApi = new ReportApiService();
export const alertApi = new AlertApiService();
export const exportApi = new ExportApiService();

// Export base class for custom implementations
export { BaseApiService };

// Utility functions
export const createApiError = (message: string, code?: string, details?: any): ApiError => ({
  success: false,
  error: message,
  code,
  details,
});

export const isApiError = (error: any): error is ApiError => {
  return error && typeof error === 'object' && 'success' in error && error.success === false;
};

export const handleApiError = (error: any): string => {
  if (isApiError(error)) {
    return error.error;
  }
  if (error.response?.data?.message) {
    return error.response.data.message;
  }
  if (error.message) {
    return error.message;
  }
  return 'An unexpected error occurred';
};
