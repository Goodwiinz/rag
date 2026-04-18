/**
 * React Hook for Real-time Document Processing
 *
 * Provides a comprehensive hook for managing real-time document processing
 * with WebSocket integration, state management, and performance optimization.
 */

import { useEffect, useCallback, useRef, useState } from 'react';
import { useAuth } from './useAuth';
import { createClient } from '@/lib/supabase/client';
import { useRealtimeProcessingStore } from '@/store/realtimeProcessingStore';
import { getRealtimeWebSocketService } from '@/services/realtimeWebSocketService';
import {
  WebSocketMessage,
  DocumentUpdateMessage,
  QueueUpdateMessage,
  SystemMetricsMessage,
  NotificationMessage,
  DocumentProcessingState,
  PerformanceMetrics,
  WebSocketConnectionState,
} from '@/types/realtime-processing';

interface UseRealtimeProcessingOptions {
  autoConnect?: boolean;
  documentIds?: string[];
  enablePerformanceMonitoring?: boolean;
  maxRetries?: number;
  reconnectInterval?: number;
}

interface UseRealtimeProcessingReturn {
  // Connection state
  connectionStatus: WebSocketConnectionState['status'];
  isConnected: boolean;
  error: string | null;

  // Data
  documents: DocumentProcessingState[];
  systemMetrics: PerformanceMetrics;

  // Actions
  connect: () => Promise<void>;
  disconnect: () => void;
  reconnect: () => Promise<void>;

  // Document management
  subscribeToDocuments: (documentIds: string[]) => void;
  unsubscribeFromDocuments: (documentIds: string[]) => void;
  pauseDocument: (documentId: string) => void;
  resumeDocument: (documentId: string) => void;
  cancelDocument: (documentId: string) => void;
  retryDocument: (documentId: string) => void;

  // Bulk actions
  pauseSelectedDocuments: () => void;
  resumeSelectedDocuments: () => void;
  cancelSelectedDocuments: () => void;
  retrySelectedDocuments: () => void;

  // Performance
  connectionLatency: number;
  messageRate: number;

  // Utilities
  clearNotifications: () => void;
  retryConnection: () => Promise<void>;
}

export const useRealtimeProcessing = (
  options: UseRealtimeProcessingOptions = {}
): UseRealtimeProcessingReturn => {
  const {
    autoConnect = true,
    documentIds = [],
    enablePerformanceMonitoring = true,
    maxRetries = 5,
    reconnectInterval = 2000,
  } = options;

  const { isAuthenticated } = useAuth();
  const store = useRealtimeProcessingStore();
  const wsServiceRef = useRef(getRealtimeWebSocketService());
  const [connectionLatency, setConnectionLatency] = useState(0);
  const [messageRate, setMessageRate] = useState(0);
  const [error, setError] = useState<string | null>(null);

  // Message handlers
  const handleDocumentUpdate = useCallback(
    (message: DocumentUpdateMessage) => {
      const { payload } = message;

      // Update document in store
      if (payload.progress !== undefined) {
        store.updateDocument(payload.documentId, {
          overallProgress: payload.progress,
          currentStage: payload.currentStage,
          status: payload.status,
          error: payload.error,
        });
      }

      // Show notification for status changes
      if (payload.status === 'completed') {
        store.addNotification({
          type: 'success',
          title: 'Document Processed',
          message: `Document has been successfully processed`,
          documentId: payload.documentId,
          autoHide: true,
          autoHideDelay: 5000,
        });
      } else if (payload.status === 'failed' && payload.error) {
        store.addNotification({
          type: 'error',
          title: 'Processing Failed',
          message: payload.error,
          documentId: payload.documentId,
          autoHide: false,
        });
      }
    },
    [store]
  );

  const handleQueueUpdate = useCallback(
    (message: QueueUpdateMessage) => {
      const { payload } = message;

      // Update queue summary and metrics
      store.setQueueSummary(payload.summary);
      store.setQueueMetrics(payload.metrics);
    },
    [store]
  );

  const handleSystemMetrics = useCallback(
    (message: SystemMetricsMessage) => {
      store.updateSystemMetrics(message.payload);
    },
    [store]
  );

  const handleNotification = useCallback(
    (message: NotificationMessage) => {
      store.addNotification(message.payload);
    },
    [store]
  );

  const handleConnectionChange = useCallback(
    (connectionState: WebSocketConnectionState) => {
      store.setConnectionStatus(connectionState.status);
      store.updateConnectionState(connectionState);

      if (connectionState.status === 'error' && connectionState.lastError) {
        setError(connectionState.lastError);
      } else {
        setError(null);
      }
    },
    [store]
  );

  const handlePerformanceUpdate = useCallback((metrics: PerformanceMetrics) => {
    setConnectionLatency(metrics.connectionLatency);
    setMessageRate(metrics.messageRate);
  }, []);

  // Connection management
  const connect = useCallback(async () => {
    if (!isAuthenticated) {
      return;
    }

    // Get token from Supabase session
    const supabase = createClient();
    const {
      data: { session },
    } = await supabase.auth.getSession();
    const accessToken = session?.access_token;
    if (!accessToken) return;

    const wsService = wsServiceRef.current;

    try {
      await wsService.connect(accessToken);

      // Set up message handlers
      wsService.subscribe('document_update', handleDocumentUpdate);
      wsService.subscribe('queue_update', handleQueueUpdate);
      wsService.subscribe('system_metrics', handleSystemMetrics);
      wsService.subscribe('notification', handleNotification);
      wsService.onConnectionChange(handleConnectionChange);
      wsService.onPerformanceUpdate(handlePerformanceUpdate);

      // Subscribe to specific documents if provided
      if (documentIds.length > 0) {
        wsService.requestDocumentUpdates(documentIds);
      }
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to connect';
      setError(errorMessage);
      console.error('WebSocket connection failed:', err);
    }
  }, [
    isAuthenticated,
    documentIds,
    handleDocumentUpdate,
    handleQueueUpdate,
    handleSystemMetrics,
    handleNotification,
    handleConnectionChange,
    handlePerformanceUpdate,
  ]);

  const disconnect = useCallback(() => {
    const wsService = wsServiceRef.current;
    wsService.disconnect();
  }, []);

  const reconnect = useCallback(async () => {
    disconnect();
    await new Promise((resolve) => setTimeout(resolve, 1000)); // Brief delay
    await connect();
  }, [disconnect, connect]);

  // Document management actions
  const subscribeToDocuments = useCallback((documentIds: string[]) => {
    const wsService = wsServiceRef.current;
    wsService.requestDocumentUpdates(documentIds);
  }, []);

  const unsubscribeFromDocuments = useCallback((documentIds: string[]) => {
    const wsService = wsServiceRef.current;
    wsService.send({
      type: 'unsubscribe_documents',
      payload: { document_ids: documentIds },
      timestamp: new Date().toISOString(),
    });
  }, []);

  const pauseDocument = useCallback((documentId: string) => {
    const wsService = wsServiceRef.current;
    wsService.send({
      type: 'pause_document',
      payload: { document_id: documentId },
      timestamp: new Date().toISOString(),
    });
  }, []);

  const resumeDocument = useCallback((documentId: string) => {
    const wsService = wsServiceRef.current;
    wsService.send({
      type: 'resume_document',
      payload: { document_id: documentId },
      timestamp: new Date().toISOString(),
    });
  }, []);

  const cancelDocument = useCallback((documentId: string) => {
    const wsService = wsServiceRef.current;
    wsService.send({
      type: 'cancel_document',
      payload: { document_id: documentId },
      timestamp: new Date().toISOString(),
    });
  }, []);

  const retryDocument = useCallback((documentId: string) => {
    const wsService = wsServiceRef.current;
    wsService.send({
      type: 'retry_document',
      payload: { document_id: documentId },
      timestamp: new Date().toISOString(),
    });
  }, []);

  // Bulk actions using store methods
  const pauseSelectedDocuments = useCallback(() => {
    store.pauseSelectedDocuments();
  }, [store]);

  const resumeSelectedDocuments = useCallback(() => {
    store.resumeSelectedDocuments();
  }, [store]);

  const cancelSelectedDocuments = useCallback(() => {
    store.cancelSelectedDocuments();
  }, [store]);

  const retrySelectedDocuments = useCallback(() => {
    store.retrySelectedDocuments();
  }, [store]);

  // Utilities
  const clearNotifications = useCallback(() => {
    store.clearNotifications();
  }, [store]);

  const retryConnection = useCallback(async () => {
    store.incrementReconnectionAttempts();
    await reconnect();
  }, [store, reconnect]);

  // Auto-connect when authenticated
  useEffect(() => {
    if (autoConnect && isAuthenticated) {
      connect();
    }

    return () => {
      if (autoConnect) {
        disconnect();
      }
    };
  }, [autoConnect, isAuthenticated, connect, disconnect]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      const wsService = wsServiceRef.current;
      // Don't destroy the service, just disconnect
      wsService.disconnect();
    };
  }, []);

  // Get data from store
  const connectionStatus = useRealtimeProcessingStore(
    (state) => state.connection.status
  );
  const documents = useRealtimeProcessingStore(
    (state) => state.queue.documents
  );
  const systemMetrics = useRealtimeProcessingStore(
    (state) => state.systemMetrics
  );

  return {
    // Connection state
    connectionStatus,
    isConnected: connectionStatus === 'connected',
    error,

    // Data
    documents,
    systemMetrics,

    // Actions
    connect,
    disconnect,
    reconnect,

    // Document management
    subscribeToDocuments,
    unsubscribeFromDocuments,
    pauseDocument,
    resumeDocument,
    cancelDocument,
    retryDocument,

    // Bulk actions
    pauseSelectedDocuments,
    resumeSelectedDocuments,
    cancelSelectedDocuments,
    retrySelectedDocuments,

    // Performance
    connectionLatency,
    messageRate,

    // Utilities
    clearNotifications,
    retryConnection,
  };
};

// Hook for document-specific updates
export const useDocumentStatus = (documentId: string) => {
  const documents = useRealtimeProcessingStore((state) =>
    state.queue.documents.filter((doc) => doc.id === documentId)
  );

  const document = documents[0];

  const pauseDocument = useCallback(() => {
    const wsService = getRealtimeWebSocketService();
    wsService.send({
      type: 'pause_document',
      payload: { document_id: documentId },
      timestamp: new Date().toISOString(),
    });
  }, [documentId]);

  const resumeDocument = useCallback(() => {
    const wsService = getRealtimeWebSocketService();
    wsService.send({
      type: 'resume_document',
      payload: { document_id: documentId },
      timestamp: new Date().toISOString(),
    });
  }, [documentId]);

  const cancelDocument = useCallback(() => {
    const wsService = getRealtimeWebSocketService();
    wsService.send({
      type: 'cancel_document',
      payload: { document_id: documentId },
      timestamp: new Date().toISOString(),
    });
  }, [documentId]);

  const retryDocument = useCallback(() => {
    const wsService = getRealtimeWebSocketService();
    wsService.send({
      type: 'retry_document',
      payload: { document_id: documentId },
      timestamp: new Date().toISOString(),
    });
  }, [documentId]);

  return {
    document,
    pauseDocument,
    resumeDocument,
    cancelDocument,
    retryDocument,
  };
};

// Hook for connection status
export const useConnectionStatus = () => {
  const connectionStatus = useRealtimeProcessingStore(
    (state) => state.connection.status
  );
  const reconnectionAttempts = useRealtimeProcessingStore(
    (state) => state.connection.reconnectionAttempts
  );
  const maxReconnectionAttempts = useRealtimeProcessingStore(
    (state) => state.connection.maxReconnectionAttempts
  );
  const lastError = useRealtimeProcessingStore(
    (state) => state.connection.lastError
  );

  return {
    status: connectionStatus,
    isConnected: connectionStatus === 'connected',
    isConnecting:
      connectionStatus === 'connecting' || connectionStatus === 'reconnecting',
    isDisconnected: connectionStatus === 'disconnected',
    hasError: connectionStatus === 'error',
    reconnectionAttempts,
    maxReconnectionAttempts,
    lastError,
  };
};

export default useRealtimeProcessing;
