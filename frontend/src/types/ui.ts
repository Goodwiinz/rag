// UI State and Layout Types
export interface UIState {
  activeTab: 'answers' | 'graph' | 'eval';
  sidebarOpen: boolean;
  uploadZoneActive: boolean;
  currentQuery: string;
  isProcessing: boolean;
  searchResults: import('./search').SearchResult | null;
  selectedDocument: import('./document').Document | null;
  selectedEntity: import('./search').Entity | null;
  filters: {
    documents: import('./document').DocumentFilters;
    search: import('./search').SearchRequest['filters'];
    graph: import('./knowledge-graph').GraphFilters;
  };
  viewSettings: {
    theme: 'light' | 'dark' | 'auto';
    language: string;
    results_per_page: number;
    auto_refresh: boolean;
  };
}

export interface LayoutConfig {
  panels: {
    left: {
      width: number; // pixels or percentage
      collapsible: boolean;
      components: string[];
    };
    right: {
      width: number;
      collapsible: boolean;
      components: string[];
    };
  };
  responsive: {
    mobile: boolean;
    tablet: boolean;
    desktop: boolean;
  };
}

export interface ComponentState {
  isLoading: boolean;
  error: string | null;
  data: any;
  lastUpdated: string;
}

// WebSocket Message Types
export interface WebSocketMessage {
  type: string;
  payload: any;
  timestamp: string;
  user_id?: string;
  organization_id?: string;
}

// Document Processing Update
export interface DocumentProcessingUpdate extends WebSocketMessage {
  type: 'document_processing_update';
  payload: {
    job_id: string;
    document_id: string;
    status: import('./document').Document['processing_status'];
    progress: number;
    current_step: string;
    estimated_remaining_seconds?: number;
    error_message?: string;
  };
}

// Query Status Update
export interface QueryStatusUpdate extends WebSocketMessage {
  type: 'query_status_update';
  payload: {
    query_id: string;
    status: 'processing' | 'completed' | 'failed';
    progress: number;
    current_step: string;
    result?: import('./search').SearchResult;
    error_message?: string;
  };
}

// System Notification
export interface SystemNotification extends WebSocketMessage {
  type: 'system_notification';
  payload: {
    level: 'info' | 'warning' | 'error';
    title: string;
    message: string;
    action_url?: string;
    persistent: boolean;
  };
}

