'use client';

import React, { createContext, useContext, useEffect, ReactNode } from 'react';
import { useAnalyticsStore, useGraphVisualizationStore, useRealtimeStore } from '@/stores/analytics';
import { useWebSocket } from '@/services/analytics';

interface AnalyticsContextType {
  // Store instances
  analytics: ReturnType<typeof useAnalyticsStore>;
  graph: ReturnType<typeof useGraphVisualizationStore>;
  realtime: ReturnType<typeof useRealtimeStore>;

  // WebSocket connection
  ws: {
    isConnected: boolean;
    error: string | null;
    subscribe: (metrics: string[]) => void;
    unsubscribe: (metrics: string[]) => void;
  };
}

const AnalyticsContext = createContext<AnalyticsContextType | null>(null);

interface AnalyticsProviderProps {
  children: ReactNode;
  autoConnect?: boolean;
  subscriptions?: string[];
}

export const AnalyticsProvider: React.FC<AnalyticsProviderProps> = ({
  children,
  autoConnect = true,
  subscriptions = [],
}) => {
  const analytics = useAnalyticsStore();
  const graph = useGraphVisualizationStore();
  const realtime = useRealtimeStore();

  const { ws, isConnected, error } = useWebSocket({
    url: process.env.NEXT_PUBLIC_WEBSOCKET_URL || 'ws://localhost:8000/ws/analytics',
    protocols: ['analytics-v1'],
    reconnectInterval: 3000,
    maxReconnectAttempts: 5,
    heartbeatInterval: 30000,
  });

  // Auto-connect and subscribe to metrics
  useEffect(() => {
    if (autoConnect && isConnected && subscriptions.length > 0) {
      ws.subscribe(subscriptions);
    }

    return () => {
      if (subscriptions.length > 0) {
        ws.unsubscribe(subscriptions);
      }
    };
  }, [autoConnect, isConnected, subscriptions, ws]);

  // Update store connection status
  useEffect(() => {
    realtime.setConnectionStatus(isConnected ? 'connected' : 'disconnected');
    realtime.setConnected(isConnected);
  }, [isConnected, realtime]);

  // Handle WebSocket errors
  useEffect(() => {
    if (error) {
      realtime.setConnectionStatus('error');
      analytics.setError(error);
    }
  }, [error, realtime, analytics]);

  const contextValue: AnalyticsContextType = {
    analytics,
    graph,
    realtime,
    ws: {
      isConnected,
      error,
      subscribe: ws.subscribe,
      unsubscribe: ws.unsubscribe,
    },
  };

  return (
    <AnalyticsContext.Provider value={contextValue}>
      {children}
    </AnalyticsContext.Provider>
  );
};

export const useAnalytics = (): AnalyticsContextType => {
  const context = useContext(AnalyticsContext);
  if (!context) {
    throw new Error('useAnalytics must be used within an AnalyticsProvider');
  }
  return context;
};

// Hook for accessing analytics state
export const useAnalyticsState = () => {
  const { analytics } = useAnalytics();
  return analytics;
};

// Hook for accessing graph state
export const useGraphState = () => {
  const { graph } = useAnalytics();
  return graph;
};

// Hook for accessing realtime state
export const useRealtimeState = () => {
  const { realtime } = useAnalytics();
  return realtime;
};

// Hook for WebSocket connection
export const useAnalyticsWebSocket = () => {
  const { ws } = useAnalytics();
  return ws;
};