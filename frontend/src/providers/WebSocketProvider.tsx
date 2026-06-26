import React, { createContext, useContext, useMemo, ReactNode } from 'react';
import { useWebSocketConnection } from '@/hooks/useWebSocketConnection';
import { useRealtimeProcessingStore } from '@/store/realtimeProcessingStore';
import type { WebSocketMessage } from '@/types/realtime-processing';

interface WebSocketContextType {
  connection: ReturnType<typeof useWebSocketConnection>;
  sendMessage: (message: Omit<WebSocketMessage, 'timestamp'>) => boolean;
  isReady: boolean;
}

const WebSocketContext = createContext<WebSocketContextType | null>(null);

interface WebSocketProviderProps {
  children: ReactNode;
  wsUrl: string;
  authToken?: string;
}

export const WebSocketProvider: React.FC<WebSocketProviderProps> = ({
  children,
  wsUrl,
  authToken,
}) => {
  const { preferences } = useRealtimeProcessingStore();

  // Destructure the stable pieces returned by the hook so the context value
  // can be memoized. The hook returns a fresh object literal every render, so
  // memoizing on that object (as before) never held — every consumer re-rendered
  // on every parent render. The individual callbacks are stable useCallbacks and
  // the connection slice only changes when connection state actually changes.
  const {
    connection: wsConnection,
    connect,
    disconnect,
    reconnect,
    sendMessage,
    isConnected,
    isConnecting,
    isReconnecting,
    hasError,
  } = useWebSocketConnection({
    url: wsUrl,
    token: authToken,
    reconnectInterval: preferences.refreshInterval,
    maxReconnectAttempts: preferences.maxRetryAttempts,
    heartbeatInterval: 30000,
    enableHeartbeat: true,
    onConnect: () => {
      console.log('Real-time processing connected');
    },
    onDisconnect: () => {
      console.log('Real-time processing disconnected');
    },
    onError: (error) => {
      console.error('Real-time processing error:', error);
    },
  });

  const isReady = isConnected;

  const contextValue = useMemo<WebSocketContextType>(
    () => ({
      connection: {
        connection: wsConnection,
        connect,
        disconnect,
        reconnect,
        sendMessage,
        isConnected,
        isConnecting,
        isReconnecting,
        hasError,
      },
      sendMessage,
      isReady,
    }),
    [
      wsConnection,
      connect,
      disconnect,
      reconnect,
      sendMessage,
      isConnected,
      isConnecting,
      isReconnecting,
      hasError,
      isReady,
    ]
  );

  return (
    <WebSocketContext.Provider value={contextValue}>
      {children}
    </WebSocketContext.Provider>
  );
};

export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within a WebSocketProvider');
  }
  return context;
};

// Higher-order component for WebSocket protection
export const withWebSocket = <P extends object>(
  Component: React.ComponentType<P>
) => {
  const WithWebSocketComponent = (props: P) => {
    const { isReady } = useWebSocket();

    if (!isReady) {
      return (
        <div className="flex items-center justify-center min-h-screen">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-foreground">
              Connecting to real-time updates...
            </p>
          </div>
        </div>
      );
    }

    return <Component {...props} />;
  };

  WithWebSocketComponent.displayName = `withWebSocket(${Component.displayName || Component.name})`;
  return WithWebSocketComponent;
};
