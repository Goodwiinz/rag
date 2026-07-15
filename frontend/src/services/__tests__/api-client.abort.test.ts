import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

describe('APIClient abort handling', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    vi.useRealTimers();

    vi.doMock('@/lib/supabase/client', () => ({
      createClient: () => ({
        auth: {
          getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
        },
      }),
    }));
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('passes the caller signal to fetch and preserves explicit cancellation', async () => {
    const callerController = new AbortController();
    const abortError = new DOMException('caller cancelled', 'AbortError');
    const fetchMock = vi.fn((_url: RequestInfo | URL, init?: RequestInit) => {
      return new Promise<Response>((_resolve, reject) => {
        callerController.signal.addEventListener(
          'abort',
          () => {
            expect(init?.signal?.aborted).toBe(true);
            reject(abortError);
          },
          { once: true }
        );
      });
    });
    vi.stubGlobal('fetch', fetchMock);

    const { APIClient } = await import('../api-client');
    const client = new APIClient('http://api.test');
    const request = client.get('/messages', {
      signal: callerController.signal,
      retries: 2,
    });

    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    callerController.abort();

    await expect(request).rejects.toBe(abortError);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('does not retry an already-aborted caller request', async () => {
    const callerController = new AbortController();
    callerController.abort();
    const abortError = new DOMException('caller cancelled', 'AbortError');
    const fetchMock = vi.fn().mockRejectedValue(abortError);
    vi.stubGlobal('fetch', fetchMock);

    const { APIClient } = await import('../api-client');
    const client = new APIClient('http://api.test');

    await expect(
      client.get('/messages', {
        signal: callerController.signal,
        retries: 2,
      })
    ).rejects.toBe(abortError);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('still classifies the client timeout as a timeout error', async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn((_url: RequestInfo | URL, init?: RequestInit) => {
      return new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener(
          'abort',
          () => reject(new DOMException('timed out', 'AbortError')),
          { once: true }
        );
      });
    });
    vi.stubGlobal('fetch', fetchMock);

    const { APIClient } = await import('../api-client');
    const client = new APIClient('http://api.test');
    const request = client.get('/messages', { timeout: 25, retries: 0 });
    const rejection = expect(request).rejects.toMatchObject({
      name: 'APIError',
      message: 'Request timeout',
      error: { status_code: 408 },
    });

    await vi.advanceTimersByTimeAsync(25);
    await rejection;
  });
});
