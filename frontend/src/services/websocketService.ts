/**
 * WebSocket Service - Real-time Graph Updates
 *
 * Handles real-time updates from backend graph services.
 * Consumes WebSocket events and updates frontend state.
 */

import { WebSocketGraphUpdate } from '../types/knowledge-graph';

export type WebSocketMessageHandler = (message: WebSocketGraphUpdate) => void;
export type WebSocketStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

export interface WebSocketConfig {
  reconnectAttempts: number;
  reconnectInterval: number;
  heartbeatInterval: number;
  maxMessageSize: number;
}

export interface WebSocketConnection {
  ws: WebSocket | null;
  status: WebSocketStatus;
  reconnectCount: number;
  lastMessage: WebSocketGraphUpdate | null;
  handlers: Map<string, WebSocketMessageHandler[]>;
  config: WebSocketConfig;
}

class WebSocketService {
  private connections: Map<string, WebSocketConnection> = new Map();
  private defaultConfig: WebSocketConfig = {
    reconnectAttempts: 5,
    reconnectInterval: 3000,
    heartbeatInterval: 30000,
    maxMessageSize: 1024 * 1024, // 1MB
  };

  /**
   * Connect to WebSocket endpoint for graph updates
   */
  connect(
    connectionId: string,
    url: string,
    config?: Partial<WebSocketConfig>
  ): Promise<WebSocketConnection> {
    return new Promise((resolve, reject) => {
      const connectionConfig = { ...this.defaultConfig, ...config };
      const connection: WebSocketConnection = {
        ws: null,
        status: 'connecting',
        reconnectCount: 0,
        lastMessage: null,
        handlers: new Map(),
        config: connectionConfig,
      };

      this.connections.set(connectionId, connection);

      try {
        const ws = new WebSocket(url);
        connection.ws = ws;

        ws.onopen = () => {
          connection.status = 'connected';
          connection.reconnectCount = 0;
          console.log(`WebSocket connected: ${connectionId}`);
          resolve(connection);
        };

        ws.onmessage = (event) => {
          try {
            const message: WebSocketGraphUpdate = JSON.parse(event.data);
            connection.lastMessage = message;
            this.handleMessage(connectionId, message);
          } catch (error) {
            console.error(`Error parsing WebSocket message: ${error}`);
          }
        };

        ws.onclose = (event) => {
          connection.status = 'disconnected';
          console.log(`WebSocket disconnected: ${connectionId}, code: ${event.code}`);

          // Attempt reconnection if not a clean close
          if (event.code !== 1000 && connection.reconnectCount < connectionConfig.reconnectAttempts) {
            this.scheduleReconnect(connectionId, url, connectionConfig);
          }
        };

        ws.onerror = (error) => {
          connection.status = 'error';
          console.error(`WebSocket error: ${connectionId}`, error);
          reject(error);
        };

      } catch (error) {
        connection.status = 'error';
        reject(error);
      }
    });
  }

  /**
   * Disconnect WebSocket connection
   */
  disconnect(connectionId: string): void {
    const connection = this.connections.get(connectionId);
    if (connection?.ws) {
      connection.ws.close(1000, 'Client disconnect');
      connection.status = 'disconnected';
    }
    this.connections.delete(connectionId);
  }

  /**
   * Subscribe to specific message types
   */
  subscribe(
    connectionId: string,
    messageType: string,
    handler: WebSocketMessageHandler
  ): () => void {
    const connection = this.connections.get(connectionId);
    if (!connection) {
      throw new Error(`Connection not found: ${connectionId}`);
    }

    if (!connection.handlers.has(messageType)) {
      connection.handlers.set(messageType, []);
    }

    connection.handlers.get(messageType)!.push(handler);

    // Return unsubscribe function
    return () => {
      const handlers = connection.handlers.get(messageType);
      if (handlers) {
        const index = handlers.indexOf(handler);
        if (index > -1) {
          handlers.splice(index, 1);
        }
      }
    };
  }

  /**
   * Send message to WebSocket server
   */
  sendMessage(connectionId: string, message: any): void {
    const connection = this.connections.get(connectionId);
    if (!connection?.ws || connection.ws.readyState !== WebSocket.OPEN) {
      throw new Error(`WebSocket not connected: ${connectionId}`);
    }

    const messageStr = JSON.stringify(message);
    if (messageStr.length > connection.config.maxMessageSize) {
      throw new Error('Message too large');
    }

    connection.ws.send(messageStr);
  }

  /**
   * Get connection status
   */
  getConnectionStatus(connectionId: string): WebSocketStatus | null {
    const connection = this.connections.get(connectionId);
    return connection?.status || null;
  }

  /**
   * Get last message for connection
   */
  getLastMessage(connectionId: string): WebSocketGraphUpdate | null {
    const connection = this.connections.get(connectionId);
    return connection?.lastMessage || null;
  }

  /**
   * Handle incoming WebSocket messages
   */
  private handleMessage(connectionId: string, message: WebSocketGraphUpdate): void {
    const connection = this.connections.get(connectionId);
    if (!connection) return;

    // Route message to appropriate handlers based on type
    const handlers = connection.handlers.get(message.type) || [];
    handlers.forEach(handler => {
      try {
        handler(message);
      } catch (error) {
        console.error(`Error in WebSocket handler for ${message.type}:`, error);
      }
    });

    // Also send to wildcard handlers
    const wildcardHandlers = connection.handlers.get('*') || [];
    wildcardHandlers.forEach(handler => {
      try {
        handler(message);
      } catch (error) {
        console.error(`Error in WebSocket wildcard handler:`, error);
      }
    });
  }

  /**
   * Schedule reconnection attempt
   */
  private scheduleReconnect(
    connectionId: string,
    url: string,
    config: WebSocketConfig
  ): void {
    const connection = this.connections.get(connectionId);
    if (!connection) return;

    connection.reconnectCount++;
    const delay = config.reconnectInterval * Math.pow(2, connection.reconnectCount - 1);

    console.log(`Scheduling reconnect attempt ${connection.reconnectCount} for ${connectionId} in ${delay}ms`);

    setTimeout(() => {
      if (this.connections.has(connectionId)) {
        this.connect(connectionId, url, config).catch(error => {
          console.error(`Reconnect failed for ${connectionId}:`, error);
        });
      }
    }, delay);
  }

  /**
   * Send heartbeat to keep connection alive
   */
  private startHeartbeat(connectionId: string): void {
    const connection = this.connections.get(connectionId);
    if (!connection) return;

    const heartbeatInterval = setInterval(() => {
      if (connection.ws?.readyState === WebSocket.OPEN) {
        this.sendMessage(connectionId, { type: 'heartbeat', timestamp: new Date().toISOString() });
      } else {
        clearInterval(heartbeatInterval);
      }
    }, connection.config.heartbeatInterval);
  }

  /**
   * Initialize graph updates WebSocket connection with filters
   */
  async connectToGraphUpdates(filters?: import('../types/knowledge-graph').GraphFilters): Promise<WebSocketConnection> {
    const baseUrl = process.env.REACT_APP_GRAPH_WS_URL || 'ws://localhost:8010';
    const wsUrl = new URL('/ws/graph-updates', baseUrl);

    // Add filters as query parameters for initial subscription
    if (filters) {
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          if (typeof value === 'object') {
            wsUrl.searchParams.set(key, JSON.stringify(value));
          } else {
            wsUrl.searchParams.set(key, String(value));
          }
        }
      });
    }

    const connection = await this.connect('graph-updates', wsUrl.toString());

    // Send initial subscription message
    if (filters) {
      this.sendMessage('graph-updates', {
        type: 'subscribe',
        filters,
        timestamp: new Date().toISOString()
      });
    }

    return connection;
  }

  /**
   * Initialize analytics updates WebSocket connection
   */
  async connectToAnalyticsUpdates(): Promise<WebSocketConnection> {
    const wsUrl = process.env.REACT_APP_ANALYTICS_WS_URL || 'ws://localhost:8009/ws/analytics-updates';
    return this.connect('analytics-updates', wsUrl);
  }

  /**
   * Subscribe to specific entity updates
   */
  subscribeToEntityUpdates(
    connectionId: string,
    entityIds: string[],
    handler: WebSocketMessageHandler
  ): () => void {
    // Send subscription message to backend
    this.sendMessage(connectionId, {
      type: 'subscribe_entities',
      entity_ids: entityIds,
      timestamp: new Date().toISOString()
    });

    // Register handler for entity updates
    return this.subscribe(connectionId, 'entity_update', handler);
  }

  /**
   * Subscribe to community updates
   */
  subscribeToCommunityUpdates(
    connectionId: string,
    communityIds: string[],
    handler: WebSocketMessageHandler
  ): () => void {
    this.sendMessage(connectionId, {
      type: 'subscribe_communities',
      community_ids: communityIds,
      timestamp: new Date().toISOString()
    });

    return this.subscribe(connectionId, 'community_update', handler);
  }

  /**
   * Subscribe to performance metrics updates
   */
  subscribeToPerformanceUpdates(
    connectionId: string,
    handler: WebSocketMessageHandler
  ): () => void {
    return this.subscribe(connectionId, 'performance_update', handler);
  }

  /**
   * Update filters for existing connection
   */
  updateFilters(connectionId: string, filters: import('../types/knowledge-graph').GraphFilters): void {
    this.sendMessage(connectionId, {
      type: 'update_filters',
      filters,
      timestamp: new Date().toISOString()
    });
  }

  /**
   * Request batch updates
   */
  requestBatchUpdate(connectionId: string, options: {
    since?: string;
    entity_ids?: string[];
    include_analytics?: boolean;
  }): void {
    this.sendMessage(connectionId, {
      type: 'request_batch_update',
      ...options,
      timestamp: new Date().toISOString()
    });
  }

  /**
   * Disconnect all WebSocket connections
   */
  disconnectAll(): void {
    this.connections.forEach((_, connectionId) => {
      this.disconnect(connectionId);
    });
  }

  /**
   * Get all active connections
   */
  getActiveConnections(): Array<{ id: string; status: WebSocketStatus }> {
    return Array.from(this.connections.entries()).map(([id, connection]) => ({
      id,
      status: connection.status,
    }));
  }
}

export const websocketService = new WebSocketService();