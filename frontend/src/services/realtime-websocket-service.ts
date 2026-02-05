/**
 * Enhanced WebSocket Client Service
 * Handles WebSocket connections with automatic reconnection, message buffering, and performance monitoring
 */

import {
  WebSocketClientConfig,
  WebSocketMessage,
  WebSocketConnectionInfo,
  DocumentProcessingState,
  Channel,
  UpdateFrequency,
  MessagePriority
} from '../types/realtime-processing';

export interface WebSocketServiceCallbacks {
  onConnect?: (connectionInfo: WebSocketConnectionInfo) => void;
  onDisconnect?: (reason?: string) => void;
  onError?: (error: Error) => void;
  onReconnect?: () => void;
  onMessage?: (message: WebSocketMessage) => void;
}

export interface ConnectionMetrics {
  messagesSent: number;
  messagesReceived: number;
  bytesSent: number;
  bytesReceived: number;
  averageLatency: number;
  lastMessageAt: string;
  uptimeSeconds: number;
  reconnectAttempts: number;
}

class RealtimeWebSocketService {
  private static instance: RealtimeWebSocketService | null = null;
  private ws: WebSocket | null = null;
  private config: WebSocketClientConfig | null = null;
  private callbacks: WebSocketServiceCallbacks = {};
  private connectionInfo: WebSocketConnectionInfo | null = null;
  private metrics: ConnectionMetrics = {
    messagesSent: 0,
    messagesReceived: 0,
    bytesSent: 0,
    bytesReceived: 0,
    averageLatency: 0,
    lastMessageAt: '',
    uptimeSeconds: 0,
    reconnectAttempts: 0
  };

  private reconnectTimeout: NodeJS.Timeout | null = null;
  private heartbeatInterval: NodeJS.Timeout | null = null;
  private messageBuffer: WebSocketMessage[] = [];
  private batchTimeout: NodeJS.Timeout | null = null;
  private latencyMeasurements: number[] = [];
  private connectionStartTime: number = 0;

  // Message handlers
  private messageHandlers = new Map<string, Set<(message: WebSocketMessage) => void>>();
  private documentSubscriptions = new Set<string>();

  private constructor() {}

  public static getInstance(): RealtimeWebSocketService {
    if (!RealtimeWebSocketService.instance) {
      RealtimeWebSocketService.instance = new RealtimeWebSocketService();
    }
    return RealtimeWebSocketService.instance;
  }

  public async initialize(
    config: WebSocketClientConfig,
    callbacks: WebSocketServiceCallbacks = {}
  ): Promise<void> {
    this.config = config;
    this.callbacks = callbacks;

    try {
      await this.connect();
    } catch (error) {
      console.error('Failed to initialize WebSocket service:', error);
      throw error;
    }
  }

  private async connect(): Promise<void> {
    if (!this.config) {
      throw new Error('WebSocket configuration not set');
    }

    return new Promise((resolve, reject) => {
      try {
        // SECURITY: Pass token via Sec-WebSocket-Protocol, not URL
        this.ws = new WebSocket(this.buildWebSocketUrl(), this.buildWebSocketProtocols());
        this.connectionStartTime = Date.now();

        this.ws.onopen = () => {
          console.log('WebSocket connected');
          this.startHeartbeat();
          this.startMetricsCollection();
          this.flushMessageBuffer();
          this.setupConnectionInfo();
          this.callbacks.onConnect?.(this.connectionInfo!);
          resolve();
        };

        this.ws.onmessage = (event) => {
          this.handleMessage(event);
        };

        this.ws.onclose = (event) => {
          console.log('WebSocket disconnected:', event.code, event.reason);
          this.stopHeartbeat();
          this.stopMetricsCollection();
          this.handleDisconnect(event.code, event.reason);
          this.callbacks.onDisconnect?.(event.reason);
        };

        this.ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          const wsError = new Error(`WebSocket error: ${error}`);
          this.callbacks.onError?.(wsError);
          reject(wsError);
        };

      } catch (error) {
        reject(error);
      }
    });
  }

  private buildWebSocketUrl(): string {
    if (!this.config) {
      throw new Error('Configuration not set');
    }

    const { url, channels = [], frequency = UpdateFrequency.NORMAL } = this.config;

    // SECURITY: Build query parameters WITHOUT the token
    // Token is passed via Sec-WebSocket-Protocol header for security
    const params = new URLSearchParams({
      channels: channels.join(','),
      frequency: frequency,
      client_info: JSON.stringify(this.config.clientInfo || {})
    });

    return `${url}?${params.toString()}`;
  }

  private buildWebSocketProtocols(): string[] | undefined {
    if (!this.config?.token) {
      return undefined;
    }
    // SECURITY: Use Sec-WebSocket-Protocol for token authentication
    // Format: ["auth", token] where "auth" indicates auth protocol
    return ['auth', this.config.token];
  }

  private setupConnectionInfo(): void {
    if (!this.config) return;

    this.connectionInfo = {
      id: `conn_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      user_id: 'unknown', // This would be extracted from JWT token
      organization_id: 'unknown',
      connected_at: new Date().toISOString(),
      last_activity: new Date().toISOString(),
      last_heartbeat: new Date().toISOString(),
      client_ip: 'unknown',
      user_agent: typeof window !== 'undefined' ? window.navigator.userAgent : 'unknown',
      connection_metadata: this.config.clientInfo || {},
      subscription_channels: this.config.channels || [],
      is_active: true,
      message_count_sent: 0,
      message_count_received: 0,
      bytes_sent: 0,
      bytes_received: 0
    };
  }

  private handleMessage(event: MessageEvent): void {
    try {
      const message: WebSocketMessage = JSON.parse(event.data);
      this.updateMetrics('received', event.data.length);

      // Handle latency measurement for pong messages
      if (message.type === 'pong' && typeof message.payload?.timestamp === 'number') {
        const latency = Date.now() - message.payload.timestamp;
        this.recordLatency(latency);
      }

      this.callbacks.onMessage?.(message);

      // Dispatch to registered handlers
      const handlers = this.messageHandlers.get(message.type);
      if (handlers) {
        handlers.forEach(handler => {
          try {
            handler(message);
          } catch (error) {
            console.error('Error in message handler:', error);
          }
        });
      }

    } catch (error) {
      console.error('Error parsing WebSocket message:', error);
    }
  }

  private lastCloseCode: number = 0;

  private handleDisconnect(code: number, _reason?: string): void {
    this.metrics.reconnectAttempts++;
    this.lastCloseCode = code;

    // Check if we should attempt reconnection
    if (this.shouldReconnect(code)) {
      this.scheduleReconnect();
    } else {
      console.log('Max reconnection attempts reached');
    }
  }

  private shouldReconnect(code?: number): boolean {
    if (!this.config) return false;

    const closeCode = code ?? this.lastCloseCode;
    const isNormalClose = closeCode === 1000 || closeCode === 1001; // Normal closure
    const maxAttempts = this.config.maxReconnectAttempts ?? 5;
    const withinAttempts = this.metrics.reconnectAttempts < maxAttempts;
    const autoReconnect = this.config.autoReconnect !== false;

    return autoReconnect && !isNormalClose && withinAttempts;
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
    }

    if (!this.config) {
      console.error('Cannot schedule reconnect without config');
      return;
    }

    const baseDelay = this.config.reconnectDelay ?? 5000;
    const delay = baseDelay * Math.pow(2, this.metrics.reconnectAttempts - 1); // Exponential backoff

    console.log(`Scheduling reconnection in ${delay}ms (attempt ${this.metrics.reconnectAttempts})`);
    this.callbacks.onReconnect?.();

    this.reconnectTimeout = setTimeout(async () => {
      try {
        await this.connect();
      } catch (error) {
        console.error('Reconnection failed:', error);
      }
    }, delay);
  }

  private startHeartbeat(): void {
    if (!this.config) return;

    const interval = this.config.heartbeatInterval || 30000;

    this.heartbeatInterval = setInterval(() => {
      this.sendMessage({
        id: `heartbeat_${Date.now()}`,
        type: 'ping',
        payload: { timestamp: Date.now() },
        timestamp: new Date().toISOString(),
        priority: MessagePriority.LOW
      });
    }, interval);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  private startMetricsCollection(): void {
    // Update uptime every second
    const updateInterval = setInterval(() => {
      this.metrics.uptimeSeconds = Math.floor((Date.now() - this.connectionStartTime) / 1000);
    }, 1000);

    // Store interval ID for cleanup
    (this as any).metricsInterval = updateInterval;
  }

  private stopMetricsCollection(): void {
    const interval = (this as any).metricsInterval;
    if (interval) {
      clearInterval(interval);
    }
  }

  private updateMetrics(direction: 'sent' | 'received', byteSize: number): void {
    if (direction === 'sent') {
      this.metrics.messagesSent++;
      this.metrics.bytesSent += byteSize;
    } else {
      this.metrics.messagesReceived++;
      this.metrics.bytesReceived += byteSize;
    }
    this.metrics.lastMessageAt = new Date().toISOString();
  }

  private recordLatency(latency: number): void {
    this.latencyMeasurements.push(latency);

    // Keep only last 100 measurements
    if (this.latencyMeasurements.length > 100) {
      this.latencyMeasurements = this.latencyMeasurements.slice(-100);
    }

    // Calculate average
    this.metrics.averageLatency = Math.round(
      this.latencyMeasurements.reduce((sum, l) => sum + l, 0) / this.latencyMeasurements.length
    );
  }

  private flushMessageBuffer(): void {
    if (this.messageBuffer.length === 0) return;

    const messages = [...this.messageBuffer];
    this.messageBuffer = [];

    messages.forEach(message => {
      this.sendRawMessage(message);
    });
  }

  private sendRawMessage(message: WebSocketMessage): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      // Buffer message for when connection is restored
      this.messageBuffer.push(message);
      return;
    }

    try {
      const serialized = JSON.stringify(message);
      this.updateMetrics('sent', serialized.length);
      this.ws.send(serialized);
    } catch (error) {
      console.error('Error sending WebSocket message:', error);
      // Buffer message for retry
      this.messageBuffer.push(message);
    }
  }

  // Public API
  public sendMessage(message: WebSocketMessage): void {
    if (this.config?.enableBatching) {
      this.bufferMessage(message);
    } else {
      this.sendRawMessage(message);
    }
  }

  private bufferMessage(message: WebSocketMessage): void {
    this.messageBuffer.push(message);

    if (this.batchTimeout) {
      clearTimeout(this.batchTimeout);
    }

    this.batchTimeout = setTimeout(() => {
      this.flushMessageBuffer();
    }, this.config?.batchTimeout || 100);
  }

  public subscribeToChannel(channel: Channel): void {
    this.sendMessage({
      id: `subscribe_${channel}_${Date.now()}`,
      type: 'subscribe',
      payload: { channel },
      timestamp: new Date().toISOString(),
      target_channels: [channel]
    });
  }

  public unsubscribeFromChannel(channel: Channel): void {
    this.sendMessage({
      id: `unsubscribe_${channel}_${Date.now()}`,
      type: 'unsubscribe',
      payload: { channel },
      timestamp: new Date().toISOString(),
      target_channels: [channel]
    });
  }

  public subscribeToDocument(documentId: string): void {
    if (!this.documentSubscriptions.has(documentId)) {
      this.documentSubscriptions.add(documentId);
      this.sendMessage({
        id: `subscribe_doc_${documentId}_${Date.now()}`,
        type: 'subscribe',
        payload: { documentId, channels: [Channel.DOCUMENT_PROCESSING] },
        timestamp: new Date().toISOString()
      });
    }
  }

  public unsubscribeFromDocument(documentId: string): void {
    if (this.documentSubscriptions.has(documentId)) {
      this.documentSubscriptions.delete(documentId);
      this.sendMessage({
        id: `unsubscribe_doc_${documentId}_${Date.now()}`,
        type: 'unsubscribe',
        payload: { documentId, channels: [Channel.DOCUMENT_PROCESSING] },
        timestamp: new Date().toISOString()
      });
    }
  }

  public on(messageType: string, handler: (message: WebSocketMessage) => void): () => void {
    if (!this.messageHandlers.has(messageType)) {
      this.messageHandlers.set(messageType, new Set());
    }

    this.messageHandlers.get(messageType)!.add(handler);

    // Return unsubscribe function
    return () => {
      const handlers = this.messageHandlers.get(messageType);
      if (handlers) {
        handlers.delete(handler);
        if (handlers.size === 0) {
          this.messageHandlers.delete(messageType);
        }
      }
    };
  }

  public disconnect(): void {
    this.clearReconnectTimeout();
    this.stopHeartbeat();
    this.stopMetricsCollection();

    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }

    this.connectionInfo = null;
    this.documentSubscriptions.clear();
    this.messageHandlers.clear();
  }

  public reconnect(): void {
    this.disconnect();

    if (this.config) {
      setTimeout(async () => {
        try {
          await this.connect();
        } catch (error) {
          console.error('Manual reconnection failed:', error);
        }
      }, 1000);
    }
  }

  public getConnectionStatus(): 'connected' | 'disconnected' | 'connecting' | 'error' {
    if (!this.ws) return 'disconnected';

    switch (this.ws.readyState) {
      case WebSocket.CONNECTING:
        return 'connecting';
      case WebSocket.OPEN:
        return 'connected';
      case WebSocket.CLOSING:
        return 'disconnected'; // Map closing to disconnected for simpler state
      case WebSocket.CLOSED:
        return 'disconnected';
      default:
        return 'error';
    }
  }

  public getMetrics(): ConnectionMetrics {
    return { ...this.metrics };
  }

  public getConnectionInfo(): WebSocketConnectionInfo | null {
    return this.connectionInfo;
  }

  public getSubscribedDocuments(): string[] {
    return Array.from(this.documentSubscriptions);
  }

  private clearReconnectTimeout(): void {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
  }

  // Static factory method
  public static create(): RealtimeWebSocketService {
    return RealtimeWebSocketService.getInstance();
  }
}

// Export singleton instance
export const realtimeWebSocketService = RealtimeWebSocketService.create();

export default RealtimeWebSocketService;