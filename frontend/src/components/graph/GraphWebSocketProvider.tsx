/**
 * Graph WebSocket Provider - Real-time Graph Updates
 *
 * Provides WebSocket integration for real-time graph updates.
 * Consumes WebSocket events from backend and updates frontend state.
 */

import React, {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  useCallback,
  useMemo,
} from 'react';
import {
  websocketService,
  WebSocketStatus,
} from '../../services/websocketService';
import { useGraphStore } from '../../stores/graphStore';
import { WebSocketGraphUpdate } from '../../types/graph-api';

interface WebSocketContextValue {
  status: WebSocketStatus;
  isConnected: boolean;
  lastMessage: WebSocketGraphUpdate | null;
  messageCount: number;
  reconnectAttempts: number;
  manuallyReconnect: () => Promise<void>;
  disconnect: () => void;
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null);

interface GraphWebSocketProviderProps {
  children: React.ReactNode;
  autoConnect?: boolean;
  reconnectOnMount?: boolean;
}

export const GraphWebSocketProvider: React.FC<GraphWebSocketProviderProps> = ({
  children,
  autoConnect = true,
  reconnectOnMount = true,
}) => {
  const [status, setStatus] = useState<WebSocketStatus>('disconnected');
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketGraphUpdate | null>(
    null
  );
  const [messageCount, setMessageCount] = useState(0);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);

  const setWebSocketStatus = useGraphStore((state) => state.setWebSocketStatus);
  const setWebSocketConnected = useGraphStore(
    (state) => state.setWebSocketConnected
  );
  const handleWebSocketMessage = useGraphStore(
    (state) => state.handleWebSocketMessage
  );

  const connectionRef = useRef<string>('graph-updates');
  const analyticsConnectionRef = useRef<string>('analytics-updates');
  const mountedRef = useRef(false);

  // Handle incoming WebSocket messages
  const handleIncomingMessage = useCallback(
    (message: WebSocketGraphUpdate) => {
      setLastMessage(message);
      setMessageCount((prev) => prev + 1);

      // Update store with message data
      handleWebSocketMessage(message);

      // Log message for debugging
      if (process.env.NODE_ENV === 'development') {
        console.log(
          'WebSocket message received:',
          message.type,
          message.timestamp
        );
      }
    },
    [handleWebSocketMessage]
  );

  // Connect to WebSocket services
  const connect = useCallback(async () => {
    try {
      setStatus('connecting');
      setReconnectAttempts((prev) => prev + 1);

      // Connect to main graph updates
      const graphConnection = await websocketService.connectToGraphUpdates();

      // Subscribe to all graph update types
      const unsubscribeGraph = websocketService.subscribe(
        connectionRef.current,
        '*',
        handleIncomingMessage
      );

      // Connect to analytics updates
      const analyticsConnection =
        await websocketService.connectToAnalyticsUpdates();

      // Subscribe to analytics updates
      const unsubscribeAnalytics = websocketService.subscribe(
        analyticsConnectionRef.current,
        'analytics_updated',
        handleIncomingMessage
      );

      setStatus('connected');
      setIsConnected(true);
      setReconnectAttempts(0);

      // Set up cleanup function
      return () => {
        unsubscribeGraph?.();
        unsubscribeAnalytics?.();
        websocketService.disconnect(connectionRef.current);
        websocketService.disconnect(analyticsConnectionRef.current);
      };
    } catch (error) {
      console.error('WebSocket connection failed:', error);
      setStatus('error');
      setIsConnected(false);
      throw error;
    }
  }, [handleIncomingMessage]);

  // Manually reconnect
  const manuallyReconnect = useCallback(async () => {
    try {
      await connect();
    } catch (error) {
      console.error('Manual reconnection failed:', error);
    }
  }, [connect]);

  // Disconnect
  const disconnect = useCallback(() => {
    websocketService.disconnect(connectionRef.current);
    websocketService.disconnect(analyticsConnectionRef.current);
    setStatus('disconnected');
    setIsConnected(false);
  }, []);

  // Auto-connect on mount
  useEffect(() => {
    if (!mountedRef.current) {
      mountedRef.current = true;

      if (autoConnect) {
        connect().catch((error) => {
          console.error('Initial WebSocket connection failed:', error);
        });
      }
    }

    return () => {
      if (mountedRef.current) {
        disconnect();
        mountedRef.current = false;
      }
    };
  }, [autoConnect, connect, disconnect]);

  // Update store with connection status
  useEffect(() => {
    setWebSocketStatus(status);
    setWebSocketConnected(isConnected);
  }, [status, isConnected, setWebSocketStatus, setWebSocketConnected]);

  // Periodic status check
  useEffect(() => {
    const interval = setInterval(() => {
      const currentStatus = websocketService.getConnectionStatus(
        connectionRef.current
      );
      if (currentStatus !== status) {
        setStatus(currentStatus || 'disconnected');
        setIsConnected(currentStatus === 'connected');
      }
    }, 5000); // Check every 5 seconds

    return () => clearInterval(interval);
  }, [status]);

  const contextValue: WebSocketContextValue = useMemo(
    () => ({
      status,
      isConnected,
      lastMessage,
      messageCount,
      reconnectAttempts,
      manuallyReconnect,
      disconnect,
    }),
    [
      status,
      isConnected,
      lastMessage,
      messageCount,
      reconnectAttempts,
      manuallyReconnect,
      disconnect,
    ]
  );

  return (
    <WebSocketContext.Provider value={contextValue}>
      {children}
    </WebSocketContext.Provider>
  );
};

// Hook to use WebSocket context
export const useGraphWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error(
      'useGraphWebSocket must be used within a GraphWebSocketProvider'
    );
  }
  return context;
};

// Hook for specific message types
export const useGraphWebSocketMessages = <
  T extends WebSocketGraphUpdate['type'],
>(
  messageType: T
) => {
  const [messages, setMessages] = useState<WebSocketGraphUpdate[]>([]);
  const { lastMessage } = useGraphWebSocket();

  useEffect(() => {
    if (lastMessage && lastMessage.type === messageType) {
      setMessages((prev) => [...prev.slice(-99), lastMessage]); // Keep last 100 messages
    }
  }, [lastMessage, messageType]);

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  return { messages, clearMessages };
};

// Component to display WebSocket status
export const WebSocketStatusIndicator: React.FC<{
  className?: string;
  showDetails?: boolean;
}> = ({ className = '', showDetails = false }) => {
  const { status, isConnected, reconnectAttempts, manuallyReconnect } =
    useGraphWebSocket();

  const getStatusColor = () => {
    switch (status) {
      case 'connected':
        return 'bg-[var(--nous-terra)]';
      case 'connecting':
        return 'bg-[var(--nous-corona)]';
      case 'error':
        return 'bg-[var(--nous-mars)]';
      case 'disconnected':
        return 'bg-[var(--nous-bg-3)]';
      default:
        return 'bg-[var(--nous-bg-3)]';
    }
  };

  const getStatusText = () => {
    switch (status) {
      case 'connected':
        return 'Connected';
      case 'connecting':
        return 'Connecting...';
      case 'error':
        return 'Error';
      case 'disconnected':
        return 'Disconnected';
      default:
        return 'Unknown';
    }
  };

  if (!showDetails) {
    return (
      <div className={`flex items-center space-x-2 ${className}`}>
        <div className={`w-2 h-2 rounded-full ${getStatusColor()}`}></div>
        <span className="text-xs text-foreground">{getStatusText()}</span>
      </div>
    );
  }

  return (
    <div className={`p-3 bg-[var(--nous-bg-2)] rounded-lg ${className}`}>
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-sm font-medium">WebSocket Status</h4>
        <div className={`w-2 h-2 rounded-full ${getStatusColor()}`}></div>
      </div>
      <div className="space-y-1 text-xs">
        <div className="flex justify-between">
          <span className="text-foreground">Status:</span>
          <span className="font-medium">{getStatusText()}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-foreground">Connected:</span>
          <span
            className={`font-medium ${isConnected ? 'text-[var(--nous-terra)]' : 'text-[var(--nous-mars)]'}`}
          >
            {isConnected ? 'Yes' : 'No'}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-foreground">Reconnect Attempts:</span>
          <span className="font-medium">{reconnectAttempts}</span>
        </div>
        {status === 'error' && (
          <button
            onClick={manuallyReconnect}
            className="mt-2 w-full px-2 py-1 bg-[var(--nous-sol)] text-white text-xs rounded hover:bg-[var(--nous-sol)]/90"
          >
            Reconnect
          </button>
        )}
      </div>
    </div>
  );
};

// Higher-order component for WebSocket-enabled components
export const withWebSocket = <P extends object>(
  Component: React.ComponentType<P>
) => {
  const WebSocketWrapper = (props: P) => {
    return (
      <GraphWebSocketProvider>
        <Component {...props} />
      </GraphWebSocketProvider>
    );
  };
  return WebSocketWrapper;
};

export default GraphWebSocketProvider;
