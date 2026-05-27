// Real-time Processing Types

// Status types defined explicitly to avoid circular references
export type ProcessingStatus =
  | 'queued'
  | 'uploading'
  | 'processing'
  | 'completed'
  | 'failed'
  | 'paused'
  | 'cancelled';

// Performance Metrics for WebSocket/processing components
export interface PerformanceMetrics {
  connectionLatency: number;
  messageRate: number;
  errorRate: number;
  reconnectionCount: number;
  uptime: number;
  lastMessageTimestamp: number;
  activeJobs?: number;
  cpuUsage?: number;
  memoryUsage?: number;
  averageJobDuration?: number;
}

export interface SystemMetrics {
  concurrentConnections: number;
  memoryUsage: number;
  cpuUsage: number;
  diskSpace: number;
  activeJobs: number;
  queuedJobs: number;
  completedJobs: number;
  averageJobDuration: number;
}

export type StageStatus =
  | 'pending'
  | 'in_progress'
  | 'completed'
  | 'failed'
  | 'skipped'
  | 'cancelled';

export interface ProcessingStage {
  id: string;
  name: string;
  description: string;
  progress: number; // 0-100
  status: StageStatus;
  startedAt?: string;
  completedAt?: string;
  duration?: number; // milliseconds
  error?: string;
  stage_metadata?: Record<string, unknown>;
}

export interface DocumentProcessingState {
  id: string;
  filename: string;
  fileType: 'pdf' | 'txt' | 'jpg' | 'png' | 'mp3' | 'mp4';
  overallProgress: number; // 0-100
  currentStage: ProcessingStage;
  stages: ProcessingStage[];
  status: ProcessingStatus;
  uploadProgress: number; // 0-100
  metadata: {
    fileSize: number;
    pageCount?: number;
    duration?: number;
    uploadStartedAt: string;
    processingStartedAt?: string;
    completedAt?: string;
    estimatedTimeRemaining?: number; // seconds
  };
  error?: string;
  retryCount: number;
  canRetry: boolean;
  actions: {
    pause: boolean;
    resume: boolean;
    cancel: boolean;
    retry: boolean;
    download: boolean;
  };
}

export interface ProcessingQueue {
  documents: DocumentProcessingState[];
  summary: {
    total: number;
    queued: number;
    uploading: number;
    processing: number;
    completed: number;
    failed: number;
    paused: number;
    cancelled: number;
  };
  metrics: {
    averageProcessingTime: number; // seconds
    throughput: number; // documents per minute
    successRate: number; // percentage
    errorRate: number; // percentage
  };
  filters: {
    fileTypes: string[];
    statuses: string[];
    dateRange?: {
      start: string;
      end: string;
    };
    searchTerm: string;
  };
  pagination: {
    page: number;
    pageSize: number;
    total: number;
    hasMore: boolean;
  };
}

export interface WebSocketConnectionState {
  status:
    | 'disconnected'
    | 'connecting'
    | 'connected'
    | 'reconnecting'
    | 'error';
  lastConnectedAt?: string;
  lastError?: string;
  reconnectionAttempts: number;
  maxReconnectionAttempts: number;
  reconnectInterval: number; // milliseconds
  latency: number; // milliseconds
}

export interface NotificationItem {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message: string;
  timestamp: string;
  documentId?: string;
  autoHide?: boolean;
  autoHideDelay?: number; // milliseconds
  actions?: {
    label: string;
    action: () => void;
  }[];
}

export interface RealtimeProcessingState {
  // WebSocket connection
  connection: WebSocketConnectionState;

  // Document processing queue
  queue: ProcessingQueue;

  // System-wide metrics
  systemMetrics: {
    concurrentConnections: number;
    memoryUsage: number;
    cpuUsage: number;
    diskSpace: number;
    activeJobs: number;
    queuedJobs: number;
    completedJobs: number;
    averageJobDuration: number;
  };

  // Notifications
  notifications: NotificationItem[];

  // UI state
  ui: {
    selectedDocuments: string[];
    sidebarCollapsed: boolean;
    autoScrollEnabled: boolean;
    compactView: boolean;
    theme: 'light' | 'dark' | 'auto';
  };

  // User preferences
  preferences: {
    refreshInterval: number; // milliseconds
    maxNotifications: number;
    soundEnabled: boolean;
    desktopNotifications: boolean;
    autoRetryFailed: boolean;
    maxRetryAttempts: number;
  };
}

// WebSocket Message Types
export interface WebSocketMessage {
  id?: string;
  type: string;
  payload: Record<string, unknown>;
  timestamp?: string;
  documentId?: string;
  jobId?: string;
  priority?: MessagePriority;
  target_channels?: Channel[];
}

export interface DocumentUpdatePayload {
  documentId: string;
  filename?: string;
  progress?: number;
  currentStage?: ProcessingStage;
  status?: DocumentProcessingState['status'];
  error?: string;
  [key: string]: unknown;
}

export interface DocumentUpdateMessage extends Omit<
  WebSocketMessage,
  'payload'
> {
  type: 'document_update';
  payload: DocumentUpdatePayload;
  documentId: string;
}

export interface QueueUpdateMessage extends WebSocketMessage {
  type: 'queue_update';
  payload: {
    summary: ProcessingQueue['summary'];
    metrics: ProcessingQueue['metrics'];
  };
}

export interface SystemMetricsMessage extends WebSocketMessage {
  type: 'system_metrics';
  payload: RealtimeProcessingState['systemMetrics'];
}

export interface NotificationMessage extends Omit<WebSocketMessage, 'payload'> {
  type: 'notification';
  payload: NotificationItem;
}

export interface ConnectionStatusMessage extends WebSocketMessage {
  type: 'connection_status';
  payload: {
    status: WebSocketConnectionState['status'];
    message?: string;
  };
}

// Enhanced WebSocket Connection Types
export interface WebSocketConnectionInfo {
  id: string;
  user_id: string;
  organization_id: string;
  connected_at: string;
  last_activity: string;
  last_heartbeat: string;
  client_ip: string;
  user_agent: string;
  connection_metadata: Record<string, unknown>;
  subscription_channels: string[];
  is_active: boolean;
  disconnect_reason?: string;
  disconnected_at?: string;
  message_count_sent: number;
  message_count_received: number;
  bytes_sent: number;
  bytes_received: number;
}

// Message Priority and Channel Types
export enum MessagePriority {
  LOW = 'low',
  NORMAL = 'normal',
  HIGH = 'high',
  CRITICAL = 'critical',
}

export enum UpdateFrequency {
  REALTIME = 'realtime',
  FREQUENT = 'frequent',
  NORMAL = 'normal',
  PERIODIC = 'periodic',
}

export enum Channel {
  DOCUMENT_PROCESSING = 'document_processing',
  JOB_STATUS = 'job_status',
  SYSTEM_STATUS = 'system_status',
  USER_NOTIFICATIONS = 'user_notifications',
  QUOTA_ALERTS = 'quota_alerts',
  QUALITY_METRICS = 'quality_metrics',
  ADMIN_ALERTS = 'admin_alerts',
}

// Client info for WebSocket connection
export interface WebSocketClientInfo {
  timestamp?: string;
  userAgent?: string;
  url?: string;
  [key: string]: unknown;
}

// Enhanced Store Interface
export interface RealtimeStore {
  // WebSocket state
  connection: WebSocketConnectionState;
  connectionInfo: WebSocketConnectionInfo | null;

  // Document processing state
  documents: Map<string, DocumentProcessingState>;
  subscribedDocuments: Set<string>;

  // Performance metrics
  systemMetrics: RealtimeProcessingState['systemMetrics'];

  // Configuration
  config: {
    updateFrequency: UpdateFrequency;
    subscribedChannels: Set<Channel>;
    messageFilter: Record<string, unknown>;
    autoReconnect: boolean;
    reconnectDelay: number;
    maxReconnectAttempts: number;
  };

  // Actions
  connect: (
    token: string,
    options?: {
      channels?: Channel[];
      frequency?: UpdateFrequency;
      clientInfo?: WebSocketClientInfo;
    }
  ) => Promise<void>;
  disconnect: () => void;
  reconnect: () => void;
  subscribeToChannel: (channel: Channel) => void;
  unsubscribeFromChannel: (channel: Channel) => void;
  subscribeToDocument: (documentId: string) => void;
  unsubscribeFromDocument: (documentId: string) => void;
  updateDocumentStatus: (update: DocumentUpdateMessage) => void;
  sendWebSocketMessage: (
    message:
      | WebSocketMessage
      | { type: string; payload: Record<string, unknown> }
  ) => void;
  clearNotifications: () => void;
  updatePreferences: (
    preferences: Partial<RealtimeProcessingState['preferences']>
  ) => void;
  updateUI: (ui: Partial<RealtimeProcessingState['ui']>) => void;
}

// WebSocket Client Configuration
export interface WebSocketClientConfig {
  url: string;
  token: string;
  channels?: Channel[];
  frequency?: UpdateFrequency;
  messageFilter?: Record<string, unknown>;
  clientInfo?: WebSocketClientInfo;
  autoReconnect?: boolean;
  reconnectDelay?: number;
  maxReconnectAttempts?: number;
  heartbeatInterval?: number;
  enableBatching?: boolean;
  batchSize?: number;
  batchTimeout?: number;
}

// Processing Stage Enhancements
export interface EnhancedProcessingStage extends ProcessingStage {
  stage_type: string;
  stage_order: number;
  worker_id?: string;
  stage_metadata?: Record<string, unknown>;
  error_details?: Record<string, unknown>;
  retry_count: number;
  max_retries: number;
  estimated_completion_time?: string;
}

// System Status Summary
export interface SystemStatusSummary {
  total_documents: number;
  queued_documents: number;
  processing_documents: number;
  processed_documents: number;
  failed_documents: number;
  active_websocket_connections: number;
  connected_users: number;
  avg_processing_time_5min?: number;
  updates_last_5min: number;
  active_jobs: number;
  status_timestamp: string;
}
