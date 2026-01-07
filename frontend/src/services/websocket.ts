import {
    DocumentProcessingUpdate,
    QueryStatusUpdate,
    SystemNotification,
    WebSocketMessage
} from '@/types';

// Re-export types that are needed by other modules
export type WebSocketEventHandler = (data: any) => void;
export type { DocumentProcessingUpdate, QueryStatusUpdate, SystemNotification };

export class WebSocketManager {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 2000;
  private listeners: Map<string, WebSocketEventHandler[]> = new Map();
  private isConnecting = false;
  private connectionPromise: Promise<void> | null = null;

  constructor(private url: string, private token: string, private organizationId: string) {}

  /**
   * Connect to WebSocket with authentication
   */
  async connect(): Promise<void> {
    if (this.isConnecting || this.isConnected()) {
      return;
    }

    this.isConnecting = true;

    return new Promise((resolve, reject) => {
      try {
        // SECURITY: Only pass non-sensitive parameters in URL
        const wsUrl = new URL(this.url);
        wsUrl.searchParams.append('organization_id', this.organizationId);

        // SECURITY: Use Sec-WebSocket-Protocol for token authentication
        // Browser WebSocket API doesn't support custom headers, but the subprotocol
        // header is a secure way to pass authentication tokens (not logged/cached)
        const protocols = this.token ? ['auth', this.token] : undefined;

        this.ws = new WebSocket(wsUrl.toString(), protocols);

        this.ws.onopen = () => {
          console.log('WebSocket connected');
          this.isConnecting = false;
          this.reconnectAttempts = 0;
          this.emit('connected', { timestamp: new Date().toISOString() });
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            const message: WebSocketMessage = JSON.parse(event.data);
            this.emit(message.type, message.payload);
          } catch (error) {
            console.error('Error parsing WebSocket message:', error);
          }
        };

        this.ws.onclose = (event) => {
          console.log('WebSocket disconnected:', event.code, event.reason);
          this.isConnecting = false;
          this.emit('disconnected', {
            code: event.code,
            reason: event.reason,
            timestamp: new Date().toISOString()
          });

          // Attempt to reconnect if not explicitly closed
          if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
            this.attemptReconnect();
          }
        };

        this.ws.onerror = (error) => {
          // Only log detailed error on first attempt to reduce console spam
          if (this.reconnectAttempts === 0) {
            console.warn('WebSocket connection failed - real-time updates unavailable');
          }
          this.isConnecting = false;
          this.emit('error', { error, timestamp: new Date().toISOString() });
          reject(new Error('WebSocket connection failed'));
        };

      } catch (error) {
        this.isConnecting = false;
        reject(error);
      }
    });
  }

  /**
   * Check if WebSocket is connected
   */
  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  /**
   * Disconnect from WebSocket
   */
  disconnect(): void {
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
    this.listeners.clear();
    this.reconnectAttempts = 0;
  }

  /**
   * Add event listener for specific message type
   */
  on(eventType: string, handler: WebSocketEventHandler): void {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, []);
    }
    this.listeners.get(eventType)!.push(handler);
  }

  /**
   * Remove event listener
   */
  off(eventType: string, handler?: WebSocketEventHandler): void {
    if (!this.listeners.has(eventType)) {
      return;
    }

    if (!handler) {
      this.listeners.delete(eventType);
      return;
    }

    const handlers = this.listeners.get(eventType)!;
    const index = handlers.indexOf(handler);
    if (index > -1) {
      handlers.splice(index, 1);
    }
  }

  /**
   * Send message to server
   */
  send(type: string, payload: any): void {
    if (!this.isConnected()) {
      console.warn('WebSocket not connected, cannot send message');
      return;
    }

    const message: WebSocketMessage = {
      type,
      payload,
      timestamp: new Date().toISOString(),
    };

    this.ws!.send(JSON.stringify(message));
  }

  /**
   * Emit event to all listeners
   */
  private emit(eventType: string, data: any): void {
    const handlers = this.listeners.get(eventType) || [];
    handlers.forEach(handler => {
      try {
        handler(data);
      } catch (error) {
        console.error(`Error in WebSocket event handler for ${eventType}:`, error);
      }
    });
  }

  /**
   * Attempt to reconnect with exponential backoff
   */
  private attemptReconnect(): void {
    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

    // Only log first and last attempts to reduce console spam
    if (this.reconnectAttempts === 1 || this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log(`WebSocket reconnect attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts}`);
    }

    setTimeout(() => {
      if (this.reconnectAttempts <= this.maxReconnectAttempts) {
        this.connect().catch((error) => {
          // Only log on last attempt to reduce console spam
          if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.info('WebSocket unavailable - real-time updates disabled (this is expected for v1 API)');
          }
        });
      }
    }, delay);
  }

  /**
   * Get connection status
   */
  getStatus(): 'connecting' | 'connected' | 'disconnected' | 'error' {
    if (this.isConnecting) return 'connecting';
    if (!this.ws) return 'disconnected';

    switch (this.ws.readyState) {
      case WebSocket.CONNECTING: return 'connecting';
      case WebSocket.OPEN: return 'connected';
      case WebSocket.CLOSING: return 'disconnected';
      case WebSocket.CLOSED: return 'disconnected';
      default: return 'error';
    }
  }

  /**
   * Set connection parameters
   */
  updateConnectionParams(token: string, organizationId: string): void {
    this.token = token;
    this.organizationId = organizationId;

    // Reconnect if currently connected
    if (this.isConnected()) {
      this.disconnect();
      this.connect().catch(console.error);
    }
  }
}

// Singleton instance for the application
let wsManager: WebSocketManager | null = null;

export const getWebSocketManager = (): WebSocketManager | null => {
  return wsManager;
};

export const initializeWebSocket = (
  url: string,
  token: string,
  organizationId: string
): WebSocketManager => {
  if (wsManager) {
    wsManager.disconnect();
  }

  wsManager = new WebSocketManager(url, token, organizationId);
  return wsManager;
};

export const cleanupWebSocket = (): void => {
  if (wsManager) {
    wsManager.disconnect();
    wsManager = null;
  }
};