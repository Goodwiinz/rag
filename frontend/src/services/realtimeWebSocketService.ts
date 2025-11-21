/**
 * Enhanced Real-time WebSocket Service for Document Processing
 *
 * This service provides a robust WebSocket connection for real-time document
 * processing status updates with authentication, reconnection logic, and
 * performance optimization for high-concurrency scenarios.
 */

import {
  WebSocketMessage,
  DocumentUpdateMessage,
  QueueUpdateMessage,
  SystemMetricsMessage,
  NotificationMessage,
  ConnectionStatusMessage,
  DocumentProcessingState,
  WebSocketConnectionState
} from '@/types/realtime-processing';

export interface WebSocketConfig {
  url: string;
  protocols?: string[];
  reconnectAttempts: number;
  reconnectInterval: number;
  heartbeatInterval: number;
  maxMessageSize: number;
  connectionTimeout: number;
  enableCompression: boolean;
  bufferMessages: boolean;
  maxBufferSize: number;
}

export interface PerformanceMetrics {
  connectionLatency: number;
  messageRate: number;
  errorRate: number;
  reconnectionCount: number;
  uptime: number;
  lastMessageTimestamp: number;
}

export interface QueuedMessage {
  id: string;
  message: WebSocketMessage;
  timestamp: number;
  retryCount: number;
  maxRetries: number;
}

type MessageHandler = (message: WebSocketMessage) => void;
type ConnectionEventHandler = (status: WebSocketConnectionState) => void;
type PerformanceEventHandler = (metrics: PerformanceMetrics) => void;

export class RealtimeWebSocketService {
  private ws: WebSocket | null = null;
  private config: WebSocketConfig;
  private connectionState: WebSocketConnectionState;
  private messageHandlers: Map<string, MessageHandler[]> = new Map();
  private connectionHandlers: ConnectionEventHandler[] = [];
  private performanceHandlers: PerformanceEventHandler[] = [];
  private messageBuffer: QueuedMessage[] = [];
  private metrics: PerformanceMetrics;
  private heartbeatTimer: NodeJS.Timeout | null = null;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private performanceTimer: NodeJS.Timeout | null = null;
  private connectionStartTime: number = 0;
  private lastHeartbeatTime: number = 0;
  private messageCount: number = 0;
  private errorCount: number = 0;

  // Performance optimization for high concurrency
  private messageQueue: WebSocketMessage[] = [];
  private processingBatch = false;
  private batchProcessorTimer: NodeJS.Timeout | null = null;

  constructor(config: Partial<WebSocketConfig> = {}) {
    this.config = {
      url: process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws/document-processing',
      reconnectAttempts: 5,
      reconnectInterval: 2000,
      heartbeatInterval: 30000,
      maxMessageSize: 1024 * 1024, // 1MB
      connectionTimeout: 10000,
      enableCompression: true,
      bufferMessages: true,
      maxBufferSize: 1000,
      ...config
    };

    this.connectionState = {
      status: 'disconnected',
      reconnectionAttempts: 0,
      maxReconnectionAttempts: this.config.reconnectAttempts,
      reconnectInterval: this.config.reconnectInterval,
      latency: 0,
    };

    this.metrics = {
      connectionLatency: 0,
      messageRate: 0,
      errorRate: 0,
      reconnectionCount: 0,
      uptime: 0,
      lastMessageTimestamp: 0,
    };

    // Bind methods to maintain context
    this.handleOpen = this.handleOpen.bind(this);
    this.handleMessage = this.handleMessage.bind(this);
    this.handleError = this.handleError.bind(this);
    this.handleClose = this.handleClose.bind(this);
  }

  /**
   * Connect to WebSocket with authentication token
   */
  async connect(authToken: string): Promise<void> {
    if (this.ws?.readyState === WebSocket.OPEN) {
      return;
    }

    this.updateConnectionState({ status: 'connecting' });
    this.connectionStartTime = Date.now();

    try {
      const wsUrl = new URL(this.config.url);
      wsUrl.searchParams.set('token', authToken);

      this.ws = new WebSocket(wsUrl.toString(), this.config.protocols);

      // Set up connection timeout
      const timeoutId = setTimeout(() => {
        if (this.ws?.readyState !== WebSocket.OPEN) {
          this.ws?.close();
          this.handleConnectionError(new Error('Connection timeout'));
        }
      }, this.config.connectionTimeout);

      this.ws.onopen = () => {
        clearTimeout(timeoutId);
        this.handleOpen();
      };

      this.ws.onmessage = this.handleMessage;
      this.ws.onerror = this.handleError;
      this.ws.onclose = this.handleClose;

    } catch (error) {
      this.handleConnectionError(error as Error);
    }
  }

  /**
   * Disconnect from WebSocket
   */
  disconnect(): void {
    this.clearTimers();

    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }

    this.updateConnectionState({ status: 'disconnected' });
    this.messageBuffer = [];
    this.messageQueue = [];
  }

  /**
   * Send message to server
   */
  send(message: WebSocketMessage): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      if (this.config.bufferMessages) {
        this.bufferMessage(message);
      }
      return;
    }

    try {
      const messageStr = JSON.stringify(message);

      if (messageStr.length > this.config.maxMessageSize) {
        throw new Error(`Message size exceeds limit: ${messageStr.length} bytes`);
      }

      this.ws.send(messageStr);
      this.messageCount++;

    } catch (error) {
      this.errorCount++;
      console.error('Failed to send message:', error);

      if (this.config.bufferMessages) {
        this.bufferMessage(message);
      }
    }
  }

  /**
   * Subscribe to specific message types
   */
  subscribe(messageType: string, handler: MessageHandler): () => void {
    if (!this.messageHandlers.has(messageType)) {
      this.messageHandlers.set(messageType, []);
    }

    this.messageHandlers.get(messageType)!.push(handler);

    // Return unsubscribe function
    return () => {
      const handlers = this.messageHandlers.get(messageType);
      if (handlers) {
        const index = handlers.indexOf(handler);
        if (index > -1) {
          handlers.splice(index, 1);
        }
      }
    };
  }

  /**
   * Subscribe to connection events
   */
  onConnectionChange(handler: ConnectionEventHandler): () => void {
    this.connectionHandlers.push(handler);

    return () => {
      const index = this.connectionHandlers.indexOf(handler);
      if (index > -1) {
        this.connectionHandlers.splice(index, 1);
      }
    };
  }

  /**
   * Subscribe to performance metrics
   */
  onPerformanceUpdate(handler: PerformanceEventHandler): () => void {
    this.performanceHandlers.push(handler);

    return () => {
      const index = this.performanceHandlers.indexOf(handler);
      if (index > -1) {
        this.performanceHandlers.splice(index, 1);
      }
    };
  }

  /**
   * Get current connection state
   */
  getConnectionState(): WebSocketConnectionState {
    return { ...this.connectionState };
  }

  /**
   * Get current performance metrics
   */
  getPerformanceMetrics(): PerformanceMetrics {
    return { ...this.metrics };
  }

  /**
   * Request document processing updates
   */
  requestDocumentUpdates(documentIds?: string[]): void {
    this.send({
      type: 'subscribe_documents',
      payload: { document_ids: documentIds },
      timestamp: new Date().toISOString()
    });
  }

  /**
   * Request system metrics updates
   */
  requestSystemMetrics(): void {
    this.send({
      type: 'subscribe_system_metrics',
      payload: {},
      timestamp: new Date().toISOString()
    });
  }

  // Private methods

  private handleOpen(): void {
    this.updateConnectionState({
      status: 'connected',
      lastConnectedAt: new Date().toISOString(),
      reconnectionAttempts: 0,
      lastError: undefined
    });

    // Start heartbeat
    this.startHeartbeat();

    // Start performance monitoring
    this.startPerformanceMonitoring();

    // Send buffered messages
    this.flushMessageBuffer();

    // Request initial data
    this.requestDocumentUpdates();
    this.requestSystemMetrics();
  }

  private handleMessage(event: MessageEvent): void {
    try {
      const message: WebSocketMessage = JSON.parse(event.data);
      this.lastHeartbeatTime = Date.now();
      this.metrics.lastMessageTimestamp = this.lastHeartbeatTime;

      // Add to queue for batch processing
      this.messageQueue.push(message);

      if (!this.processingBatch) {
        this.processMessageBatch();
      }

    } catch (error) {
      this.errorCount++;
      console.error('Failed to parse WebSocket message:', error);
    }
  }

  private processMessageBatch(): void {
    if (this.processingBatch) return;

    this.processingBatch = true;
    const batch = this.messageQueue.splice(0, 100); // Process max 100 messages per batch

    batch.forEach(message => {
      // Route message to appropriate handlers
      const handlers = this.messageHandlers.get(message.type) || [];
      handlers.forEach(handler => {
        try {
          handler(message);
        } catch (error) {
          console.error(`Error in message handler for ${message.type}:`, error);
        }
      });

      // Send to wildcard handlers
      const wildcardHandlers = this.messageHandlers.get('*') || [];
      wildcardHandlers.forEach(handler => {
        try {
          handler(message);
        } catch (error) {
          console.error('Error in wildcard handler:', error);
        }
      });
    });

    this.processingBatch = false;

    // Continue processing if there are more messages
    if (this.messageQueue.length > 0) {
      // Use nextTick to avoid blocking
      setTimeout(() => this.processMessageBatch(), 0);
    }
  }

  private handleError(event: Event): void {
    this.errorCount++;
    this.handleConnectionError(new Error('WebSocket connection error'));
  }

  private handleClose(event: CloseEvent): void {
    this.clearTimers();
    this.updateConnectionState({ status: 'disconnected' });

    // Attempt reconnection if not a clean close
    if (event.code !== 1000 && this.connectionState.reconnectionAttempts < this.config.reconnectAttempts) {
      this.scheduleReconnect();
    }
  }

  private handleConnectionError(error: Error): void {
    this.updateConnectionState({
      status: 'error',
      lastError: error.message
    });
  }

  private updateConnectionState(updates: Partial<WebSocketConnectionState>): void {
    this.connectionState = { ...this.connectionState, ...updates };

    this.connectionHandlers.forEach(handler => {
      try {
        handler(this.connectionState);
      } catch (error) {
        console.error('Error in connection handler:', error);
      }
    });
  }

  private scheduleReconnect(): void {
    const attempts = this.connectionState.reconnectionAttempts + 1;
    this.updateConnectionState({ reconnectionAttempts: attempts });

    const delay = this.config.reconnectInterval * Math.pow(2, attempts - 1);

    this.reconnectTimer = setTimeout(() => {
      if (this.connectionState.status === 'disconnected') {
        this.updateConnectionState({ status: 'reconnecting' });
        // Reconnection would require getting a fresh auth token
        // This should be handled by the calling code
      }
    }, delay);
  }

  private startHeartbeat(): void {
    this.heartbeatTimer = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.send({
          type: 'heartbeat',
          payload: { timestamp: Date.now() },
          timestamp: new Date().toISOString()
        });
      }
    }, this.config.heartbeatInterval);
  }

  private startPerformanceMonitoring(): void {
    this.performanceTimer = setInterval(() => {
      this.updatePerformanceMetrics();
    }, 5000); // Update every 5 seconds
  }

  private updatePerformanceMetrics(): void {
    const now = Date.now();
    const uptime = this.connectionStartTime > 0 ? now - this.connectionStartTime : 0;

    // Calculate message rate (messages per second over last 5 seconds)
    const messageRate = this.messageCount / 5;
    this.messageCount = 0;

    // Calculate error rate
    const errorRate = this.errorCount > 0 ? (this.errorCount / (messageRate + this.errorCount)) * 100 : 0;
    this.errorCount = 0;

    // Calculate latency if we have heartbeat responses
    const latency = this.metrics.connectionLatency; // This would be updated by heartbeat responses

    this.metrics = {
      connectionLatency: latency,
      messageRate,
      errorRate,
      reconnectionCount: this.connectionState.reconnectionAttempts,
      uptime,
      lastMessageTimestamp: this.metrics.lastMessageTimestamp,
    };

    this.performanceHandlers.forEach(handler => {
      try {
        handler(this.metrics);
      } catch (error) {
        console.error('Error in performance handler:', error);
      }
    });
  }

  private bufferMessage(message: WebSocketMessage): void {
    const bufferedMessage: QueuedMessage = {
      id: `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      message,
      timestamp: Date.now(),
      retryCount: 0,
      maxRetries: 3,
    };

    this.messageBuffer.push(bufferedMessage);

    // Remove old messages if buffer is full
    if (this.messageBuffer.length > this.config.maxBufferSize) {
      this.messageBuffer.shift();
    }
  }

  private flushMessageBuffer(): void {
    const messages = this.messageBuffer.splice(0);
    messages.forEach(buffered => {
      this.send(buffered.message);
    });
  }

  private clearTimers(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.performanceTimer) {
      clearInterval(this.performanceTimer);
      this.performanceTimer = null;
    }

    if (this.batchProcessorTimer) {
      clearTimeout(this.batchProcessorTimer);
      this.batchProcessorTimer = null;
    }
  }

  /**
   * Cleanup resources
   */
  destroy(): void {
    this.disconnect();
    this.messageHandlers.clear();
    this.connectionHandlers = [];
    this.performanceHandlers = [];
  }
}

// Singleton instance for the application
let realtimeWebSocketService: RealtimeWebSocketService | null = null;

export const getRealtimeWebSocketService = (): RealtimeWebSocketService => {
  if (!realtimeWebSocketService) {
    realtimeWebSocketService = new RealtimeWebSocketService();
  }
  return realtimeWebSocketService;
};

export const destroyRealtimeWebSocketService = (): void => {
  if (realtimeWebSocketService) {
    realtimeWebSocketService.destroy();
    realtimeWebSocketService = null;
  }
};