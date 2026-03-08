import { useEffect, useState, useCallback, useRef } from 'react';
import { useAuth } from './useAuth';
import {
  WebSocketManager,
  getWebSocketManager,
  initializeWebSocket,
  cleanupWebSocket,
  WebSocketEventHandler,
  DocumentProcessingUpdate,
  QueryStatusUpdate,
  SystemNotification,
} from '@/services/websocket';
import { UI_CONFIG } from '@/types';

interface UseWebSocketReturn {
  isConnected: boolean;
  status: 'connecting' | 'connected' | 'disconnected' | 'error';
  manager: WebSocketManager | null;
  error: string | null;
  reconnect: () => Promise<void>;
  disconnect: () => void;
}

export const useWebSocket = (): UseWebSocketReturn => {
  const { token, user, isAuthenticated } = useAuth();
  const [status, setStatus] = useState<
    'connecting' | 'connected' | 'disconnected' | 'error'
  >('disconnected');
  const [error, setError] = useState<string | null>(null);
  const managerRef = useRef<WebSocketManager | null>(null);

  const connect = useCallback(async () => {
    if (!token || !user || !isAuthenticated) {
      return;
    }

    try {
      const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws';

      // Initialize or get existing manager
      const manager =
        getWebSocketManager() ||
        initializeWebSocket(wsUrl, token, user.organization_id);

      managerRef.current = manager;

      // Set up event listeners
      const handleConnected = () => {
        setStatus('connected');
        setError(null);
      };

      const handleDisconnected = () => {
        setStatus('disconnected');
      };

      const handleError = (data: any) => {
        setStatus('error');
        setError(data.error?.message || 'WebSocket connection error');
      };

      manager.on('connected', handleConnected);
      manager.on('disconnected', handleDisconnected);
      manager.on('error', handleError);

      // Update initial status
      setStatus(manager.getStatus());

      // Connect if not already connected
      if (!manager.isConnected()) {
        await manager.connect();
      }
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to connect WebSocket';
      setError(errorMessage);
      setStatus('error');
    }
  }, [token, user, isAuthenticated]);

  const disconnect = useCallback(() => {
    if (managerRef.current) {
      managerRef.current.disconnect();
      managerRef.current = null;
    }
    setStatus('disconnected');
    setError(null);
  }, []);

  const reconnect = useCallback(async () => {
    disconnect();
    await connect();
  }, [disconnect, connect]);

  // Auto-connect when authentication is available
  useEffect(() => {
    if (isAuthenticated && token && user) {
      connect();
    } else {
      disconnect();
    }

    return () => {
      // Cleanup on unmount
      const manager = managerRef.current;
      if (manager) {
        manager.off('connected');
        manager.off('disconnected');
        manager.off('error');
      }
    };
  }, [isAuthenticated, token, user, connect, disconnect]);

  // Update connection parameters when token changes
  useEffect(() => {
    const manager = managerRef.current;
    if (manager && token && user) {
      manager.updateConnectionParams(token, user.organization_id);
    }
  }, [token, user]);

  return {
    isConnected: status === 'connected',
    status,
    manager: managerRef.current,
    error,
    reconnect,
    disconnect,
  };
};

// Hook for document processing updates
export const useDocumentProcessingUpdates = () => {
  const { manager } = useWebSocket();
  const [updates, setUpdates] = useState<DocumentProcessingUpdate[]>([]);

  useEffect(() => {
    if (!manager) return;

    const handleUpdate = (data: DocumentProcessingUpdate) => {
      setUpdates((prev) => {
        // Update existing or add new
        const index = prev.findIndex(
          (u) => u.payload.job_id === data.payload.job_id
        );
        if (index >= 0) {
          const updated = [...prev];
          updated[index] = data;
          return updated;
        }
        return [...prev, data];
      });
    };

    manager.on('document_processing_update', handleUpdate);

    return () => {
      manager.off('document_processing_update', handleUpdate);
    };
  }, [manager]);

  const clearUpdates = useCallback(() => {
    setUpdates([]);
  }, []);

  return { updates, clearUpdates };
};

// Hook for query status updates
export const useQueryStatusUpdates = () => {
  const { manager } = useWebSocket();
  const [queryUpdates, setQueryUpdates] = useState<QueryStatusUpdate[]>([]);

  useEffect(() => {
    if (!manager) return;

    const handleUpdate = (data: QueryStatusUpdate) => {
      setQueryUpdates((prev) => {
        // Update existing or add new
        const index = prev.findIndex(
          (u) => u.payload.query_id === data.payload.query_id
        );
        if (index >= 0) {
          const updated = [...prev];
          updated[index] = data;
          return updated;
        }
        return [...prev, data];
      });
    };

    manager.on('query_status_update', handleUpdate);

    return () => {
      manager.off('query_status_update', handleUpdate);
    };
  }, [manager]);

  const clearQueryUpdates = useCallback(() => {
    setQueryUpdates([]);
  }, []);

  return { queryUpdates, clearQueryUpdates };
};

// Hook for system notifications
export const useSystemNotifications = () => {
  const { manager } = useWebSocket();
  const [notifications, setNotifications] = useState<SystemNotification[]>([]);

  useEffect(() => {
    if (!manager) return;

    const handleNotification = (data: SystemNotification) => {
      setNotifications((prev) => [...prev, data]);

      // Auto-remove non-persistent notifications after 5 seconds
      if (!data.payload.persistent) {
        setTimeout(() => {
          setNotifications((prev) => prev.filter((n) => n !== data));
        }, 5000);
      }
    };

    manager.on('system_notification', handleNotification);

    return () => {
      manager.off('system_notification', handleNotification);
    };
  }, [manager]);

  const clearNotification = useCallback((notification: SystemNotification) => {
    setNotifications((prev) => prev.filter((n) => n !== notification));
  }, []);

  const clearAllNotifications = useCallback(() => {
    setNotifications([]);
  }, []);

  return { notifications, clearNotification, clearAllNotifications };
};

export default useWebSocket;
