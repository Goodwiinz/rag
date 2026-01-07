// Analytics Types for RAG System
import type { ReactNode } from 'react';

// Analytics tracking types
export type AnalyticsProvider = 'google-analytics' | 'plausible' | 'custom' | 'none';

export interface AnalyticsConfig {
  enabled?: boolean;
  trackingId?: string;
  debug?: boolean;
  anonymizeIp?: boolean;
  sampleRate?: number;
  // Extended properties for lib/analytics.ts
  provider?: AnalyticsProvider;
  measurementId?: string;
  customEndpoint?: string;
  trackPageViews?: boolean;
  trackEvents?: boolean;
  enableDebug?: boolean;
}

export interface AnalyticsEvent {
  name?: string;
  event?: string; // Alternative to name for AnalyticsService
  category?: string;
  action?: string;
  label?: string;
  value?: number;
  properties?: Record<string, unknown>;
  timestamp?: string;
  // Extended properties used by AnalyticsService
  userId?: string;
  sessionId?: string;
  page?: string;
  userAgent?: string;
  referrer?: string;
}

export interface PageView {
  path: string;
  title?: string;
  referrer?: string;
  properties?: Record<string, unknown>;
  timestamp?: string;
  // Extended properties used by AnalyticsService
  userId?: string;
  sessionId?: string;
  userAgent?: string;
}

export interface UserSession {
  id: string;
  userId?: string;
  startTime: string;
  endTime?: string;
  pageViews: PageView[];
  events: AnalyticsEvent[];
}

export interface RAGTriadMetrics {
  context_relevance: MetricScore;
  answer_relevance: MetricScore;
  groundedness: MetricScore;
  overall_score: number;
  timestamp: string;
  metadata?: Record<string, any>;
}

export interface MetricScore {
  score: number;
  confidence: number;
  samples: number;
  trend?: TrendData;
}

export interface TrendData {
  direction: 'up' | 'down' | 'stable';
  percentage: number;
  comparison_period?: string;
}

export interface SystemPerformanceMetrics {
  latency: LatencyMetrics;
  throughput: ThroughputMetrics;
  error_rate: ErrorRateMetrics;
  resource_utilization: ResourceMetrics;
  timestamp: string;
}

export interface LatencyMetrics {
  average: number;
  p50: number;
  p95: number;
  p99: number;
  unit: 'ms' | 's';
}

export interface ThroughputMetrics {
  requests_per_second: number;
  queries_per_minute: number;
  peak_throughput: number;
}

export interface ErrorRateMetrics {
  total_errors: number;
  error_rate: number;
  error_types: Record<string, number>;
}

export interface ResourceMetrics {
  cpu_usage: number;
  memory_usage: number;
  disk_usage: number;
  network_usage: number;
}

export interface SystemUsageMetrics {
  total_queries: number;
  unique_users: number;
  active_sessions: number;
  popular_queries: QueryFrequency[];
  user_behavior: UserBehaviorMetrics;
  timestamp: string;
}

export interface QueryFrequency {
  query: string;
  frequency: number;
  avg_response_time: number;
  success_rate: number;
}

export interface UserBehaviorMetrics {
  avg_session_duration: number;
  avg_queries_per_session: number;
  bounce_rate: number;
  return_rate: number;
}

export type TimeRangePreset =
  | '1h'
  | '24h'
  | '7d'
  | '30d'
  | '90d'
  | 'custom';

export interface CustomTimeRange {
  start: string;
  end: string;
}

export type TimeRange = TimeRangePreset | CustomTimeRange;

export interface AnalyticsFilters {
  timeRange?: TimeRange;
  startDate?: string;
  endDate?: string;
  metricType?: string;
  groupBy?: 'hour' | 'day' | 'week' | 'month';
  tags?: string[];
  documentIds?: string[];
  modalities?: string[];
  queryTypes?: string[];
  userSegments?: string[];
  performanceThresholds?: {
    answer_relevancy: number;
    faithfulness: number;
    contextual_relevancy: number;
  };
}

export interface MetricCardProps {
  title: string;
  value: number | string;
  unit?: string;
  trend?: TrendData;
  status?: 'success' | 'warning' | 'error' | 'info';
  description?: string;
  icon?: ReactNode;
  loading?: boolean;
  threshold?: number;
  error?: string | null;
  onClick?: () => void;
}

export interface ChartData {
  timestamp: string;
  value: number;
  label?: string;
  metadata?: Record<string, any>;
}

export interface AnalyticsDashboardData {
  ragTriadMetrics: RAGTriadMetrics;
  performanceAnalytics: SystemPerformanceMetrics;
  usageAnalytics: SystemUsageMetrics;
  recentActivity: ActivityItem[];
}

export interface ActivityItem {
  id: string;
  type: 'query' | 'evaluation' | 'error' | 'alert';
  description: string;
  timestamp: string;
  severity?: 'low' | 'medium' | 'high' | 'critical';
  metadata?: Record<string, any>;
}

// Search Analytics
export interface SearchAnalyticsData {
  top_queries: QueryFrequency[];
  query_categories: QueryCategory[];
  search_trends: SearchTrend[];
  failed_queries: FailedQuery[];
}

export interface QueryCategory {
  category: string;
  count: number;
  avg_score: number;
  queries: Array<{ query: string; frequency: number }>;
}

export interface SearchTrend {
  date: string;
  total_searches: number;
  unique_queries: number;
  avg_results: number;
}

export interface FailedQuery {
  query: string;
  count: number;
  last_attempt: string;
  reason?: string;
}

// Quality Metrics
export interface QualityMetrics {
  accuracy: number;
  precision: number;
  recall: number;
  f1_score: number;
  user_satisfaction: number;
}

// Recommendation types
export interface RecommendationData {
  recommendations: Recommendation[];
  priority: 'low' | 'medium' | 'high';
}

export interface Recommendation {
  id: string;
  type: 'performance' | 'quality' | 'usage' | 'cost';
  title: string;
  description: string;
  impact: 'low' | 'medium' | 'high';
  effort: 'low' | 'medium' | 'high';
  action_items: string[];
}

// Backward compatibility exports
export type { SystemPerformanceMetrics as PerformanceMetrics };
export type { SystemUsageMetrics as UsageMetrics };
export type { SystemPerformanceMetrics as PerformanceAnalytics };
export type { SystemUsageMetrics as UsageAnalytics };
