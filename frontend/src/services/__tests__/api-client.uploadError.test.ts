import { beforeEach, describe, expect, it, vi } from 'vitest';

/**
 * R4-M24: a failed upload (api.upload → uploadWithProgress, the XHR path)
 * used to discard the backend's error body and reject with only
 * `xhr.statusText` (e.g. "Unprocessable Entity"), hiding the real
 * FileValidationError message ("File extension '.exe' is not allowed",
 * "File size (...) exceeds maximum allowed size (...)", etc). The XHR error
 * branch must parse the same `{ error: { message, ... } }` envelope
 * handleErrorResponse() parses for every other request path.
 */
describe('APIClient upload error surfacing', () => {
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

  function mockXhr(status: number, statusText: string, responseText: string): void {
    class MockXMLHttpRequest {
      upload = { onprogress: null as ((e: ProgressEvent) => void) | null };
      onload: (() => void) | null = null;
      onerror: (() => void) | null = null;
      status = status;
      statusText = statusText;
      responseText = responseText;

      open(): void {}
      setRequestHeader(): void {}
      send(): void {
        if (this.onload) this.onload();
      }
    }
    // @ts-expect-error test override
    global.XMLHttpRequest = MockXMLHttpRequest;
  }

  it('surfaces the backend envelope message verbatim, not statusText', async () => {
    mockXhr(
      422,
      'Unprocessable Entity',
      JSON.stringify({
        error: {
          message: "File extension '.exe' is not allowed",
          status_code: 422,
          type: 'validation_error',
        },
      })
    );

    const { APIClient } = await import('../api-client');
    const client = new APIClient('http://api.test');
    const file = new File(['hi'], 'virus.exe', { type: 'application/octet-stream' });

    await expect(
      client.upload('/files/upload', file, { onProgress: () => {} })
    ).rejects.toMatchObject({
      error: { message: "File extension '.exe' is not allowed" },
    });
  });

  it('falls back to FastAPI-native `detail` when there is no envelope', async () => {
    mockXhr(
      413,
      'Payload Too Large',
      JSON.stringify({ detail: 'File size (999) exceeds maximum allowed size (100)' })
    );

    const { APIClient } = await import('../api-client');
    const client = new APIClient('http://api.test');
    const file = new File(['hi'], 'big.pdf', { type: 'application/pdf' });

    await expect(
      client.upload('/files/upload', file, { onProgress: () => {} })
    ).rejects.toMatchObject({
      error: { message: 'File size (999) exceeds maximum allowed size (100)' },
    });
  });

  it('falls back to statusText when the response body is not JSON', async () => {
    mockXhr(500, 'Internal Server Error', 'not json');

    const { APIClient } = await import('../api-client');
    const client = new APIClient('http://api.test');
    const file = new File(['hi'], 'ok.pdf', { type: 'application/pdf' });

    await expect(
      client.upload('/files/upload', file, { onProgress: () => {} })
    ).rejects.toMatchObject({
      error: { message: 'Internal Server Error' },
    });
  });
});
