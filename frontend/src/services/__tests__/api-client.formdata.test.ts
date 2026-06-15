import { beforeEach, describe, expect, it, vi } from 'vitest';
import { z } from 'zod';

/**
 * Regression: file uploads go through `api.post(endpoint, formData)`.
 * The generic client must NOT JSON-stringify a FormData body and must NOT
 * force `Content-Type: application/json` (which would strip the multipart
 * boundary the browser sets). Either defect makes the backend reject the
 * upload with 422 → the UI shows "Upload failed".
 */
describe('APIClient FormData handling', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();

    vi.doMock('@/lib/supabase/client', () => ({
      createClient: () => ({
        auth: {
          getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
        },
      }),
    }));
  });

  it('sends FormData as-is, not JSON-stringified, with no JSON Content-Type', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ document_id: 'doc-1' }),
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    const { APIClient } = await import('../api-client');
    const client = new APIClient('http://api.test');

    const formData = new FormData();
    formData.append('file', new File(['hi'], 'hi.txt', { type: 'text/plain' }));
    formData.append('title', 'hi');

    await client.post('/files/upload', formData);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0];

    // Body must be the FormData instance, never a JSON string.
    expect(init.body).toBeInstanceOf(FormData);
    expect(typeof init.body).not.toBe('string');

    // Content-Type must be absent so the browser sets the multipart boundary.
    const headers = init.headers as Record<string, string>;
    const contentType = headers['Content-Type'] ?? headers['content-type'];
    expect(contentType).toBeUndefined();
  });

  it('strips the JSON Content-Type for FormData routed through request() (upload without progress)', async () => {
    // This is the real upload entry point: api.upload(file) with no onProgress
    // goes through request(), NOT post()/bodyHeaders(). Its only protection is
    // the request()-level strip — getHeaders() injects DEFAULT_HEADERS'
    // application/json on every request. This guards the original 422 bug.
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ document_id: 'doc-2' }),
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    const { APIClient } = await import('../api-client');
    const client = new APIClient('http://api.test');

    const file = new File(['hi'], 'hi.txt', { type: 'text/plain' });
    await client.upload('/files/upload', file);

    const [, init] = fetchMock.mock.calls[0];
    expect(init.body).toBeInstanceOf(FormData);

    const headers = init.headers as Record<string, string>;
    const contentType = headers['Content-Type'] ?? headers['content-type'];
    expect(contentType).toBeUndefined();
  });

  it('sends no body (undefined) for a bodyless POST', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ ok: true }),
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    const { APIClient } = await import('../api-client');
    const client = new APIClient('http://api.test');

    await client.post('/documents/abc/reprocess');

    const [, init] = fetchMock.mock.calls[0];
    expect(init.body).toBeUndefined();
  });

  it('strips a case-insensitive content-type override for FormData', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ document_id: 'doc-3' }),
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    const { APIClient } = await import('../api-client');
    const client = new APIClient('http://api.test');

    const formData = new FormData();
    formData.append('file', new File(['x'], 'x.txt', { type: 'text/plain' }));

    // A caller that sneaks in a lowercase content-type must still be stripped.
    await client.post('/files/upload', formData, {
      headers: { 'content-type': 'application/json' },
    });

    const [, init] = fetchMock.mock.calls[0];
    const headers = init.headers as Record<string, string>;
    const leaked = Object.keys(headers).some(
      (k) => k.toLowerCase() === 'content-type'
    );
    expect(leaked).toBe(false);
  });

  it('strips Content-Type for FormData in requestWithValidation', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ value: 'ok' }),
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    const { APIClient } = await import('../api-client');
    const client = new APIClient('http://api.test');

    const formData = new FormData();
    formData.append('file', new File(['x'], 'x.txt', { type: 'text/plain' }));

    await client.requestWithValidation(
      '/validated-upload',
      z.object({ value: z.string() }),
      { method: 'POST', body: formData }
    );

    const [, init] = fetchMock.mock.calls[0];
    const headers = init.headers as Record<string, string>;
    const contentType = headers['Content-Type'] ?? headers['content-type'];
    expect(contentType).toBeUndefined();
  });

  it('wraps a non-serializable body in APIErrorClass instead of leaking a raw TypeError', async () => {
    const fetchMock = vi.fn();
    global.fetch = fetchMock as unknown as typeof fetch;

    const { APIClient } = await import('../api-client');
    const client = new APIClient('http://api.test');

    const circular: Record<string, unknown> = {};
    circular.self = circular;

    await expect(client.post('/data', circular)).rejects.toMatchObject({
      name: 'APIError',
      error: { type: 'validation_error' },
    });
    // Serialization fails before the network call — fetch must not run.
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('still JSON-encodes plain object bodies', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ ok: true }),
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    const { APIClient } = await import('../api-client');
    const client = new APIClient('http://api.test');

    await client.post('/documents/check-duplicate', { sha256: 'abc' });

    const [, init] = fetchMock.mock.calls[0];
    expect(init.body).toBe(JSON.stringify({ sha256: 'abc' }));
    const headers = init.headers as Record<string, string>;
    expect(headers['Content-Type']).toBe('application/json');
  });
});
