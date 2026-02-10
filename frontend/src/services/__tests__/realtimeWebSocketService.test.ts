/**
 * Real-time WebSocket Service Tests
 */

import { RealtimeWebSocketService } from '../realtimeWebSocketService';
import type { WebSocketMessage } from '@/types/realtime-processing';

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

    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN;
      this.onopen?.(new Event('open'));
    }, 10);
  }

  send(data: string): void {
    if (this.readyState !== MockWebSocket.OPEN) {
      throw new Error('WebSocket is not open');
    }
    this.onmessage?.(new MessageEvent('message', { data }));
  }

  close(code?: number, reason?: string): void {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.(new CloseEvent('close', { code: code || 1000, reason }));
  }

  simulateMessage(data: WebSocketMessage): void {
    this.onmessage?.(
      new MessageEvent('message', {
        data: JSON.stringify(data),
      })
    );
  }

  simulateClose(code: number = 1000, reason?: string): void {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.(new CloseEvent('close', { code, reason }));
  }
}

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
    jest.useFakeTimers();
    service = new RealtimeWebSocketService(testConfig);
  });

  afterEach(() => {
    service.destroy();
    jest.useRealTimers();
    jest.clearAllMocks();
  });

  it('initializes disconnected', () => {
    const state = service.getConnectionState();
    expect(state.status).toBe('disconnected');
    expect(state.reconnectionAttempts).toBe(0);
  });

  it('connect transitions to connected after open event', async () => {
    await service.connect(testToken);

    expect(service.getConnectionState().status).toBe('connecting');
    jest.advanceTimersByTime(20);
    expect(service.getConnectionState().status).toBe('connected');

    const ws = (service as any).ws as MockWebSocket;
    expect(ws.url).toContain('token=test-token');
  });

  it('send while disconnected does not throw', () => {
    const msg: WebSocketMessage = {
      type: 'test',
      payload: { data: 'x' },
      timestamp: new Date().toISOString(),
    };

    expect(() => service.send(msg)).not.toThrow();
  });

  it('dispatches subscribed message handlers', async () => {
    await service.connect(testToken);
    jest.advanceTimersByTime(20);

    const handler = jest.fn();
    const unsubscribe = service.subscribe('test_type', handler);

    const msg: WebSocketMessage = {
      type: 'test_type',
      payload: { value: 1 },
      timestamp: new Date().toISOString(),
    };

    const ws = (service as any).ws as MockWebSocket;
    ws.simulateMessage(msg);

    expect(handler).toHaveBeenCalledWith(msg);

    unsubscribe();
    ws.simulateMessage(msg);
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('ignores malformed JSON messages without throwing', async () => {
    await service.connect(testToken);
    jest.advanceTimersByTime(20);

    const ws = (service as any).ws as MockWebSocket;

    expect(() => {
      ws.onmessage?.(new MessageEvent('message', { data: 'invalid json' }));
    }).not.toThrow();
  });

  it('attempts reconnection on unexpected close', async () => {
    await service.connect(testToken);
    jest.advanceTimersByTime(20);

    const ws = (service as any).ws as MockWebSocket;
    ws.simulateClose(1006);

    jest.advanceTimersByTime(testConfig.reconnectInterval);

    expect(service.getConnectionState().reconnectionAttempts).toBeGreaterThan(0);
  });

  it('does not reconnect on clean close', async () => {
    await service.connect(testToken);
    jest.advanceTimersByTime(20);

    const ws = (service as any).ws as MockWebSocket;
    ws.simulateClose(1000);

    jest.advanceTimersByTime(testConfig.reconnectInterval * 2);

    expect(service.getConnectionState().status).toBe('disconnected');
    expect(service.getConnectionState().reconnectionAttempts).toBe(0);
  });

  it('destroy cleans up and disconnects', async () => {
    await service.connect(testToken);
    jest.advanceTimersByTime(20);

    service.destroy();

    expect(service.getConnectionState().status).toBe('disconnected');
  });
});
