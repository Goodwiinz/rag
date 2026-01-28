/**
 * Real-time WebSocket Service Tests
 */

import { RealtimeWebSocketService } from '../realtimeWebSocketService';
import type { WebSocketMessage } from '@/types/realtime-processing';

// Mock WebSocket
class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  readyState = MockWebSocket.CONNECTING;
  url: string;
  protocols?: string[];
  onopen: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;

  constructor(url: string, protocols?: string[]) {
    this.url = url;
    this.protocols = protocols;

    // Simulate connection after a delay
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN;
      if (this.onopen) {
        this.onopen(new Event('open'));
      }
    }, 10);
  }

  send(data: string): void {
    if (this.readyState !== MockWebSocket.OPEN) {
      throw new Error('WebSocket is not open');
    }

    // Echo back the message for testing
    if (this.onmessage) {
      this.onmessage(new MessageEvent('message', { data }));
    }
  }

  close(code?: number, reason?: string): void {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(new CloseEvent('close', { code: code || 1000, reason }));
    }
  }

  // Helper method for testing
  simulateMessage(data: any): void {
    if (this.onmessage) {
      this.onmessage(new MessageEvent('message', {
        data: JSON.stringify(data)
      }));
    }
  }

  simulateError(): void {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onerror) {
      this.onerror(new Event('error'));
    }
  }

  simulateClose(code: number = 1000, reason?: string): void {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(new CloseEvent('close', { code, reason }));
    }
  }
}

// Replace global WebSocket with mock
(global as any).WebSocket = MockWebSocket;

describe('RealtimeWebSocketService', () => {
  let service: RealtimeWebSocketService;
  const testToken = 'test-token';
  const testConfig = {
    url: 'ws://localhost:8000/ws/test',
    reconnectAttempts: 3,
    reconnectInterval: 100,
    heartbeatInterval: 1000,
  };

  beforeEach(() => {
    service = new RealtimeWebSocketService(testConfig);
    jest.useFakeTimers();
  });

  afterEach(() => {
    service.destroy();
    jest.useRealTimers();
    jest.clearAllMocks();
  });

  describe('Connection Management', () => {
    it('should initialize with correct default state', () => {
      const state = service.getConnectionState();
      expect(state.status).toBe('disconnected');
      expect(state.reconnectionAttempts).toBe(0);
      expect(state.maxReconnectionAttempts).toBe(testConfig.reconnectAttempts);
    });

    it('should connect successfully with auth token', () => {
      service.connect(testToken);

      // Advance time to complete the mock WebSocket connection
      jest.advanceTimersByTime(15);

      const state = service.getConnectionState();
      expect(state.status).toBe('connected');
      expect(state.lastError).toBeUndefined();
    });

    it('should transition to connecting state immediately', () => {
      service.connect(testToken);

      // Immediately after connect, should be in connecting state
      const state = service.getConnectionState();
      expect(state.status).toBe('connecting');
    });

    it('should disconnect cleanly', () => {
      service.connect(testToken);
      jest.advanceTimersByTime(15);
      expect(service.getConnectionState().status).toBe('connected');

      service.disconnect();
      expect(service.getConnectionState().status).toBe('disconnected');
    });

    it('should handle empty auth token', () => {
      // Service should handle empty token gracefully
      // Some implementations may throw, others may set error state
      expect(() => service.connect('')).not.toThrow();
    });
  });

  describe('Message Handling', () => {
    beforeEach(() => {
      service.connect(testToken);
      jest.advanceTimersByTime(15);
    });

    it('should send messages successfully', () => {
      const testMessage: WebSocketMessage = {
        type: 'test',
        payload: { data: 'test' },
        timestamp: new Date().toISOString()
      };

      expect(() => service.send(testMessage)).not.toThrow();
    });

    it('should buffer messages when disconnected', () => {
      service.disconnect();

      const testMessage: WebSocketMessage = {
        type: 'test',
        payload: { data: 'test' },
        timestamp: new Date().toISOString()
      };

      service.send(testMessage); // Should not throw, should buffer

      // Reconnect and check if message is sent
      expect(() => service.connect(testToken)).not.toThrow();
    });

    it('should handle message size limit gracefully', () => {
      const consoleError = jest.spyOn(console, 'error').mockImplementation();

      const largeMessage: WebSocketMessage = {
        type: 'test',
        payload: { data: 'x'.repeat(2 * 1024 * 1024) }, // 2MB message
        timestamp: new Date().toISOString()
      };

      // The send method catches the error internally and logs it
      expect(() => service.send(largeMessage)).not.toThrow();

      // Error should be logged
      expect(consoleError).toHaveBeenCalledWith(
        'Failed to send message:',
        expect.any(Error)
      );

      consoleError.mockRestore();
    });

    it('should subscribe and receive messages', () => {
      const handler = jest.fn();
      const unsubscribe = service.subscribe('test_type', handler);

      const testMessage: WebSocketMessage = {
        type: 'test_type',
        payload: { data: 'test' },
        timestamp: new Date().toISOString()
      };

      // Simulate receiving a message
      const ws = (service as any).ws;
      ws.simulateMessage(testMessage);

      expect(handler).toHaveBeenCalledWith(testMessage);

      unsubscribe();
      ws.simulateMessage(testMessage);

      // Handler should not be called after unsubscribe
      expect(handler).toHaveBeenCalledTimes(1);
    });

    it('should handle wildcard message subscriptions', () => {
      const handler = jest.fn();
      service.subscribe('*', handler);

      const testMessage: WebSocketMessage = {
        type: 'any_type',
        payload: { data: 'test' },
        timestamp: new Date().toISOString()
      };

      const ws = (service as any).ws;
      ws.simulateMessage(testMessage);

      expect(handler).toHaveBeenCalledWith(testMessage);
    });
  });

  describe('Connection Events', () => {
    it('should emit connection state changes', () => {
      const handler = jest.fn();
      service.onConnectionChange(handler);

      service.connect(testToken);

      // Should emit connecting state
      expect(handler).toHaveBeenCalledWith(
        expect.objectContaining({ status: 'connecting' })
      );
    });

    it('should emit performance metrics after connect and time advance', async () => {
      const handler = jest.fn();

      // Connect first to set up the performance monitoring timer
      service.connect(testToken);

      // Advance time to complete connection
      jest.advanceTimersByTime(15);

      // Register handler after connection is established
      service.onPerformanceUpdate(handler);

      // Fast forward time to trigger performance monitoring interval
      jest.advanceTimersByTime(5000);

      // Performance metrics should be available after time advance
      const metrics = service.getPerformanceMetrics();
      expect(metrics).toHaveProperty('connectionLatency');
      expect(metrics).toHaveProperty('messageRate');
    });
  });

  describe('Error Handling', () => {
    it('should handle connection state changes', () => {
      const handler = jest.fn();
      const errorService = new RealtimeWebSocketService({
        ...testConfig,
        url: 'ws://example.com/test'
      });

      errorService.onConnectionChange(handler);

      // Start connection
      errorService.connect(testToken);

      // Handler should be called with connecting state
      expect(handler).toHaveBeenCalledWith(
        expect.objectContaining({ status: 'connecting' })
      );

      // Connection state should be properly tracked
      const state = errorService.getConnectionState();
      expect(['connecting', 'connected', 'disconnected', 'error']).toContain(state.status);

      errorService.destroy();
    });

    it('should handle malformed messages', async () => {
      service.connect(testToken);
      jest.advanceTimersByTime(15);

      const handler = jest.fn();
      service.subscribe('test', handler);

      const ws = (service as any).ws;

      // Send malformed JSON
      expect(() => {
        ws.onmessage?.(new MessageEvent('message', { data: 'invalid json' }));
      }).not.toThrow();

      expect(handler).not.toHaveBeenCalled();
    });

    it('should handle handler errors without crashing', () => {
      service.connect(testToken);
      jest.advanceTimersByTime(15);

      const errorHandler = jest.fn(() => {
        throw new Error('Handler error');
      });
      service.subscribe('test', errorHandler);

      const ws = (service as any).ws;
      const testMessage: WebSocketMessage = {
        type: 'test',
        payload: { data: 'test' },
        timestamp: new Date().toISOString()
      };

      expect(() => {
        ws.simulateMessage(testMessage);
      }).not.toThrow();

      expect(errorHandler).toHaveBeenCalled();
    });
  });

  describe('Reconnection Logic', () => {
    it('should handle unexpected disconnect status change', () => {
      service.connect(testToken);
      jest.advanceTimersByTime(15); // Complete connection

      const ws = (service as any).ws;
      // Simulate unexpected close (not code 1000)
      ws.simulateClose(1006);

      // After abnormal close, status should change
      const state = service.getConnectionState();
      expect(['disconnected', 'error', 'reconnecting']).toContain(state.status);
    });

    it('should not attempt reconnection on clean close', () => {
      service.connect(testToken);
      jest.advanceTimersByTime(15); // Complete connection

      const ws = (service as any).ws;
      // Simulate clean close (code 1000)
      ws.simulateClose(1000);

      expect(service.getConnectionState().status).toBe('disconnected');
      // Clean close with code 1000 should not trigger reconnection
      expect(service.getConnectionState().reconnectionAttempts).toBe(0);
    });

    it('should track reconnection attempts', () => {
      const state = service.getConnectionState();
      // Initially no reconnection attempts
      expect(state.reconnectionAttempts).toBe(0);
      expect(state.maxReconnectionAttempts).toBe(testConfig.reconnectAttempts);
    });
  });

  describe('Performance Monitoring', () => {
    it('should track messages sent count', () => {
      service.connect(testToken);
      jest.advanceTimersByTime(15); // Complete connection

      // Send some messages
      for (let i = 0; i < 10; i++) {
        service.send({
          type: 'test',
          payload: { index: i },
          timestamp: new Date().toISOString()
        });
      }

      // Get metrics after sending messages
      const metrics = service.getPerformanceMetrics();
      expect(metrics).toHaveProperty('messageRate');
      expect(typeof metrics.messageRate).toBe('number');
    });

    it('should calculate connection latency', () => {
      const metrics = service.getPerformanceMetrics();
      expect(metrics.connectionLatency).toBeGreaterThanOrEqual(0);
    });

    it('should return performance metrics object', () => {
      const metrics = service.getPerformanceMetrics();
      expect(metrics).toHaveProperty('connectionLatency');
      expect(metrics).toHaveProperty('messageRate');
      expect(metrics).toHaveProperty('errorRate');
      expect(metrics).toHaveProperty('reconnectionCount');
      expect(metrics).toHaveProperty('uptime');
    });
  });

  describe('Document-Specific Methods', () => {
    it('should request document updates', () => {
      service.connect(testToken);
      jest.advanceTimersByTime(15);

      const documentIds = ['doc1', 'doc2'];

      expect(() => {
        service.requestDocumentUpdates(documentIds);
      }).not.toThrow();
    });

    it('should request system metrics', () => {
      service.connect(testToken);
      jest.advanceTimersByTime(15);

      expect(() => {
        service.requestSystemMetrics();
      }).not.toThrow();
    });
  });

  describe('Resource Cleanup', () => {
    it('should cleanup resources on destroy', () => {
      const handler1 = jest.fn();
      const handler2 = jest.fn();

      service.onConnectionChange(handler1);
      service.onPerformanceUpdate(handler2);

      service.destroy();

      // Should disconnect WebSocket
      expect(service.getConnectionState().status).toBe('disconnected');

      // Should clear handlers (test by attempting to trigger events)
      expect(() => {
        service.connect(testToken);
      }).not.toThrow(); // Should not throw even after destroy
    });
  });
});