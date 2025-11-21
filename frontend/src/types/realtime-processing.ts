// Real-time Processing Types
export interface ProcessingStage {
  id: string;
  name: string;
  description: string;
  progress: number; // 0-100
  status: 'pending' | 'in_progress' | 'completed' | 'failed' | 'skipped';
  startedAt?: string;
  completedAt?: string;
  duration?: number; // milliseconds
  error?: string;
}

export interface DocumentProcessingState {
  id: string;
  filename: string;
  fileType: 'pdf' | 'txt' | 'jpg' | 'png' | 'mp3' | 'mp4';
  overallProgress: number; // 0-100
  currentStage: ProcessingStage;
  stages: ProcessingStage[];
  status: 'queued' | 'uploading' | 'processing' | 'completed' | 'failed' | 'paused' | 'cancelled';
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
    processing: number;
    completed: number;
    failed: number;
    paused: number;
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
  status: 'disconnected' | 'connecting' | 'connected' | 'reconnecting' | 'error';
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
  type: string;
  payload: any;
  timestamp: string;
  documentId?: string;
  jobId?: string;
}

export interface DocumentUpdateMessage extends WebSocketMessage {
  type: 'document_update';
  payload: {
    documentId: string;
    progress: number;
    currentStage: ProcessingStage;
    status: DocumentProcessingState['status'];
    error?: string;
  };
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

export interface NotificationMessage extends WebSocketMessage {
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