import React, { createContext, useContext, useEffect, ReactNode } from 'react';
import { useWebSocketConnection } from '@/hooks/useWebSocketConnection';
import { useRealtimeProcessingStore } from '@/store/realtimeProcessingStore';

interface WebSocketContextType {
  connection: ReturnType<typeof useWebSocketConnection>;
  sendMessage: (message: any) => boolean;
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

  const connection = useWebSocketConnection({
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

  const isReady = connection.isConnected;

  const contextValue: WebSocketContextType = {
    connection,
    sendMessage: connection.sendMessage,
    isReady,
  };

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
            <p className="mt-4 text-gray-600">Connecting to real-time updates...</p>
          </div>
        </div>
      );
    }

    return <Component {...props} />;
  };

  WithWebSocketComponent.displayName = `withWebSocket(${Component.displayName || Component.name})`;
  return WithWebSocketComponent;
};