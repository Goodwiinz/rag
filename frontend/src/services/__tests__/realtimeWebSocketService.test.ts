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

    it('should connect successfully with auth token', async () => {
      await service.connect(testToken);

      const state = service.getConnectionState();
      expect(state.status).toBe('connected');
      expect(state.lastError).toBeUndefined();
    });

    it('should handle connection timeout', async () => {
      const timeoutConfig = { ...testConfig, connectionTimeout: 50 };
      const timeoutService = new RealtimeWebSocketService(timeoutConfig);

      await expect(timeoutService.connect(testToken)).rejects.toThrow('Connection timeout');
      timeoutService.destroy();
    });

    it('should disconnect cleanly', async () => {
      await service.connect(testToken);
      expect(service.getConnectionState().status).toBe('connected');

      service.disconnect();
      expect(service.getConnectionState().status).toBe('disconnected');
    });

    it('should not connect without auth token', async () => {
      await expect(service.connect('')).rejects.toThrow();
    });
  });

  describe('Message Handling', () => {
    beforeEach(async () => {
      await service.connect(testToken);
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

    it('should handle message size limit', () => {
      const largeMessage: WebSocketMessage = {
        type: 'test',
        payload: { data: 'x'.repeat(2 * 1024 * 1024) }, // 2MB message
        timestamp: new Date().toISOString()
      };

      expect(() => service.send(largeMessage)).toThrow('Message size exceeds limit');
    });

    it('should subscribe and receive messages', async () => {
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

    it('should emit performance metrics', () => {
      const handler = jest.fn();
      service.onPerformanceUpdate(handler);

      // Fast forward time to trigger performance monitoring
      jest.advanceTimersByTime(5000);

      expect(handler).toHaveBeenCalledWith(
        expect.objectContaining({
          connectionLatency: expect.any(Number),
          messageRate: expect.any(Number)
        })
      );
    });
  });

  describe('Error Handling', () => {
    it('should handle connection errors gracefully', async () => {
      const handler = jest.fn();
      service.onConnectionChange(handler);

      // Simulate connection error
      const errorService = new RealtimeWebSocketService({
        ...testConfig,
        url: 'ws://invalid-url-that-fails'
      });

      await expect(errorService.connect(testToken)).rejects.toThrow();

      const state = errorService.getConnectionState();
      expect(state.status).toBe('error');
      expect(state.lastError).toBeDefined();

      errorService.destroy();
    });

    it('should handle malformed messages', async () => {
      await service.connect(testToken);

      const handler = jest.fn();
      service.subscribe('test', handler);

      const ws = (service as any).ws;

      // Send malformed JSON
      expect(() => {
        ws.onmessage?.(new MessageEvent('message', { data: 'invalid json' }));
      }).not.toThrow();

      expect(handler).not.toHaveBeenCalled();
    });

    it('should handle handler errors without crashing', async () => {
      await service.connect(testToken);

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
    it('should attempt reconnection on unexpected disconnect', async () => {
      await service.connect(testToken);

      const ws = (service as any).ws;
      // Simulate unexpected close (not code 1000)
      ws.simulateClose(1006);

      expect(service.getConnectionState().status).toBe('disconnected');

      // Fast forward time to trigger reconnection
      jest.advanceTimersByTime(testConfig.reconnectInterval);

      // Should attempt reconnection
      expect(service.getConnectionState().reconnectionAttempts).toBeGreaterThan(0);
    });

    it('should not attempt reconnection on clean close', async () => {
      await service.connect(testToken);

      const ws = (service as any).ws;
      // Simulate clean close (code 1000)
      ws.simulateClose(1000);

      expect(service.getConnectionState().status).toBe('disconnected');
      expect(service.getConnectionState().reconnectionAttempts).toBe(0);
    });

    it('should respect max reconnection attempts', () => {
      service.connect(testToken);

      // Simulate multiple reconnection attempts
      for (let i = 0; i < testConfig.reconnectAttempts + 2; i++) {
        jest.advanceTimersByTime(testConfig.reconnectInterval * Math.pow(2, i));
      }

      const state = service.getConnectionState();
      expect(state.reconnectionAttempts).toBeLessThanOrEqual(testConfig.reconnectAttempts);
    });
  });

  describe('Performance Monitoring', () => {
    it('should track message rate', async () => {
      await service.connect(testToken);

      const handler = jest.fn();
      service.onPerformanceUpdate(handler);

      // Send some messages
      for (let i = 0; i < 10; i++) {
        service.send({
          type: 'test',
          payload: { index: i },
          timestamp: new Date().toISOString()
        });
      }

      // Fast forward time to trigger metrics calculation
      jest.advanceTimersByTime(5000);

      expect(handler).toHaveBeenCalledWith(
        expect.objectContaining({
          messageRate: expect.any(Number)
        })
      );
    });

    it('should calculate connection latency', () => {
      const metrics = service.getPerformanceMetrics();
      expect(metrics.connectionLatency).toBeGreaterThanOrEqual(0);
    });
  });

  describe('Document-Specific Methods', () => {
    it('should request document updates', async () => {
      await service.connect(testToken);

      const documentIds = ['doc1', 'doc2'];

      expect(() => {
        service.requestDocumentUpdates(documentIds);
      }).not.toThrow();
    });

    it('should request system metrics', async () => {
      await service.connect(testToken);

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