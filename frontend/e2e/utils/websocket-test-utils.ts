import { Page, expect } from '@playwright/test';

/**
 * WebSocket Testing Utilities for Real-Time Document Processing
 *
 * Provides comprehensive WebSocket testing capabilities:
 * - Connection management and monitoring
 * - Message interception and validation
 * - Real-time status updates verification
 * - Error handling and reconnection testing
 * - Performance monitoring of WebSocket communications
 */

interface WebSocketMessage {
  type: string;
  payload: any;
  timestamp: number;
  documentId?: string;
}

interface ConnectionStatus {
  connected: boolean;
  reconnectAttempts: number;
  lastError?: string;
  lastHeartbeat?: number;
}

interface DocumentProcessingUpdate {
  documentId: string;
  status: 'uploading' | 'queued' | 'processing' | 'ocr' | 'transcription' | 'embedding' | 'completed' | 'error';
  progress: number;
  stage?: string;
  error?: string;
  metadata?: Record<string, any>;
}

export class WebSocketTestUtils {
  private page: Page;
  private wsUrl: string;
  private messageLog: WebSocketMessage[] = [];
  private connectionStatus: ConnectionStatus = {
    connected: false,
    reconnectAttempts: 0
  };
  private monitoringInterval?: NodeJS.Timeout;
  private messageHandlers: Map<string, Function[]> = new Map();

  constructor(page: Page, wsUrl?: string) {
    this.page = page;
    this.wsUrl = wsUrl || this.getDefaultWebSocketUrl();
    this.setupWebSocketMonitoring();
  }

  /**
   * Get default WebSocket URL based on current environment
   */
  private getDefaultWebSocketUrl(): string {
    const baseUrl = this.page.context().baseUrl() || 'http://localhost:3000';
    return baseUrl.replace('http', 'ws') + '/ws';
  }

  /**
   * Set up WebSocket monitoring and interception
   */
  private async setupWebSocketMonitoring(): Promise<void> {
    // Intercept WebSocket connections
    await this.page.route('**/ws', async (route) => {
      // Continue with the WebSocket connection but add monitoring
      await route.continue();
    });

    // Set up monitoring of WebSocket messages
    await this.page.evaluate(() => {
      // Store original WebSocket
      const OriginalWebSocket = window.WebSocket;

      // Override WebSocket constructor for monitoring
      (window as any).WebSocket = function(url: string, protocols?: string | string[]) {
        const ws = new OriginalWebSocket(url, protocols);

        // Store monitoring data
        (ws as any).__monitoring = {
          url,
          messages: [],
          connectionTime: Date.now(),
          reconnectAttempts: 0
        };

        // Override send method to intercept messages
        const originalSend = ws.send.bind(ws);
        ws.send = function(data: string) {
          try {
            const message = JSON.parse(data);
            (ws as any).__monitoring.messages.push({
              direction: 'outgoing',
              timestamp: Date.now(),
              data: message
            });
          } catch (e) {
            // Not JSON, just store as string
            (ws as any).__monitoring.messages.push({
              direction: 'outgoing',
              timestamp: Date.now(),
              data: data
            });
          }
          return originalSend(data);
        };

        // Override event listeners to capture incoming messages
        const originalAddEventListener = ws.addEventListener.bind(ws);
        ws.addEventListener = function(type: string, listener: any) {
          if (type === 'message') {
            const wrappedListener = function(event: MessageEvent) {
              try {
                const message = JSON.parse(event.data);
                (ws as any).__monitoring.messages.push({
                  direction: 'incoming',
                  timestamp: Date.now(),
                  data: message
                });

                // Emit to global message handler for test access
                window.dispatchEvent(new CustomEvent('ws-message', {
                  detail: { message, url: (ws as any).__monitoring.url }
                }));
              } catch (e) {
                (ws as any).__monitoring.messages.push({
                  direction: 'incoming',
                  timestamp: Date.now(),
                  data: event.data
                });
              }
              return listener(event);
            };
            return originalAddEventListener(type, wrappedListener);
          }
          return originalAddEventListener(type, listener);
        };

        return ws;
      };
    });

    // Set up message listener
    await this.page.exposeFunction('__onWebSocketMessage', (message: any) => {
      this.handleWebSocketMessage(message);
    });

    // Start monitoring connection status
    this.startConnectionMonitoring();
  }

  /**
   * Monitor WebSocket connection status
   */
  private startConnectionMonitoring(): void {
    this.monitoringInterval = setInterval(async () => {
      const status = await this.getConnectionStatus();
      this.connectionStatus = {
        ...this.connectionStatus,
        connected: status === 'connected'
      };
    }, 1000);
  }

  /**
   * Handle incoming WebSocket messages
   */
  private handleWebSocketMessage(message: any): void {
    const wsMessage: WebSocketMessage = {
      type: message.type || 'unknown',
      payload: message.payload || message,
      timestamp: Date.now(),
      documentId: message.documentId
    };

    this.messageLog.push(wsMessage);

    // Trigger registered message handlers
    const handlers = this.messageHandlers.get(wsMessage.type) || [];
    handlers.forEach(handler => {
      try {
        handler(wsMessage);
      } catch (error) {
        console.error('Error in WebSocket message handler:', error);
      }
    });

    // Handle document processing updates
    if (wsMessage.type === 'document_status_update' && wsMessage.documentId) {
      this.messageHandlers.get(`document_${wsMessage.documentId}`)?.forEach(handler => {
        try {
          handler(wsMessage);
        } catch (error) {
          console.error('Error in document-specific message handler:', error);
        }
      });
    }
  }

  /**
   * Get current WebSocket connection status
   */
  async getConnectionStatus(): Promise<'connected' | 'disconnected' | 'error'> {
    const status = await this.page.evaluate(() => {
      const websockets = Array.from(document.all)
        .filter(el => (el as any).__monitoring)
        .map(el => (el as any).__monitoring);

      if (websockets.length === 0) return 'disconnected';

      const latestWs = websockets[websockets.length - 1];
      if (latestWs.socket?.readyState === WebSocket.OPEN) return 'connected';
      if (latestWs.socket?.readyState === WebSocket.CLOSED) return 'disconnected';
      if (latestWs.socket?.readyState === WebSocket.CONNECTING) return 'connected'; // Connecting state

      return 'error';
    });

    return status as 'connected' | 'disconnected' | 'error';
  }

  /**
   * Wait for WebSocket connection to be established
   */
  async waitForConnection(timeout: number = 10000): Promise<void> {
    const startTime = Date.now();

    while (Date.now() - startTime < timeout) {
      const status = await this.getConnectionStatus();
      if (status === 'connected') {
        return;
      }
      await this.page.waitForTimeout(100);
    }

    throw new Error(`WebSocket connection not established within ${timeout}ms`);
  }

  /**
   * Get document processing updates for a specific document
   */
  async getDocumentUpdates(documentId: string): Promise<string[]> {
    const documentMessages = this.messageLog.filter(
      msg => msg.documentId === documentId && msg.type === 'document_status_update'
    );

    return documentMessages.map(msg => msg.payload?.status || msg.type);
  }

  /**
   * Wait for specific document processing status
   */
  async waitForDocumentStatus(
    documentId: string,
    expectedStatus: string,
    timeout: number = 60000
  ): Promise<DocumentProcessingUpdate> {
    const startTime = Date.now();

    return new Promise((resolve, reject) => {
      const checkStatus = () => {
        const message = this.messageLog.findLast(
          msg => msg.documentId === documentId &&
                 msg.type === 'document_status_update' &&
                 msg.payload?.status === expectedStatus
        );

        if (message) {
          resolve(message.payload as DocumentProcessingUpdate);
          return;
        }

        if (Date.now() - startTime > timeout) {
          reject(new Error(`Document ${documentId} did not reach status ${expectedStatus} within ${timeout}ms`));
          return;
        }

        // Check again in 500ms
        setTimeout(checkStatus, 500);
      };

      // Register a handler for new messages
      const handler = (msg: WebSocketMessage) => {
        if (msg.documentId === documentId &&
            msg.type === 'document_status_update' &&
            msg.payload?.status === expectedStatus) {
          resolve(msg.payload as DocumentProcessingUpdate);
        }
      };

      this.messageHandlers.set(`document_${documentId}`, [
        ...(this.messageHandlers.get(`document_${documentId}`) || []),
        handler
      ]);

      // Start checking
      checkStatus();
    });
  }

  /**
   * Mock WebSocket message for testing
   */
  async mockWebSocketMessage(message: WebSocketMessage): Promise<void> {
    await this.page.evaluate((msg) => {
      window.dispatchEvent(new CustomEvent('ws-message', {
        detail: { message: msg }
      }));
    }, message);
  }

  /**
   * Simulate WebSocket connection loss and reconnection
   */
  async simulateConnectionLoss(duration: number = 5000): Promise<void> {
    // Close existing WebSocket connections
    await this.page.evaluate(() => {
      const websockets = Array.from(document.all)
        .filter((el: any) => el.__monitoring?.socket)
        .map((el: any) => el.__monitoring.socket);

      websockets.forEach((ws: WebSocket) => {
        ws.close();
      });
    });

    // Wait for specified duration
    await this.page.waitForTimeout(duration);

    // Wait for reconnection
    await this.waitForConnection();
  }

  /**
   * Get WebSocket performance metrics
   */
  async getPerformanceMetrics(): Promise<{
    messagesReceived: number;
    messagesSent: number;
    connectionUptime: number;
    averageLatency: number;
  }> {
    return await this.page.evaluate(() => {
      const websockets = Array.from(document.all)
        .filter((el: any) => el.__monitoring)
        .map((el: any) => el.__monitoring);

      if (websockets.length === 0) {
        return {
          messagesReceived: 0,
          messagesSent: 0,
          connectionUptime: 0,
          averageLatency: 0
        };
      }

      const latestWs = websockets[websockets.length - 1];
      const messages = latestWs.messages || [];
      const connectionUptime = Date.now() - latestWs.connectionTime;

      const incomingMessages = messages.filter((msg: any) => msg.direction === 'incoming');
      const outgoingMessages = messages.filter((msg: any) => msg.direction === 'outgoing');

      // Calculate average latency for request-response pairs
      let totalLatency = 0;
      let latencyCount = 0;

      // Simple latency calculation based on timestamp differences
      for (let i = 1; i < messages.length; i++) {
        const current = messages[i];
        const previous = messages[i - 1];

        if (previous.direction === 'outgoing' && current.direction === 'incoming') {
          totalLatency += current.timestamp - previous.timestamp;
          latencyCount++;
        }
      }

      const averageLatency = latencyCount > 0 ? totalLatency / latencyCount : 0;

      return {
        messagesReceived: incomingMessages.length,
        messagesSent: outgoingMessages.length,
        connectionUptime,
        averageLatency
      };
    });
  }

  /**
   * Register custom message handler
   */
  registerMessageHandler(messageType: string, handler: Function): void {
    const handlers = this.messageHandlers.get(messageType) || [];
    handlers.push(handler);
    this.messageHandlers.set(messageType, handlers);
  }

  /**
   * Clear message handlers for a specific message type
   */
  clearMessageHandlers(messageType?: string): void {
    if (messageType) {
      this.messageHandlers.delete(messageType);
    } else {
      this.messageHandlers.clear();
    }
  }

  /**
   * Get all logged messages
   */
  getMessageLog(): WebSocketMessage[] {
    return [...this.messageLog];
  }

  /**
   * Clear message log
   */
  clearMessageLog(): void {
    this.messageLog = [];
  }

  /**
   * Cleanup resources
   */
  async cleanup(): Promise<void> {
    if (this.monitoringInterval) {
      clearInterval(this.monitoringInterval);
    }

    this.messageHandlers.clear();
    this.messageLog = [];
    this.connectionStatus = {
      connected: false,
      reconnectAttempts: 0
    };
  }
}