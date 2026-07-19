/**
 * @deprecated This file is deprecated. Please migrate to the new unified WebSocket client.
 * Import from '@/services/websocket-client' instead.
 * 
 * Migration guide:
 * - Replace `EnhancedWebSocketService` with `WebSocketClient` from websocket-client
 * - Use `initializeWebSocketClient()` for singleton setup
 * - The new client includes all enhanced features (buffering, latency, priority queues)
 */

/**
 * Enhanced WebSocket Service for Real-Time Document Processing
 *
 * This service extends the existing WebSocket functionality with additional
 * features for the real-time processing dashboard including:
 * - Advanced reconnection logic with exponential backoff
 * - Message queuing and buffering
 * - Latency monitoring and performance metrics
 * - Comprehensive error handling
 * - Event-driven architecture
 */

import {
    WebSocketMessage
} from '@/types/realtime-processing';
import { EventEmitter } from 'events';
import { WebSocketManager } from './websocket';

// Enhanced configuration options
export interface EnhancedWebSocketConfig {
  url: string;
  token: string;
  organizationId: string;
  reconnectInterval?: number;
  maxReconnectionAttempts?: number;
  heartbeatInterval?: number;
  connectionTimeout?: number;
  messageQueueSize?: number;
  enableLatencyMonitoring?: boolean;
  enableMessageBuffering?: boolean;
  bufferSize?: number;
  bufferFlushInterval?: number;
}

// Connection statistics
export interface ConnectionStats {
  connectedAt?: string;
  lastMessageAt?: string;
  lastPingAt?: string;
  messagesReceived: number;
  messagesSent: number;
  reconnectAttempts: number;
  currentLatency: number;
  averageLatency: number;
  minLatency: number;
  maxLatency: number;
  connectionUptime: number;
  bufferFullEvents: number;
  errorCount: number;
}

// Message buffer entry
interface BufferedMessage {
  message: WebSocketMessage;
  timestamp: number;
  priority: 'high' | 'medium' | 'low';
  retries?: number;
}

export class EnhancedWebSocketService extends EventEmitter {
  private wsManager: WebSocketManager;
  private config: Required<EnhancedWebSocketConfig>;
  private messageBuffer: BufferedMessage[] = [];
  private bufferFlushTimer: NodeJS.Timeout | null = null;
  private heartbeatTimer: NodeJS.Timeout | null = null;
  private stats: ConnectionStats;
  private isDestroyed = false;
  private latencyMeasurements: number[] = [];

  constructor(config: EnhancedWebSocketConfig) {
    super();

    this.config = {
      reconnectInterval: config.reconnectInterval || 2000,
      maxReconnectionAttempts: config.maxReconnectionAttempts || 5,
      heartbeatInterval: config.heartbeatInterval || 30000,
      connectionTimeout: config.connectionTimeout || 10000,
      messageQueueSize: config.messageQueueSize || 1000,
      enableLatencyMonitoring: config.enableLatencyMonitoring !== false,
      enableMessageBuffering: config.enableMessageBuffering !== false,
      bufferSize: config.bufferSize || 100,
      bufferFlushInterval: config.bufferFlushInterval || 1000,
      ...config
    };

    this.stats = this.initializeStats();
    this.wsManager = new WebSocketManager(config.url, config.token, config.organizationId);
    this.setupEventHandlers();
  }

  /**
   * Initialize statistics
   */
  private initializeStats(): ConnectionStats {
    return {
      messagesReceived: 0,
      messagesSent: 0,
      reconnectAttempts: 0,
      currentLatency: 0,
      averageLatency: 0,
      minLatency: Infinity,
      maxLatency: 0,
      connectionUptime: 0,
      bufferFullEvents: 0,
      errorCount: 0
    };
  }

  /**
   * Set up event handlers for the underlying WebSocket manager
   */
  private setupEventHandlers(): void {
    // Connection events
    this.wsManager.on('connected', (data) => {
      this.handleConnected(data);
    });

    this.wsManager.on('disconnected', (data) => {
      this.handleDisconnected(data);
    });

    this.wsManager.on('error', (data) => {
      this.handleError(data);
    });

    // Message events
    this.wsManager.on('document_processing_update', (data) => {
      this.handleDocumentUpdate(data);
    });

    this.wsManager.on('queue_update', (data) => {
      this.handleQueueUpdate(data);
    });

    this.wsManager.on('system_metrics', (data) => {
      this.handleSystemMetrics(data);
    });

    this.wsManager.on('system_notification', (data) => {
      this.handleNotification(data);
    });
  }

  /**
   * Connect to WebSocket server
   */
  async connect(): Promise<void> {
    if (this.isDestroyed) {
      throw new Error('Service has been destroyed');
    }

    try {
      await this.wsManager.connect();
      this.startHeartbeat();
      this.startBufferFlush();
    } catch (error) {
      this.stats.errorCount++;
      this.emit('error', error);
      throw error;
    }
  }

  /**
   * Disconnect from WebSocket server
   */
  disconnect(): void {
    this.isDestroyed = true;
    this.cleanup();
    this.wsManager.disconnect();
    this.emit('disconnected');
  }

  /**
   * Check if connected
   */
  isConnected(): boolean {
    return this.wsManager.isConnected();
  }

  /**
   * Get connection status
   */
  getStatus(): string {
    return this.wsManager.getStatus();
  }

  /**
   * Get connection statistics
   */
  getStats(): ConnectionStats {
    // Calculate uptime
    if (this.stats.connectedAt) {
      this.stats.connectionUptime = Date.now() - new Date(this.stats.connectedAt).getTime();
    }

    return { ...this.stats };
  }

  /**
   * Send message with optional buffering
   */
  send(type: string, payload: any, priority: 'high' | 'medium' | 'low' = 'medium'): void {
    const message: WebSocketMessage = {
      type,
      payload,
      timestamp: new Date().toISOString()
    };

    if (this.isConnected()) {
      try {
        this.wsManager.send(type, payload);
        this.stats.messagesSent++;
        this.stats.lastMessageAt = new Date().toISOString();
      } catch (error) {
        this.bufferMessage(message, priority);
      }
    } else if (this.config.enableMessageBuffering) {
      this.bufferMessage(message, priority);
    }
  }

  /**
   * Buffer message for later sending
   */
  private bufferMessage(message: WebSocketMessage, priority: 'high' | 'medium' | 'low'): void {
    const bufferedMessage: BufferedMessage = {
      message,
      timestamp: Date.now(),
      priority,
      retries: 0
    };

    // Insert message based on priority
    let insertIndex = this.messageBuffer.length;
    for (let i = 0; i < this.messageBuffer.length; i++) {
      if (this.getPriorityValue(priority) > this.getPriorityValue(this.messageBuffer[i].priority)) {
        insertIndex = i;
        break;
      }
    }

    this.messageBuffer.splice(insertIndex, 0, bufferedMessage);

    // Remove old messages if buffer is full
    if (this.messageBuffer.length > this.config.bufferSize) {
      const removed = this.messageBuffer.pop();
      if (removed) {
        this.stats.bufferFullEvents++;
      }
    }
  }

  /**
   * Get numeric value for priority comparison
   */
  private getPriorityValue(priority: 'high' | 'medium' | 'low'): number {
    switch (priority) {
      case 'high': return 3;
      case 'medium': return 2;
      case 'low': return 1;
      default: return 1;
    }
  }

  /**
   * Flush buffered messages
   */
  private flushBuffer(): void {
    if (!this.isConnected() || this.messageBuffer.length === 0) {
      return;
    }

    const maxMessagesPerFlush = 10; // Prevent overwhelming the connection
    const messagesToSend = this.messageBuffer.splice(0, maxMessagesPerFlush);

    messagesToSend.forEach((bufferedMessage) => {
      try {
        this.wsManager.send(bufferedMessage.message.type, bufferedMessage.message.payload);
        this.stats.messagesSent++;
      } catch (error) {
        // Re-buffer high priority messages
        if (bufferedMessage.priority === 'high' && (bufferedMessage.retries || 0) < 3) {
          bufferedMessage.retries = (bufferedMessage.retries || 0) + 1;
          this.messageBuffer.unshift(bufferedMessage);
        }
      }
    });

    if (this.messageBuffer.length > 0) {
      this.emit('buffer_full', { remainingMessages: this.messageBuffer.length });
    }
  }

  /**
   * Start buffer flush timer
   */
  private startBufferFlush(): void {
    if (this.bufferFlushTimer) {
      clearInterval(this.bufferFlushTimer);
    }

    this.bufferFlushTimer = setInterval(() => {
      this.flushBuffer();
    }, this.config.bufferFlushInterval);
  }

  /**
   * Start heartbeat/ping mechanism
   */
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

  /**
   * Measure connection latency
   */
  private measureLatency(): void {
    const pingTime = Date.now();
    this.stats.lastPingAt = new Date().toISOString();

    // Send ping message
    this.send('ping', { timestamp: pingTime }, 'high');

    // Listen for pong response
    const onPong = (data: any) => {
      if (data.payload?.timestamp === pingTime) {
        const latency = Date.now() - pingTime;
        this.updateLatencyStats(latency);
        this.wsManager.off('pong', onPong);
      }
    };

    this.wsManager.on('pong', onPong);

    // Timeout for latency measurement
    setTimeout(() => {
      this.wsManager.off('pong', onPong);
    }, 5000);
  }

  /**
   * Update latency statistics
   */
  private updateLatencyStats(latency: number): void {
    this.stats.currentLatency = latency;
    this.stats.minLatency = Math.min(this.stats.minLatency, latency);
    this.stats.maxLatency = Math.max(this.stats.maxLatency, latency);

    // Keep only last 100 measurements for average calculation
    this.latencyMeasurements.push(latency);
    if (this.latencyMeasurements.length > 100) {
      this.latencyMeasurements.shift();
    }

    // Calculate average
    this.stats.averageLatency = this.latencyMeasurements.reduce((sum, l) => sum + l, 0) / this.latencyMeasurements.length;
  }

  /**
   * Handle connection established
   */
  private handleConnected(data: any): void {
    this.stats.connectedAt = new Date().toISOString();
    this.stats.reconnectAttempts = 0;
    this.emit('connected', data);
  }

  /**
   * Handle connection lost
   */
  private handleDisconnected(data: any): void {
    this.emit('disconnected', data);

    // Attempt reconnection if not destroyed
    if (!this.isDestroyed && data.code !== 1000) {
      this.stats.reconnectAttempts++;
      this.emit('reconnecting', { attempts: this.stats.reconnectAttempts });
    }
  }

  /**
   * Handle connection error
   */
  private handleError(data: any): void {
    this.stats.errorCount++;
    this.emit('error', data.error || new Error('WebSocket error'));
  }

  /**
   * Handle document update
   */
  private handleDocumentUpdate(data: any): void {
    this.stats.messagesReceived++;
    this.emit('document_update', data);
  }

  /**
   * Handle queue update
   */
  private handleQueueUpdate(data: any): void {
    this.stats.messagesReceived++;
    this.emit('queue_update', data);
  }

  /**
   * Handle system metrics
   */
  private handleSystemMetrics(data: any): void {
    this.stats.messagesReceived++;
    this.emit('system_metrics', data);
  }

  /**
   * Handle notification
   */
  private handleNotification(data: any): void {
    this.stats.messagesReceived++;
    this.emit('notification', data);
  }

  /**
   * Clean up resources
   */
  private cleanup(): void {
    if (this.bufferFlushTimer) {
      clearInterval(this.bufferFlushTimer);
      this.bufferFlushTimer = null;
    }

    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }

    this.messageBuffer = [];
    this.latencyMeasurements = [];
  }

  /**
   * Update connection parameters
   */
  updateConnectionParams(token: string, organizationId: string): void {
    this.config.token = token;
    this.config.organizationId = organizationId;
    this.wsManager.updateConnectionParams(token, organizationId);
  }

  /**
   * Get buffer status
   */
  getBufferStatus(): {
    size: number;
    maxSize: number;
    utilization: number;
    oldestMessageAge: number;
  } {
    const oldestMessage = this.messageBuffer[0];
    return {
      size: this.messageBuffer.length,
      maxSize: this.config.bufferSize,
      utilization: this.messageBuffer.length / this.config.bufferSize,
      oldestMessageAge: oldestMessage ? Date.now() - oldestMessage.timestamp : 0
    };
  }

  /**
   * Force flush all buffered messages
   */
  forceFlush(): void {
    while (this.messageBuffer.length > 0 && this.isConnected()) {
      this.flushBuffer();
    }
  }

  /**
   * Clear buffered messages
   */
  clearBuffer(): void {
    this.messageBuffer = [];
  }
}

// Singleton instance
let enhancedWebSocketService: EnhancedWebSocketService | null = null;

export function getEnhancedWebSocketService(): EnhancedWebSocketService | null {
  return enhancedWebSocketService;
}

export function initializeEnhancedWebSocket(config: EnhancedWebSocketConfig): EnhancedWebSocketService {
  if (enhancedWebSocketService) {
    enhancedWebSocketService.disconnect();
  }

  enhancedWebSocketService = new EnhancedWebSocketService(config);
  return enhancedWebSocketService;
}

export function cleanupEnhancedWebSocket(): void {
  if (enhancedWebSocketService) {
    enhancedWebSocketService.disconnect();
    enhancedWebSocketService = null;
  }
}

export default EnhancedWebSocketService;