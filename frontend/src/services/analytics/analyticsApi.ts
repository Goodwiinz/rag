import { api } from '@/services/api-client';
import {
  AnalyticsMetric,
  TimeSeriesData,
  GraphData,
  Dashboard,
  Widget,
  Report,
  AlertRule,
} from '@/stores/analytics';
import type { GraphNode, GraphEdge } from '@/types/graph-api';

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

const ANALYTICS_API_PREFIX = '/analytics';

/**
 * Helper to make a request and extract the inner `.data` from the
 * `{ success, data, message }` envelope the analytics backend returns.
 */
async function analyticsGet<T>(endpoint: string, queryParams?: Record<string, unknown>): Promise<T> {
  let url = `${ANALYTICS_API_PREFIX}${endpoint}`;
  if (queryParams) {
    const params = new URLSearchParams();
    Object.entries(queryParams).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        if (typeof value === 'object') {
          params.append(key, JSON.stringify(value));
        } else {
          params.append(key, String(value));
        }
      }
    });
    const qs = params.toString();
    if (qs) url += `?${qs}`;
  }
  const response = await api.get<ApiResponse<T>>(url);
  if (!response.success) {
    throw new Error(response.message || 'API request failed');
  }
  return response.data;
}

async function analyticsPost<T>(endpoint: string, data?: unknown, queryParams?: Record<string, unknown>): Promise<T> {
  let url = `${ANALYTICS_API_PREFIX}${endpoint}`;
  if (queryParams) {
    const params = new URLSearchParams();
    Object.entries(queryParams).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        if (typeof value === 'object') {
          params.append(key, JSON.stringify(value));
        } else {
          params.append(key, String(value));
        }
      }
    });
    const qs = params.toString();
    if (qs) url += `?${qs}`;
  }
  const response = await api.post<ApiResponse<T>>(url, data);
  if (!response.success) {
    throw new Error(response.message || 'API request failed');
  }
  return response.data;
}

async function analyticsPatch<T>(endpoint: string, data?: unknown): Promise<T> {
  const response = await api.patch<ApiResponse<T>>(`${ANALYTICS_API_PREFIX}${endpoint}`, data);
  if (!response.success) {
    throw new Error(response.message || 'API request failed');
  }
  return response.data;
}

async function analyticsPut<T>(endpoint: string, data?: unknown): Promise<T> {
  const response = await api.put<ApiResponse<T>>(`${ANALYTICS_API_PREFIX}${endpoint}`, data);
  if (!response.success) {
    throw new Error(response.message || 'API request failed');
  }
  return response.data;
}

async function analyticsDelete<T>(endpoint: string): Promise<T> {
  const response = await api.delete<ApiResponse<T>>(`${ANALYTICS_API_PREFIX}${endpoint}`);
  if (!response.success) {
    throw new Error(response.message || 'API request failed');
  }
  return response.data;
}

// Metrics API Service
export class MetricsApiService {
  async getMetrics(timeRange?: { start: string; end: string }): Promise<AnalyticsMetric[]> {
    const params = timeRange ? { timeRange } : {};
    return analyticsGet<AnalyticsMetric[]>('/metrics', params);
  }

  async getMetric(metricId: string): Promise<AnalyticsMetric> {
    return analyticsGet<AnalyticsMetric>(`/metrics/${metricId}`);
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
    return analyticsGet<TimeSeriesData[]>(`/metrics/${metricId}/timeseries`, params);
  }

  async createMetric(metric: Omit<AnalyticsMetric, 'id'>): Promise<AnalyticsMetric> {
    return analyticsPost<AnalyticsMetric>('/metrics', metric);
  }

  async updateMetric(metricId: string, updates: Partial<AnalyticsMetric>): Promise<AnalyticsMetric> {
    return analyticsPatch<AnalyticsMetric>(`/metrics/${metricId}`, updates);
  }

  async deleteMetric(metricId: string): Promise<void> {
    return analyticsDelete<void>(`/metrics/${metricId}`);
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
    return analyticsGet<AnalyticsMetric>('/metrics/aggregate', params);
  }
}

// Graph API Service
export class GraphApiService {
  async getGraphData(filters?: {
    nodeTypes?: string[];
    edgeTypes?: string[];
    timeRange?: { start: string; end: string };
    searchQuery?: string;
    limit?: number;
  }): Promise<GraphData> {
    const params = filters || {};
    return analyticsGet<GraphData>('/graph', params);
  }

  async getNode(nodeId: string): Promise<GraphNode> {
    return analyticsGet<GraphNode>(`/graph/nodes/${nodeId}`);
  }

  async getEdge(edgeId: string): Promise<GraphEdge> {
    return analyticsGet<GraphEdge>(`/graph/edges/${edgeId}`);
  }

  async searchNodes(query: string, limit?: number): Promise<GraphNode[]> {
    const params = { query, limit };
    return analyticsGet<GraphNode[]>('/graph/nodes/search', params);
  }

  async getNodeNeighbors(nodeId: string, depth?: number): Promise<GraphData> {
    const params = { depth };
    return analyticsGet<GraphData>(`/graph/nodes/${nodeId}/neighbors`, params);
  }

  async getGraphStatistics(): Promise<{
    totalNodes: number;
    totalEdges: number;
    nodeTypes: Record<string, number>;
    edgeTypes: Record<string, number>;
    density: number;
    averageDegree: number;
  }> {
    return analyticsGet<any>('/graph/statistics');
  }

  async getGraphLayout(layout: 'force' | 'hierarchical' | 'circular'): Promise<{
    nodes: Array<{ id: string; x: number; y: number }>;
    edges: Array<{ id: string; source: string; target: string }>;
  }> {
    const params = { layout };
    return analyticsGet<any>('/graph/layout', params);
  }

  async detectCommunities(algorithm?: 'louvain' | 'label-propagation' | 'walktrap'): Promise<Record<string, string[]>> {
    const params = { algorithm };
    return analyticsGet<Record<string, string[]>>('/graph/communities', params);
  }

  async calculateCentrality(
    type: 'degree' | 'betweenness' | 'closeness' | 'eigenvector' | 'pagerank'
  ): Promise<Record<string, number>> {
    const params = { type };
    return analyticsGet<Record<string, number>>('/graph/centrality', params);
  }

  async findShortestPath(sourceId: string, targetId: string): Promise<string[]> {
    const params = { source: sourceId, target: targetId };
    return analyticsGet<string[]>('/graph/shortest-path', params);
  }
}

// Dashboard API Service
export class DashboardApiService {
  async getDashboards(): Promise<Dashboard[]> {
    return analyticsGet<Dashboard[]>('/dashboards');
  }

  async getDashboard(dashboardId: string): Promise<Dashboard> {
    return analyticsGet<Dashboard>(`/dashboards/${dashboardId}`);
  }

  async createDashboard(dashboard: Omit<Dashboard, 'id' | 'createdAt' | 'updatedAt'>): Promise<Dashboard> {
    return analyticsPost<Dashboard>('/dashboards', dashboard);
  }

  async updateDashboard(dashboardId: string, updates: Partial<Dashboard>): Promise<Dashboard> {
    return analyticsPatch<Dashboard>(`/dashboards/${dashboardId}`, updates);
  }

  async deleteDashboard(dashboardId: string): Promise<void> {
    return analyticsDelete<void>(`/dashboards/${dashboardId}`);
  }

  async duplicateDashboard(dashboardId: string, name: string): Promise<Dashboard> {
    return analyticsPost<Dashboard>(`/dashboards/${dashboardId}/duplicate`, { name });
  }

  async addWidget(dashboardId: string, widget: Omit<Widget, 'id' | 'lastUpdated' | 'isRefreshing'>): Promise<Widget> {
    return analyticsPost<Widget>(`/dashboards/${dashboardId}/widgets`, widget);
  }

  async updateWidget(widgetId: string, updates: Partial<Widget>): Promise<Widget> {
    return analyticsPatch<Widget>(`/widgets/${widgetId}`, updates);
  }

  async deleteWidget(widgetId: string): Promise<void> {
    return analyticsDelete<void>(`/widgets/${widgetId}`);
  }

  async refreshWidget(widgetId: string): Promise<Widget> {
    return analyticsPost<Widget>(`/widgets/${widgetId}/refresh`);
  }

  async getWidgetData(widgetId: string): Promise<any> {
    return analyticsGet<any>(`/widgets/${widgetId}/data`);
  }
}

// Report API Service
export class ReportApiService {
  async getReports(): Promise<Report[]> {
    return analyticsGet<Report[]>('/reports');
  }

  async getReport(reportId: string): Promise<Report> {
    return analyticsGet<Report>(`/reports/${reportId}`);
  }

  async createReport(report: Omit<Report, 'id'>): Promise<Report> {
    return analyticsPost<Report>('/reports', report);
  }

  async updateReport(reportId: string, updates: Partial<Report>): Promise<Report> {
    return analyticsPatch<Report>(`/reports/${reportId}`, updates);
  }

  async deleteReport(reportId: string): Promise<void> {
    return analyticsDelete<void>(`/reports/${reportId}`);
  }

  async generateReport(reportId: string, format?: 'pdf' | 'csv' | 'json'): Promise<{
    downloadUrl: string;
    expiresAt: string;
  }> {
    const params = format ? { format } : {};
    return analyticsPost<any>(`/reports/${reportId}/generate`, undefined, params);
  }

  async getReportTemplates(): Promise<Array<{
    id: string;
    name: string;
    description: string;
    config: any;
  }>> {
    return analyticsGet<any[]>('/reports/templates');
  }

  async scheduleReport(reportId: string, schedule: {
    frequency: 'daily' | 'weekly' | 'monthly';
    time: string;
    enabled: boolean;
  }): Promise<void> {
    return analyticsPost<void>(`/reports/${reportId}/schedule`, schedule);
  }

  async getReportHistory(reportId: string): Promise<Array<{
    id: string;
    generatedAt: string;
    format: string;
    status: 'completed' | 'failed' | 'pending';
    downloadUrl?: string;
  }>> {
    return analyticsGet<any[]>(`/reports/${reportId}/history`);
  }
}

// Alert API Service
export class AlertApiService {
  async getAlertRules(): Promise<AlertRule[]> {
    return analyticsGet<AlertRule[]>('/alerts/rules');
  }

  async createAlertRule(rule: Omit<AlertRule, 'id'>): Promise<AlertRule> {
    return analyticsPost<AlertRule>('/alerts/rules', rule);
  }

  async updateAlertRule(ruleId: string, updates: Partial<AlertRule>): Promise<AlertRule> {
    return analyticsPatch<AlertRule>(`/alerts/rules/${ruleId}`, updates);
  }

  async deleteAlertRule(ruleId: string): Promise<void> {
    return analyticsDelete<void>(`/alerts/rules/${ruleId}`);
  }

  async toggleAlertRule(ruleId: string): Promise<AlertRule> {
    return analyticsPatch<AlertRule>(`/alerts/rules/${ruleId}/toggle`);
  }

  async testAlertRule(ruleId: string): Promise<{
    triggered: boolean;
    value: number;
    threshold: number;
  }> {
    return analyticsPost<any>(`/alerts/rules/${ruleId}/test`);
  }

  async getActiveAlerts(limit?: number): Promise<any[]> {
    const params = limit !== undefined ? { limit } : {};
    return analyticsGet<any[]>('/alerts', params);
  }

  async acknowledgeAlert(alertId: string): Promise<void> {
    return analyticsPost<void>(`/alerts/${alertId}/acknowledge`);
  }

  async resolveAlert(alertId: string): Promise<void> {
    return analyticsPost<void>(`/alerts/${alertId}/resolve`);
  }
}

// Export API Service
export class ExportApiService {
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
    return analyticsPost<any>('/export', undefined, params);
  }

  async getExportStatus(exportId: string): Promise<{
    status: 'pending' | 'processing' | 'completed' | 'failed';
    progress: number;
    downloadUrl?: string;
    error?: string;
  }> {
    return analyticsGet<any>(`/export/${exportId}/status`);
  }

  async downloadExport(exportId: string): Promise<Blob> {
    return api.request(`${ANALYTICS_API_PREFIX}/export/${exportId}/download`, {
      method: 'GET',
    });
  }
}

// Create and export API service instances
export const metricsApi = new MetricsApiService();
export const graphApi = new GraphApiService();
export const dashboardApi = new DashboardApiService();
export const reportApi = new ReportApiService();
export const alertApi = new AlertApiService();
export const exportApi = new ExportApiService();

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
