/**
 * Comprehensive TypeScript definitions for the Monitoring Dashboard System
 * This file contains all types related to monitoring, alerts, metrics, and dashboard components
 */

// ============================================================================
// CORE MONITORING TYPES
// ============================================================================

export interface SystemHealthScore {
  overall: number; // 0-100
  components: ComponentHealth[];
  timestamp: string;
  trend: HealthTrend;
}

export interface ComponentHealth {
  name: string;
  status: 'healthy' | 'degraded' | 'unhealthy' | 'unknown';
  score: number; // 0-100
  last_check: string;
  metrics?: Record<string, number>;
  dependencies?: string[];
}

export interface HealthTrend {
  direction: 'improving' | 'stable' | 'degrading';
  percentage: number;
  period: string;
}

// ============================================================================
// SLI/SLO METRICS
// ============================================================================

export interface SLIMetrics {
  name: string;
  current_value: number;
  target: number;
  window: string; // e.g., "30d", "7d", "24h"
  status: 'passing' | 'warning' | 'failing';
  history: SLIDataPoint[];
}

export interface SLIDataPoint {
  timestamp: string;
  value: number;
  target: number;
  achieved: boolean;
}

export interface SLODefinition {
  id: string;
  name: string;
  description: string;
  sli_name: string;
  target_percentage: number;
  window: string;
  alerting_policy: AlertingPolicy;
  status: 'active' | 'disabled' | 'deleted';
  created_at: string;
  updated_at: string;
}

export interface AlertingPolicy {
  burn_rate_threshold: number;
  alert_after_minutes: number;
  severity: 'critical' | 'warning' | 'info';
}

// ============================================================================
// PERFORMANCE METRICS
// ============================================================================

export interface PerformanceMetrics {
  latency: LatencyMetrics;
  throughput: ThroughputMetrics;
  error_rates: ErrorRateMetrics;
  resource_utilization: ResourceMetrics;
  cache_performance: CacheMetrics;
  database_performance: DatabaseMetrics;
  timestamp: string;
}

export interface LatencyMetrics {
  average_ms: number;
  p50_ms: number;
  p90_ms: number;
  p95_ms: number;
  p99_ms: number;
  max_ms: number;
  trend: TrendData;
}

export interface ThroughputMetrics {
  requests_per_second: number;
  queries_per_minute: number;
  documents_processed_per_hour: number;
  peak_throughput: number;
  trend: TrendData;
}

export interface ErrorRateMetrics {
  total_errors: number;
  error_rate_percentage: number;
  errors_by_type: Record<string, number>;
  errors_by_service: Record<string, number>;
  critical_errors: number;
  trend: TrendData;
}

export interface ResourceMetrics {
  cpu: {
    usage_percentage: number;
    cores_available: number;
    load_average: number[];
  };
  memory: {
    used_percentage: number;
    used_gb: number;
    total_gb: number;
    available_gb: number;
  };
  disk: {
    used_percentage: number;
    used_gb: number;
    total_gb: number;
    read_iops: number;
    write_iops: number;
  };
  network: {
    incoming_mbps: number;
    outgoing_mbps: number;
  };
}

export interface CacheMetrics {
  hit_rate_percentage: number;
  miss_rate_percentage: number;
  eviction_rate: number;
  size_mb: number;
  max_size_mb: number;
}

export interface DatabaseMetrics {
  connection_pool: {
    active_connections: number;
    idle_connections: number;
    max_connections: number;
  };
  query_performance: {
    average_query_time_ms: number;
    slow_queries_count: number;
    total_queries_count: number;
  };
  replication_lag_ms?: number;
}

// ============================================================================
// BUSINESS METRICS
// ============================================================================

export interface BusinessMetrics {
  document_processing: DocumentProcessingMetrics;
  search_quality: SearchQualityMetrics;
  user_engagement: UserEngagementMetrics;
  content_analytics: ContentAnalytics;
  timestamp: string;
}

export interface DocumentProcessingMetrics {
  total_documents: number;
  processed_today: number;
  processing_success_rate: number;
  average_processing_time_seconds: number;
  queue_depth: number;
  processing_by_type: Record<string, number>;
  failed_processing_today: number;
  retry_rate: number;
}

export interface SearchQualityMetrics {
  total_searches: number;
  searches_today: number;
  average_result_count: number;
  zero_result_rate: number;
  click_through_rate: number;
  user_satisfaction_score: number;
  rag_triad_scores: {
    answer_relevancy: number;
    faithfulness: number;
    contextual_relevancy: number;
  };
  search_by_modality: Record<string, number>;
}

export interface UserEngagementMetrics {
  active_users_today: number;
  active_users_this_week: number;
  active_users_this_month: number;
  average_session_duration_minutes: number;
  average_queries_per_session: number;
  user_retention_rate: number;
  new_users_today: number;
  power_users_count: number;
}

export interface ContentAnalytics {
  total_entities: number;
  total_relationships: number;
  knowledge_graph_growth: {
    entities_added_today: number;
    relationships_added_today: number;
  };
  content_by_modality: Record<string, number>;
  most_accessed_content: ContentAccessStats[];
}

export interface ContentAccessStats {
  content_id: string;
  content_type: string;
  access_count: number;
  last_accessed: string;
}

// ============================================================================
// INFRASTRUCTURE METRICS
// ============================================================================

export interface InfrastructureMetrics {
  services: ServiceHealthMetrics[];
  databases: DatabaseHealthMetrics[];
  external_apis: ExternalAPIHealthMetrics[];
  message_queues: QueueMetrics[];
  timestamp: string;
}

export interface ServiceHealthMetrics {
  service_name: string;
  status: 'healthy' | 'degraded' | 'unhealthy';
  uptime_percentage: number;
  response_time_ms: number;
  last_health_check: string;
  version: string;
  endpoint_health: EndpointHealth[];
}

export interface EndpointHealth {
  endpoint: string;
  method: string;
  status_code: number;
  response_time_ms: number;
  last_check: string;
}

export interface DatabaseHealthMetrics {
  database_name: string;
  type: 'postgresql' | 'neo4j' | 'qdrant' | 'redis';
  status: 'healthy' | 'degraded' | 'unhealthy';
  connection_count: number;
  query_performance: DatabaseQueryMetrics;
  storage_metrics: DatabaseStorageMetrics;
  replication_status?: ReplicationStatus;
}

export interface DatabaseQueryMetrics {
  average_query_time_ms: number;
  queries_per_second: number;
  slow_queries_count: number;
  failed_queries_count: number;
}

export interface DatabaseStorageMetrics {
  size_gb: number;
  used_percentage: number;
  index_size_gb: number;
  growth_rate_mb_per_day: number;
}

export interface ReplicationStatus {
  status: 'healthy' | 'lagging' | 'failed';
  lag_seconds: number;
  last_sync: string;
}

export interface ExternalAPIHealthMetrics {
  api_name: string;
  status: 'healthy' | 'degraded' | 'unhealthy';
  response_time_ms: number;
  success_rate_percentage: number;
  error_rate_percentage: number;
  last_request: string;
  rate_limit_remaining?: number;
}

export interface QueueMetrics {
  queue_name: string;
  depth: number;
  processing_rate: number;
  message_rate: number;
  consumer_count: number;
  oldest_message_age_seconds: number;
  dead_letter_queue_depth: number;
}

// ============================================================================
// ALERT MANAGEMENT
// ============================================================================

export interface Alert {
  id: string;
  name: string;
  description: string;
  severity: 'critical' | 'warning' | 'info';
  status: 'active' | 'acknowledged' | 'resolved' | 'suppressed';
  source: string;
  rule_id: string;
  triggered_at: string;
  acknowledged_at?: string;
  acknowledged_by?: string;
  resolved_at?: string;
  resolved_by?: string;
  metadata: Record<string, any>;
  labels: Record<string, string>;
  annotations: Record<string, string>;
  actions: AlertAction[];
}

export interface AlertAction {
  type: 'acknowledge' | 'resolve' | 'escalate' | 'silence' | 'run_playbook';
  label: string;
  available: boolean;
  performed_at?: string;
  performed_by?: string;
}

export interface AlertRule {
  id: string;
  name: string;
  description: string;
  condition: AlertCondition;
  severity: 'critical' | 'warning' | 'info';
  enabled: boolean;
  notification_channels: string[];
  cooldown_period_minutes: number;
  evaluation_interval_seconds: number;
  created_at: string;
  updated_at: string;
  last_triggered?: string;
}

export interface AlertCondition {
  metric: string;
  operator: 'gt' | 'gte' | 'lt' | 'lte' | 'eq' | 'ne';
  threshold: number;
  duration_minutes: number;
  aggregation?: 'avg' | 'max' | 'min' | 'sum';
  group_by?: string[];
}

export interface AlertHistory {
  total_alerts: number;
  active_alerts: number;
  alerts_by_severity: Record<string, number>;
  alerts_by_source: Record<string, number>;
  mean_time_to_acknowledge_minutes: number;
  mean_time_to_resolve_minutes: number;
  recent_alerts: Alert[];
}

// ============================================================================
// USER ANALYTICS
// ============================================================================

export interface UserAnalytics {
  session_metrics: SessionMetrics;
  concurrent_users: ConcurrentUserMetrics;
  feature_usage: FeatureUsageMetrics;
  user_segments: UserSegmentMetrics;
  user_journey: UserJourneyMetrics;
  timestamp: string;
}

export interface SessionMetrics {
  active_sessions: number;
  average_session_duration_minutes: number;
  sessions_today: number;
  sessions_this_week: number;
  sessions_this_month: number;
  bounce_rate: number;
  new_vs_returning: {
    new_sessions: number;
    returning_sessions: number;
  };
}

export interface ConcurrentUserMetrics {
  current_users: number;
  peak_today: number;
  peak_this_week: number;
  peak_this_month: number;
  average_concurrent_users: number;
  user_distribution: UserDistribution;
}

export interface UserDistribution {
  by_role: Record<string, number>;
  by_location: Record<string, number>;
  by_device: Record<string, number>;
  by_browser: Record<string, number>;
}

export interface FeatureUsageMetrics {
  feature_adoption: Record<string, number>;
  feature_frequency: Record<string, number>;
  most_used_features: FeatureUsage[];

  least_used_features: FeatureUsage[];
  feature_correlation: Record<string, Record<string, number>>;
}

export interface FeatureUsage {
  feature_name: string;
  usage_count: number;
  unique_users: number;
  average_usage_per_user: number;
  adoption_rate: number;
}

export interface UserSegmentMetrics {
  segments: UserSegment[];
  segment_behavior: Record<string, SegmentBehavior>;
  segment_growth: Record<string, number>;
}

export interface UserSegment {
  id: string;
  name: string;
  description: string;
  user_count: number;
  criteria: SegmentCriteria;
}

export interface SegmentCriteria {
  demographics?: Record<string, any>;
  behavior?: Record<string, any>;
  usage?: Record<string, any>;
  custom?: Record<string, any>;
}

export interface SegmentBehavior {
  average_session_duration: number;
  feature_usage: Record<string, number>;
  retention_rate: number;
  satisfaction_score: number;
}

export interface UserJourneyMetrics {
  common_paths: UserJourneyPath[];
  conversion_funnel: ConversionFunnelStep[];
  drop_off_points: DropOffPoint[];
  time_to_value: TimeToValueMetric[];
}

export interface UserJourneyPath {
  path_id: string;
  steps: string[];
  frequency: number;
  conversion_rate: number;
  average_completion_time_minutes: number;
}

export interface ConversionFunnelStep {
  step_name: string;
  step_number: number;
  users_completed: number;
  users_started: number;
  conversion_rate: number;
  drop_off_rate: number;
  average_time_to_complete_minutes: number;
}

export interface DropOffPoint {
  step_name: string;
  drop_off_count: number;
  drop_off_rate: number;
  reasons: string[];
}

export interface TimeToValueMetric {
  action: string;
  average_time_minutes: number;
  median_time_minutes: number;
  p90_time_minutes: number;
  users_achieved: number;
}

// ============================================================================
// DASHBOARD COMPONENT TYPES
// ============================================================================

export interface DashboardConfig {
  id: string;
  name: string;
  description: string;
  layout: DashboardLayout;
  widgets: WidgetConfig[];
  filters: DashboardFilter[];
  refresh_interval_seconds: number;
  auto_refresh: boolean;
  time_range: TimeRange;
}

export interface DashboardLayout {
  columns: number;
  row_height: number;
  gap: number;
  breakpoints: Record<string, number>;
}

export interface WidgetConfig {
  id: string;
  type: WidgetType;
  title: string;
  position: WidgetPosition;
  data_source: DataSource;
  visualization: VisualizationConfig;
  interactions: InteractionConfig;
  refresh_interval?: number;
}

export interface WidgetPosition {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface DataSource {
  type: 'api' | 'websocket' | 'mock';
  endpoint?: string;
  query?: string;
  refresh_interval?: number;
  transformations?: DataTransformation[];
}

export interface DataTransformation {
  type: 'filter' | 'aggregate' | 'calculate' | 'format';
  config: Record<string, any>;
}

export type WidgetType =
  | 'metric_card'
  | 'line_chart'
  | 'bar_chart'
  | 'pie_chart'
  | 'heatmap'
  | 'table'
  | 'alert_list'
  | 'status_grid'
  | 'gauge'
  | 'progress_bar'
  | 'trend_indicator'
  | 'user_list'
  | 'system_health';

export interface VisualizationConfig {
  chart_type?: string;
  axes?: ChartAxes;
  colors?: string[];
  legend?: LegendConfig;
  tooltips?: TooltipConfig;
  thresholds?: ThresholdConfig[];
}

export interface ChartAxes {
  x: AxisConfig;
  y: AxisConfig;
  y2?: AxisConfig;
}

export interface AxisConfig {
  label: string;
  type: 'linear' | 'log' | 'category' | 'time';
  format?: string;
  min?: number;
  max?: number;
}

export interface LegendConfig {
  show: boolean;
  position: 'top' | 'bottom' | 'left' | 'right';
  format?: string;
}

export interface TooltipConfig {
  show: boolean;
  format?: string;
  fields?: string[];
}

export interface ThresholdConfig {
  value: number;
  color: string;
  label?: string;
  operator?: 'gt' | 'gte' | 'lt' | 'lte';
}

export interface InteractionConfig {
  clickable: boolean;
  expandable: boolean;
  filterable: boolean;
  actions: WidgetAction[];
}

export interface WidgetAction {
  type: 'filter' | 'drill_down' | 'export' | 'share' | 'refresh';
  label: string;
  icon?: string;
  config?: Record<string, any>;
}

export interface DashboardFilter {
  key: string;
  label: string;
  type: 'select' | 'multiselect' | 'date_range' | 'text' | 'number';
  options?: FilterOption[];
  default_value?: any;
  required?: boolean;
}

export interface FilterOption {
  label: string;
  value: any;
  group?: string;
}

// ============================================================================
// REAL-TIME DATA TYPES
// ============================================================================

export interface RealTimeUpdate {
  type: UpdateType;
  timestamp: string;
  data: any;
  source: string;
  version: number;
}

export type UpdateType =
  | 'metric_update'
  | 'alert_triggered'
  | 'alert_resolved'
  | 'system_status_change'
  | 'user_activity'
  | 'performance_spike'
  | 'error_increase';

export interface WebSocketMessage {
  type: string;
  payload: any;
  timestamp: string;
  id: string;
}

// ============================================================================
// UTILITY TYPES
// ============================================================================

export interface TimeRange {
  start: string;
  end: string;
  preset?: TimeRangePreset;
}

export type TimeRangePreset = '1h' | '6h' | '24h' | '7d' | '30d' | '90d' | 'custom';

export interface TrendData {
  direction: 'up' | 'down' | 'stable';
  percentage: number;
  period: string;
  is_significant: boolean;
}

export interface LoadingState {
  loading: boolean;
  error?: string;
  last_updated?: string;
}

export interface PaginationConfig {
  page: number;
  page_size: number;
  total: number;
  has_next: boolean;
  has_prev: boolean;
}

// ============================================================================
// AGGREGATION TYPES
// ============================================================================

export interface AggregatedMetrics {
  time_bucket: string;
  metrics: Record<string, AggregatedValue>;
  dimensions?: Record<string, string>;
}

export interface AggregatedValue {
  value: number;
  count: number;
  min: number;
  max: number;
  avg: number;
  sum: number;
}

export interface MetricAggregation {
  metric: string;
  aggregation: 'avg' | 'sum' | 'min' | 'max' | 'count' | 'p50' | 'p90' | 'p95' | 'p99';
  group_by?: string[];
  time_bucket?: string;
}

// ============================================================================
// EXPORT TYPES
// ============================================================================

export interface ExportConfig {
  format: 'csv' | 'json' | 'pdf' | 'excel';
  include_charts: boolean;
  time_range: TimeRange;
  filters: Record<string, any>;
  sections: string[];
}

export interface ScheduledReport {
  id: string;
  name: string;
  description: string;
  schedule: string; // cron expression
  recipients: string[];
  export_config: ExportConfig;
  enabled: boolean;
  last_sent?: string;
  next_send?: string;
}

// ============================================================================
// INTEGRATION TYPES
// ============================================================================

export interface MonitoringIntegration {
  id: string;
  name: string;
  type: 'prometheus' | 'grafana' | 'datadog' | 'newrelic' | 'webhook';
  config: Record<string, any>;
  enabled: boolean;
  status: 'connected' | 'disconnected' | 'error';
  last_sync?: string;
  error_message?: string;
}