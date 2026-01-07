/**
 * Processing Components Index
 *
 * Exports all real-time document processing components
 */

export { default as ProcessingDashboard } from './ProcessingDashboard';
// Note: Components below require type fixes - commented out for strict mode
// export { default as RealtimeStatusDashboard } from './RealtimeStatusDashboard';
export { default as DocumentProgressVisualizer } from './DocumentProgressVisualizer';
// export { default as NotificationCenter } from './NotificationCenter';
// export { default as ConnectionManager } from './ConnectionManager';
// export { default as PerformanceMonitor } from './PerformanceMonitor';

// Re-export hooks
// Note: useRealtimeProcessing requires type fixes - commented out for strict mode
// export { useRealtimeProcessing, useDocumentStatus, useConnectionStatus } from '@/hooks/useRealtimeProcessing';
// export { useNotificationCenter } from './NotificationCenter';

// Re-export types
export type {
  DocumentProcessingState,
  ProcessingStage,
  WebSocketConnectionState,
  NotificationItem,
  RealtimeProcessingState,
  WebSocketMessage,
  DocumentUpdateMessage,
  QueueUpdateMessage,
  SystemMetricsMessage,
  NotificationMessage,
  ConnectionStatusMessage,
} from '@/types/realtime-processing';