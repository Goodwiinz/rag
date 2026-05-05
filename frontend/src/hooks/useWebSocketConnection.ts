import { useEffect, useRef, useCallback } from 'react';
import { useRealtimeProcessingStore } from '@/store/realtimeProcessingStore';
import {
  WebSocketMessage,
  DocumentUpdateMessage,
  QueueUpdateMessage,
  SystemMetricsMessage,
  NotificationMessage,
  ConnectionStatusMessage,
} from '@/types/realtime-processing';

interface UseWebSocketConnectionProps {
  url: string;
  token?: string;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
  heartbeatInterval?: number;
  enableHeartbeat?: boolean;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
}

const DEFAULT_RECONNECT_INTERVAL = 2000;
const DEFAULT_MAX_RECONNECT_ATTEMPTS = 5;
const DEFAULT_HEARTBEAT_INTERVAL = 30000; // 30 seconds
const CONNECTION_TIMEOUT = 10000; // 10 seconds

export const useWebSocketConnection = ({
  url,
  token,
  reconnectInterval = DEFAULT_RECONNECT_INTERVAL,
  maxReconnectAttempts = DEFAULT_MAX_RECONNECT_ATTEMPTS,
  heartbeatInterval = DEFAULT_HEARTBEAT_INTERVAL,
  enableHeartbeat = true,
  onConnect,
  onDisconnect,
  onError,
}: UseWebSocketConnectionProps) => {
  const wsRef = useRef<WebSocket | null>(null);
  const heartbeatTimeoutRef = useRef<ReturnType<typeof setTimeout>>();
  const heartbeatIntervalRef = useRef<ReturnType<typeof setInterval>>();
  const connectionTimeoutRef = useRef<ReturnType<typeof setTimeout>>();
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout>>();
  const lastPingRef = useRef<number>(0);

  const {
    connection,
    setConnectionStatus,
    updateConnectionState,
    incrementReconnectionAttempts,
    resetConnectionState,
    updateDocument,
    setQueueSummary,
    setQueueMetrics,
    updateSystemMetrics,
    addNotification,
  } = useRealtimeProcessingStore();

  // Clear all timers (timeouts + intervals)
  const clearTimeouts = useCallback(() => {
    if (heartbeatTimeoutRef.current) {
      clearTimeout(heartbeatTimeoutRef.current);
    }
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = undefined;
    }
    if (connectionTimeoutRef.current) {
      clearTimeout(connectionTimeoutRef.current);
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
  }, []);

  // Handle incoming WebSocket messages
  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const message: WebSocketMessage = JSON.parse(event.data);

      // Update latency based on timestamp if available
      if (message.timestamp) {
        const now = Date.now();
        const messageTime = new Date(message.timestamp).getTime();
        const latency = now - messageTime;
        updateConnectionState({ latency });
      }

      switch (message.type) {
        case 'document_update': {
          const docMessage = message as DocumentUpdateMessage;
          updateDocument(docMessage.documentId, {
            overallProgress: docMessage.payload.progress,
            currentStage: docMessage.payload.currentStage,
            status: docMessage.payload.status,
            error: docMessage.payload.error,
          });
          break;
        }

        case 'queue_update': {
          const queueMessage = message as QueueUpdateMessage;
          setQueueSummary(queueMessage.payload.summary);
          setQueueMetrics(queueMessage.payload.metrics);
          break;
        }

        case 'system_metrics': {
          const metricsMessage = message as SystemMetricsMessage;
          updateSystemMetrics(metricsMessage.payload);
          break;
        }

        case 'notification': {
          const notificationMessage = message as NotificationMessage;
          addNotification(notificationMessage.payload);
          break;
        }

        case 'connection_status': {
          const statusMessage = message as ConnectionStatusMessage;
          setConnectionStatus(statusMessage.payload.status);
          if (statusMessage.payload.message) {
            addNotification({
              type: statusMessage.payload.status === 'connected' ? 'success' : 'warning',
              title: 'Connection Status',
              message: statusMessage.payload.message,
              timestamp: new Date().toISOString(),
              autoHide: true,
              autoHideDelay: 5000,
            });
          }
          break;
        }

        case 'pong': {
          // Handle heartbeat response
          const now = Date.now();
          const rtt = now - lastPingRef.current;
          updateConnectionState({ latency: rtt });
          break;
        }

        default:
          console.warn('Unknown WebSocket message type:', message.type);
      }
    } catch (error) {
      console.error('Error parsing WebSocket message:', error);
    }
  }, [updateDocument, setQueueSummary, setQueueMetrics, updateSystemMetrics, addNotification, updateConnectionState, setConnectionStatus]);

  // Send heartbeat ping
  const sendPing = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      lastPingRef.current = Date.now();
      const pingMessage: WebSocketMessage = {
        type: 'ping',
        payload: { timestamp: new Date().toISOString() },
        timestamp: new Date().toISOString(),
      };
      wsRef.current.send(JSON.stringify(pingMessage));

      // Set timeout for pong response
      heartbeatTimeoutRef.current = setTimeout(() => {
        console.warn('Heartbeat timeout - no pong received');
        if (wsRef.current) {
          wsRef.current.close();
        }
      }, heartbeatInterval);
    }
  }, [heartbeatInterval]);

  // Start heartbeat interval
  const startHeartbeat = useCallback(() => {
    if (enableHeartbeat && wsRef.current?.readyState === WebSocket.OPEN) {
      // Clear any existing heartbeat interval to prevent leaks on reconnect
      if (heartbeatIntervalRef.current) {
        clearInterval(heartbeatIntervalRef.current);
      }

      // Send initial ping
      sendPing();

      // Set up interval in a separate ref so it can be cleared independently
      // of the pong timeout stored in heartbeatTimeoutRef
      heartbeatIntervalRef.current = setInterval(sendPing, heartbeatInterval);
    }
  }, [enableHeartbeat, heartbeatInterval, sendPing]);

  // Connect to WebSocket
  const connect = useCallback(() => {
    try {
      clearTimeouts();
      setConnectionStatus('connecting');

      const wsUrl = token ? `${url}?token=${encodeURIComponent(token)}` : url;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      // Connection timeout
      connectionTimeoutRef.current = setTimeout(() => {
        if (ws.readyState === WebSocket.CONNECTING) {
          ws.close();
          setConnectionStatus('error');
          updateConnectionState({ lastError: 'Connection timeout' });
        }
      }, CONNECTION_TIMEOUT);

      ws.onopen = () => {
        clearTimeout(connectionTimeoutRef.current);
        console.log('WebSocket connected');
        setConnectionStatus('connected');
        resetConnectionState();
        startHeartbeat();
        onConnect?.();
      };

      ws.onmessage = handleMessage;

      ws.onclose = (event) => {
        clearTimeouts();
        console.log('WebSocket disconnected:', event.code, event.reason);
        setConnectionStatus('disconnected');
        onDisconnect?.();

        // Attempt reconnection if not a normal close and we haven't exceeded max attempts
        if (event.code !== 1000 && connection.reconnectionAttempts < maxReconnectAttempts) {
          incrementReconnectionAttempts();
          const delay = Math.min(reconnectInterval * Math.pow(2, connection.reconnectionAttempts), 30000);

          reconnectTimeoutRef.current = setTimeout(() => {
            console.log(`Attempting to reconnect... (${connection.reconnectionAttempts + 1}/${maxReconnectAttempts})`);
            connect();
          }, delay);
        }
      };

      ws.onerror = (error) => {
        clearTimeouts();
        console.error('WebSocket error:', error);
        setConnectionStatus('error');
        updateConnectionState({ lastError: error.toString() });
        onError?.(error);
      };

    } catch (error) {
      console.error('Error creating WebSocket connection:', error);
      setConnectionStatus('error');
      updateConnectionState({ lastError: error.toString() });
    }
  }, [
    url,
    token,
    reconnectInterval,
    maxReconnectAttempts,
    enableHeartbeat,
    heartbeatInterval,
    onConnect,
    onDisconnect,
    onError,
    setConnectionStatus,
    updateConnectionState,
    resetConnectionState,
    incrementReconnectionAttempts,
    startHeartbeat,
    handleMessage,
    clearTimeouts,
    connection.reconnectionAttempts,
  ]);

  // Disconnect WebSocket
  const disconnect = useCallback(() => {
    clearTimeouts();
    if (wsRef.current) {
      wsRef.current.close(1000, 'User disconnected');
      wsRef.current = null;
    }
    setConnectionStatus('disconnected');
  }, [clearTimeouts, setConnectionStatus]);

  // Send message to WebSocket
  const sendMessage = useCallback((message: Omit<WebSocketMessage, 'timestamp'>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      const fullMessage: WebSocketMessage = {
        ...message,
        timestamp: new Date().toISOString(),
      };
      wsRef.current.send(JSON.stringify(fullMessage));
      return true;
    } else {
      console.warn('Cannot send message - WebSocket not connected');
      return false;
    }
  }, []);

  // Manual reconnection
  const reconnect = useCallback(() => {
    resetConnectionState();
    connect();
  }, [resetConnectionState, connect]);

  // Initialize connection on mount
  useEffect(() => {
    connect();

    return () => {
      clearTimeouts();
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect, clearTimeouts]);

  // Handle visibility change (pause/resume when tab becomes visible/hidden)
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden) {
        // Pause heartbeat when tab is hidden
        if (heartbeatTimeoutRef.current) {
          clearInterval(heartbeatTimeoutRef.current);
        }
      } else {
        // Resume heartbeat and check connection when tab becomes visible
        if (wsRef.current?.readyState !== WebSocket.OPEN) {
          reconnect();
        } else {
          startHeartbeat();
        }
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [reconnect, startHeartbeat]);

  return {
    connection,
    connect,
    disconnect,
    reconnect,
    sendMessage,
    isConnected: connection.status === 'connected',
    isConnecting: connection.status === 'connecting',
    isReconnecting: connection.status === 'reconnecting',
    hasError: connection.status === 'error',
  };
};