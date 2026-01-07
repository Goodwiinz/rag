/**
 * Unified WebSocket Client
 *
 * This is the consolidated WebSocket service that combines functionality from:
 * - websocket.ts (basic connection management)
 * - websocketService.ts (graph updates)
 * - enhancedWebSocket.ts (message buffering, latency monitoring)
 * - realtime-websocket-service.ts (document status)
 * - realtimeWebSocketService.ts (realtime updates)
 * - monitoringWebsocketService.ts (system monitoring)
 *
 * Features:
 * - Type-safe message handling
 * - Auto-reconnection with exponential backoff
 * - Message buffering with priority queue
 * - Latency monitoring
 * - Event-driven architecture
 * - Multiple subscription support
 */


// ============================================================================
// Types
// ============================================================================

export interface WebSocketConfig {
  url: string;
  token?: string;
  organizationId?: string;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
  heartbeatInterval?: number;
  connectionTimeout?: number;
  enableLatencyMonitoring?: boolean;
  enableMessageBuffering?: boolean;
  bufferSize?: number;
}

export interface WebSocketMessage<T = unknown> {
  type: string;
  payload: T;
  timestamp: string;
}

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error';
export type MessageHandler<T = unknown> = (data: T) => void;
export type MessagePriority = 'high' | 'medium' | 'low';

export interface ConnectionStats {
  connectedAt?: string;
  lastMessageAt?: string;
  messagesReceived: number;
  messagesSent: number;
  reconnectAttempts: number;
  currentLatency: number;
  averageLatency: number;
  errorCount: number;
}

interface BufferedMessage {
  message: WebSocketMessage;
  priority: MessagePriority;
  retries: number;
  timestamp: number;
}

// ============================================================================
// Unified WebSocket Client
// ============================================================================

export class WebSocketClient {
  private ws: WebSocket | null = null;
  private config: Required<Omit<WebSocketConfig, 'token' | 'organizationId'>> & Pick<WebSocketConfig, 'token' | 'organizationId'>;
  private listeners: Map<string, MessageHandler[]> = new Map();
  private eventListeners: Map<string, ((...args: unknown[]) => void)[]> = new Map();
  private messageBuffer: BufferedMessage[] = [];
  private stats: ConnectionStats;
  private isDestroyed = false;
  private isConnecting = false;
  private latencyMeasurements: number[] = [];
  private heartbeatTimer: NodeJS.Timeout | null = null;
  private bufferFlushTimer: NodeJS.Timeout | null = null;
  private reconnectTimer: NodeJS.Timeout | null = null;

  constructor(config: WebSocketConfig) {
    this.config = {
      reconnectInterval: 2000,
      maxReconnectAttempts: 5,
      heartbeatInterval: 30000,
      connectionTimeout: 10000,
      enableLatencyMonitoring: true,
      enableMessageBuffering: true,
      bufferSize: 100,
      ...config,
    };
    this.stats = this.initializeStats();
  }

  // Simple event emitter implementation
  private emit(event: string, data?: unknown): void {
    const listeners = this.eventListeners.get(event) || [];
    listeners.forEach(listener => {
      try {
        listener(data);
      } catch (error) {
        console.error(`Error in event listener for ${event}:`, error);
      }
    });
  }

  // --------------------------------------------------------------------------
  // Connection Management
  // --------------------------------------------------------------------------

  async connect(): Promise<void> {
    if (this.isDestroyed) {
      throw new Error('WebSocket client has been destroyed');
    }

    if (this.isConnecting || this.isConnected()) {
      return;
    }

    this.isConnecting = true;

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        this.isConnecting = false;
        reject(new Error('Connection timeout'));
      }, this.config.connectionTimeout);

      try {
        const wsUrl = new URL(this.config.url);
        if (this.config.token) {
          wsUrl.searchParams.append('token', this.config.token);
        }
        if (this.config.organizationId) {
          wsUrl.searchParams.append('organization_id', this.config.organizationId);
        }

        this.ws = new WebSocket(wsUrl.toString());

        this.ws.onopen = () => {
          clearTimeout(timeout);
          this.isConnecting = false;
          this.stats.connectedAt = new Date().toISOString();
          this.stats.reconnectAttempts = 0;

          this.startHeartbeat();
          this.startBufferFlush();
          this.flushBuffer();

          this.emit('connected', { timestamp: new Date().toISOString() });
          this.notifyListeners('connected', { timestamp: new Date().toISOString() });
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            const message: WebSocketMessage = JSON.parse(event.data);
            this.stats.messagesReceived++;
            this.stats.lastMessageAt = new Date().toISOString();
            this.handleMessage(message);
          } catch (error) {
            console.error('Error parsing WebSocket message:', error);
          }
        };

        this.ws.onclose = (event) => {
          clearTimeout(timeout);
          this.isConnecting = false;
          this.cleanup();

          this.emit('disconnected', { code: event.code, reason: event.reason });
          this.notifyListeners('disconnected', { code: event.code, reason: event.reason });

          // Auto-reconnect if not a clean close
          if (event.code !== 1000 && !this.isDestroyed) {
            this.scheduleReconnect();
          }
        };

        this.ws.onerror = (error) => {
          clearTimeout(timeout);
          this.isConnecting = false;
          this.stats.errorCount++;

          if (this.stats.reconnectAttempts === 0) {
            console.warn('WebSocket connection failed - real-time updates unavailable');
          }

          this.emit('error', { error, timestamp: new Date().toISOString() });
          reject(new Error('WebSocket connection failed'));
        };
      } catch (error) {
        clearTimeout(timeout);
        this.isConnecting = false;
        reject(error);
      }
    });
  }

  disconnect(): void {
    this.isDestroyed = true;
    this.cleanup();
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
    this.listeners.clear();
    this.emit('disconnected', { code: 1000, reason: 'Client disconnect' });
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  getStatus(): ConnectionStatus {
    if (this.isConnecting) return 'connecting';
    if (!this.ws) return 'disconnected';

    switch (this.ws.readyState) {
      case WebSocket.CONNECTING:
        return 'connecting';
      case WebSocket.OPEN:
        return 'connected';
      case WebSocket.CLOSING:
      case WebSocket.CLOSED:
        return 'disconnected';
      default:
        return 'error';
    }
  }

  getStats(): ConnectionStats {
    return { ...this.stats };
  }

  // --------------------------------------------------------------------------
  // Message Handling
  // --------------------------------------------------------------------------

  on<T = unknown>(eventType: string, handler: MessageHandler<T>): () => void {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, []);
    }
    this.listeners.get(eventType)!.push(handler as MessageHandler);

    // Return unsubscribe function
    return () => this.off(eventType, handler);
  }

  off<T = unknown>(eventType: string, handler?: MessageHandler<T>): void {
    if (!this.listeners.has(eventType)) return;

    if (!handler) {
      this.listeners.delete(eventType);
      return;
    }

    const handlers = this.listeners.get(eventType)!;
    const index = handlers.indexOf(handler as MessageHandler);
    if (index > -1) {
      handlers.splice(index, 1);
    }
  }

  send<T = unknown>(type: string, payload: T, priority: MessagePriority = 'medium'): void {
    const message: WebSocketMessage<T> = {
      type,
      payload,
      timestamp: new Date().toISOString(),
    };

    if (this.isConnected()) {
      try {
        this.ws!.send(JSON.stringify(message));
        this.stats.messagesSent++;
      } catch (error) {
        if (this.config.enableMessageBuffering) {
          this.bufferMessage(message, priority);
        }
      }
    } else if (this.config.enableMessageBuffering) {
      this.bufferMessage(message, priority);
    }
  }

  // --------------------------------------------------------------------------
  // Subscriptions (Convenience Methods)
  // --------------------------------------------------------------------------

  subscribeToDocumentUpdates(handler: MessageHandler): () => void {
    return this.on('document_processing_update', handler);
  }

  subscribeToQueueUpdates(handler: MessageHandler): () => void {
    return this.on('queue_update', handler);
  }

  subscribeToSystemMetrics(handler: MessageHandler): () => void {
    return this.on('system_metrics', handler);
  }

  subscribeToNotifications(handler: MessageHandler): () => void {
    return this.on('system_notification', handler);
  }

  subscribeToGraphUpdates(handler: MessageHandler): () => void {
    return this.on('graph_update', handler);
  }

  // --------------------------------------------------------------------------
  // Private Methods
  // --------------------------------------------------------------------------

  private initializeStats(): ConnectionStats {
    return {
      messagesReceived: 0,
      messagesSent: 0,
      reconnectAttempts: 0,
      currentLatency: 0,
      averageLatency: 0,
      errorCount: 0,
    };
  }

  private handleMessage(message: WebSocketMessage): void {
    // Notify type-specific listeners
    this.notifyListeners(message.type, message.payload);

    // Notify wildcard listeners
    this.notifyListeners('*', message);

    // Emit event for EventEmitter listeners
    this.emit(message.type, message.payload);
  }

  private notifyListeners(eventType: string, data: unknown): void {
    const handlers = this.listeners.get(eventType) || [];
    handlers.forEach((handler) => {
      try {
        handler(data);
      } catch (error) {
        console.error(`Error in WebSocket handler for ${eventType}:`, error);
      }
    });
  }

  private bufferMessage(message: WebSocketMessage, priority: MessagePriority): void {
    const bufferedMessage: BufferedMessage = {
      message,
      priority,
      retries: 0,
      timestamp: Date.now(),
    };

    // Insert based on priority
    const priorityValue = this.getPriorityValue(priority);
    let insertIndex = this.messageBuffer.length;
    for (let i = 0; i < this.messageBuffer.length; i++) {
      if (priorityValue > this.getPriorityValue(this.messageBuffer[i].priority)) {
        insertIndex = i;
        break;
      }
    }

    this.messageBuffer.splice(insertIndex, 0, bufferedMessage);

    // Remove old messages if buffer is full
    if (this.messageBuffer.length > this.config.bufferSize) {
      this.messageBuffer.pop();
    }
  }

  private getPriorityValue(priority: MessagePriority): number {
    switch (priority) {
      case 'high':
        return 3;
      case 'medium':
        return 2;
      case 'low':
        return 1;
    }
  }

  private flushBuffer(): void {
    if (!this.isConnected() || this.messageBuffer.length === 0) return;

    const maxPerFlush = 10;
    const toSend = this.messageBuffer.splice(0, maxPerFlush);

    toSend.forEach((buffered) => {
      try {
        this.ws!.send(JSON.stringify(buffered.message));
        this.stats.messagesSent++;
      } catch (error) {
        // Re-buffer high priority messages with limited retries
        if (buffered.priority === 'high' && buffered.retries < 3) {
          buffered.retries++;
          this.messageBuffer.unshift(buffered);
        }
      }
    });
  }

  private startBufferFlush(): void {
    if (this.bufferFlushTimer) {
      clearInterval(this.bufferFlushTimer);
    }
    this.bufferFlushTimer = setInterval(() => this.flushBuffer(), 1000);
  }

  private startHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
    }
    this.heartbeatTimer = setInterval(() => {
      if (this.isConnected() && this.config.enableLatencyMonitoring) {
        this.measureLatency();
      }
    }, this.config.heartbeatInterval);
  }

  private measureLatency(): void {
    const pingTime = Date.now();
    this.send('ping', { timestamp: pingTime }, 'high');

    const onPong = (data: { timestamp?: number }) => {
      if (data.timestamp === pingTime) {
        const latency = Date.now() - pingTime;
        this.updateLatencyStats(latency);
        this.off('pong', onPong);
      }
    };

    this.on('pong', onPong);
    setTimeout(() => this.off('pong', onPong), 5000);
  }

  private updateLatencyStats(latency: number): void {
    this.stats.currentLatency = latency;
    this.latencyMeasurements.push(latency);
    if (this.latencyMeasurements.length > 100) {
      this.latencyMeasurements.shift();
    }
    this.stats.averageLatency =
      this.latencyMeasurements.reduce((sum, l) => sum + l, 0) / this.latencyMeasurements.length;
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
    }

    this.stats.reconnectAttempts++;
    if (this.stats.reconnectAttempts > this.config.maxReconnectAttempts) {
      console.info('WebSocket max reconnect attempts reached - real-time updates disabled');
      return;
    }

    const delay = this.config.reconnectInterval * Math.pow(2, this.stats.reconnectAttempts - 1);

    if (this.stats.reconnectAttempts === 1 || this.stats.reconnectAttempts >= this.config.maxReconnectAttempts) {
      console.log(`WebSocket reconnect attempt ${this.stats.reconnectAttempts}/${this.config.maxReconnectAttempts}`);
    }

    this.emit('reconnecting', { attempt: this.stats.reconnectAttempts, delay });

    this.reconnectTimer = setTimeout(() => {
      if (!this.isDestroyed) {
        this.connect().catch(() => {
          // Reconnect failure is handled in the connect method
        });
      }
    }, delay);
  }

  private cleanup(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
    if (this.bufferFlushTimer) {
      clearInterval(this.bufferFlushTimer);
      this.bufferFlushTimer = null;
    }
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  updateConnectionParams(token: string, organizationId: string): void {
    this.config.token = token;
    this.config.organizationId = organizationId;

    // Reconnect if currently connected
    if (this.isConnected()) {
      this.disconnect();
      this.isDestroyed = false; // Reset for reconnect
      this.connect().catch(console.error);
    }
  }
}

// ============================================================================
// Singleton Instance
// ============================================================================

let wsClient: WebSocketClient | null = null;

export function getWebSocketClient(): WebSocketClient | null {
  return wsClient;
}

export function initializeWebSocketClient(config: WebSocketConfig): WebSocketClient {
  if (wsClient) {
    wsClient.disconnect();
  }
  wsClient = new WebSocketClient(config);
  return wsClient;
}

export function cleanupWebSocketClient(): void {
  if (wsClient) {
    wsClient.disconnect();
    wsClient = null;
  }
}

// ============================================================================
// Default Export
// ============================================================================

export default WebSocketClient;
