import React, {
  createContext,
  useContext,
  useEffect,
  useRef,
  useCallback,
  useMemo,
} from 'react';
import { useRealtimeProcessingStore } from '@/store/realtimeProcessingStore';
import { useAuth } from '@/hooks/useAuth';
import { createClient } from '@/lib/supabase/client';
import { WebSocketManager } from '@/services/websocket';
import { getPublicWebSocketOrigin } from '@/utils/publicEndpoints';
import {
  DocumentUpdateMessage,
  QueueUpdateMessage,
  SystemMetricsMessage,
  NotificationMessage,
  WebSocketMessage,
} from '@/types/realtime-processing';
import { toast } from 'react-hot-toast';

interface RealtimeProcessingContextType {
  isConnected: boolean;
  reconnect: () => Promise<void>;
  disconnect: () => void;
  manager: WebSocketManager | null;
}

const RealtimeProcessingContext =
  createContext<RealtimeProcessingContextType | null>(null);

export const useRealtimeProcessing = () => {
  const context = useContext(RealtimeProcessingContext);
  if (!context) {
    throw new Error(
      'useRealtimeProcessing must be used within RealtimeProcessingProvider'
    );
  }
  return context;
};

interface RealtimeProcessingProviderProps {
  children: React.ReactNode;
  wsUrl?: string;
  autoConnect?: boolean;
}

export const RealtimeProcessingProvider: React.FC<
  RealtimeProcessingProviderProps
> = ({
  children,
  wsUrl = `${getPublicWebSocketOrigin()}/ws`,
  autoConnect = true,
}) => {
  const { user, isAuthenticated } = useAuth();
  const managerRef = useRef<WebSocketManager | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();

  const {
    setConnectionStatus,
    updateConnectionState,
    incrementReconnectionAttempts,
    resetConnectionState,
    addDocument,
    updateDocument,
    updateDocuments,
    setQueueSummary,
    setQueueMetrics,
    updateSystemMetrics,
    addNotification,
    updatePreferences,
  } = useRealtimeProcessingStore();

  // Initialize WebSocket connection
  const connect = useCallback(async () => {
    if (!user || !isAuthenticated) {
      return;
    }

    // Get token from Supabase session
    const supabase = createClient();
    const {
      data: { session },
    } = await supabase.auth.getSession();
    const token = session?.access_token;
    if (!token) return;

    try {
      setConnectionStatus('connecting');

      const manager = new WebSocketManager(wsUrl, token, user.organization_id);
      managerRef.current = manager;

      // Set up event handlers
      manager.on('connected', () => {
        setConnectionStatus('connected');
        updateConnectionState({
          lastConnectedAt: new Date().toISOString(),
          lastError: undefined,
          reconnectionAttempts: 0,
        });
        toast.success('Connected to real-time processing server');
      });

      manager.on('disconnected', () => {
        setConnectionStatus('disconnected');
        toast.error('Disconnected from processing server');
      });

      manager.on('error', (error) => {
        setConnectionStatus('error');
        updateConnectionState({
          lastError: error.message,
          reconnectionAttempts: manager.getReconnectionAttempts(),
        });
        toast.error(`WebSocket error: ${error.message}`);
      });

      manager.on('reconnecting', () => {
        setConnectionStatus('reconnecting');
        incrementReconnectionAttempts();
      });

      // Handle different message types
      manager.on('document_update', handleDocumentUpdate);
      manager.on('queue_update', handleQueueUpdate);
      manager.on('system_metrics', handleSystemMetrics);
      manager.on('notification', handleNotification);

      await manager.connect();
    } catch (error) {
      console.error('Failed to connect WebSocket:', error);
      setConnectionStatus('error');
      updateConnectionState({
        lastError: error instanceof Error ? error.message : 'Connection failed',
      });
    }
  }, [
    user,
    isAuthenticated,
    wsUrl,
    setConnectionStatus,
    updateConnectionState,
    incrementReconnectionAttempts,
  ]);

  // Handle document update messages
  const handleDocumentUpdate = useCallback(
    (data: DocumentUpdateMessage) => {
      const { documentId, progress, currentStage, status, error } =
        data.payload;

      updateDocument(documentId, {
        overallProgress: progress,
        currentStage,
        status,
        error,
        metadata: {
          ...data.payload.metadata,
          // Update timestamp if provided
          ...(data.payload.metadata?.processingStartedAt && {
            processingStartedAt: data.payload.metadata.processingStartedAt,
          }),
          ...(data.payload.metadata?.completedAt && {
            completedAt: data.payload.metadata.completedAt,
          }),
        },
      });

      // Show completion notification
      if (status === 'completed') {
        toast.success(
          `Document processing completed: ${data.payload.filename}`
        );
        addNotification({
          type: 'success',
          title: 'Processing Complete',
          message: `Successfully processed ${data.payload.filename}`,
          documentId,
          autoHide: true,
          autoHideDelay: 5000,
        });
      }

      // Show error notification
      if (status === 'failed' && error) {
        toast.error(`Processing failed: ${data.payload.filename}`);
        addNotification({
          type: 'error',
          title: 'Processing Failed',
          message: `Failed to process ${data.payload.filename}: ${error}`,
          documentId,
          autoHide: false,
        });
      }
    },
    [updateDocument, addNotification]
  );

  // Handle queue update messages
  const handleQueueUpdate = useCallback(
    (data: QueueUpdateMessage) => {
      const { summary, metrics } = data.payload;
      setQueueSummary(summary);
      setQueueMetrics(metrics);
    },
    [setQueueSummary, setQueueMetrics]
  );

  // Handle system metrics messages
  const handleSystemMetrics = useCallback(
    (data: SystemMetricsMessage) => {
      updateSystemMetrics(data.payload);
    },
    [updateSystemMetrics]
  );

  // Handle notification messages
  const handleNotification = useCallback(
    (data: NotificationMessage) => {
      const { type, title, message, autoHide = true } = data.payload;

      // Show toast notification
      switch (type) {
        case 'success':
          toast.success(message);
          break;
        case 'error':
          toast.error(message);
          break;
        case 'warning':
          toast.warning(message);
          break;
        default:
          toast(message);
      }

      // Add to notification center
      addNotification({
        ...data.payload,
        autoHide,
        autoHideDelay: data.payload.autoHideDelay || 5000,
      });
    },
    [addNotification]
  );

  // Disconnect WebSocket
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }

    if (managerRef.current) {
      managerRef.current.disconnect();
      managerRef.current = null;
    }

    resetConnectionState();
  }, [resetConnectionState]);

  // Manual reconnect
  const reconnect = useCallback(async () => {
    disconnect();
    await connect();
  }, [disconnect, connect]);

  // Auto-connect when authenticated
  useEffect(() => {
    if (autoConnect && isAuthenticated && user) {
      connect();
    } else if (!isAuthenticated) {
      disconnect();
    }

    return () => {
      disconnect();
    };
  }, [autoConnect, isAuthenticated, user, connect, disconnect]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  // Connection status for context
  const connectionStatus = useRealtimeProcessingStore(
    (state) => state.connection.status
  );
  const isConnected = connectionStatus === 'connected';

  const contextValue = useMemo<RealtimeProcessingContextType>(
    () => ({
      isConnected,
      reconnect,
      disconnect,
      manager: managerRef.current,
    }),
    [isConnected, reconnect, disconnect]
  );

  return (
    <RealtimeProcessingContext.Provider value={contextValue}>
      {children}
    </RealtimeProcessingContext.Provider>
  );
};

// HOC for components that need real-time processing
export const withRealtimeProcessing = <P extends object>(
  Component: React.ComponentType<P>
) => {
  const WrappedComponent = (props: P) => (
    <RealtimeProcessingProvider>
      <Component {...props} />
    </RealtimeProcessingProvider>
  );

  WrappedComponent.displayName = `withRealtimeProcessing(${Component.displayName || Component.name})`;
  return WrappedComponent;
};

export default RealtimeProcessingProvider;
