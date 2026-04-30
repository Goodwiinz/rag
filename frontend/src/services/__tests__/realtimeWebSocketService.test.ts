/**
 * Real-time WebSocket Service Tests
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
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
    vi.useFakeTimers();
    service = new RealtimeWebSocketService(testConfig);
  });

  afterEach(() => {
    service.destroy();
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it('initializes disconnected', () => {
    const state = service.getConnectionState();
    expect(state.status).toBe('disconnected');
    expect(state.reconnectionAttempts).toBe(0);
  });

  it('connect transitions to connected after open event', async () => {
    await service.connect(testToken);

    expect(service.getConnectionState().status).toBe('connecting');
    vi.advanceTimersByTime(20);
    expect(service.getConnectionState().status).toBe('connected');

    const ws = (service as any).ws as MockWebSocket;
    // Token should be in protocols (Sec-WebSocket-Protocol), NOT in URL
    expect(ws.url).not.toContain('token=');
    expect(ws.protocols).toContain('auth');
    expect(ws.protocols).toContain(testToken);
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
    vi.advanceTimersByTime(20);

    const handler = vi.fn();
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
    vi.advanceTimersByTime(20);

    const ws = (service as any).ws as MockWebSocket;

    expect(() => {
      ws.onmessage?.(new MessageEvent('message', { data: 'invalid json' }));
    }).not.toThrow();
  });

  it('attempts reconnection on unexpected close', async () => {
    await service.connect(testToken);
    vi.advanceTimersByTime(20);

    const ws = (service as any).ws as MockWebSocket;
    ws.simulateClose(1006);

    vi.advanceTimersByTime(testConfig.reconnectInterval);

    expect(service.getConnectionState().reconnectionAttempts).toBeGreaterThan(
      0
    );
  });

  it('does not reconnect on clean close', async () => {
    await service.connect(testToken);
    vi.advanceTimersByTime(20);

    const ws = (service as any).ws as MockWebSocket;
    ws.simulateClose(1000);

    vi.advanceTimersByTime(testConfig.reconnectInterval * 2);

    expect(service.getConnectionState().status).toBe('disconnected');
    expect(service.getConnectionState().reconnectionAttempts).toBe(0);
  });

  it('destroy cleans up and disconnects', async () => {
    await service.connect(testToken);
    vi.advanceTimersByTime(20);

    service.destroy();

    expect(service.getConnectionState().status).toBe('disconnected');
  });
});
