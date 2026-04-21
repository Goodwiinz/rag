import { z } from 'zod';

describe('APIClient auth bootstrapping', () => {
  beforeEach(() => {
    jest.resetModules();
    jest.clearAllMocks();
  });

  it('loads auth before requestWithValidation', async () => {
    const getSession = jest.fn().mockResolvedValue({
      data: {
        session: {
          access_token: 'session-token',
          user: { user_metadata: { organization_id: 'org-123' } },
        },
      },
    });

    jest.doMock('@/lib/supabase/client', () => ({
      createClient: () => ({
        auth: {
          getSession,
        },
      }),
    }));

    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ value: 'ok' }),
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    const { APIClient } = await import('../api-client');
    const client = new APIClient('http://api.test');
    await client.requestWithValidation('/secure', z.object({ value: z.string() }));

    expect(getSession).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      'http://api.test/secure',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer session-token',
          'X-Organization-ID': 'org-123',
        }),
      })
    );
  });

  it('loads auth before uploadWithProgress requests', async () => {
    const getSession = jest.fn().mockResolvedValue({
      data: {
        session: {
          access_token: 'upload-token',
          user: { user_metadata: { organization_id: 'org-upload' } },
        },
      },
    });

    jest.doMock('@/lib/supabase/client', () => ({
      createClient: () => ({
        auth: {
          getSession,
        },
      }),
    }));

    const setRequestHeader = jest.fn();
    class MockXMLHttpRequest {
      upload = { onprogress: null as ((e: ProgressEvent) => void) | null };
      onload: (() => void) | null = null;
      onerror: (() => void) | null = null;
      status = 200;
      responseText = '{}';
      statusText = 'OK';

      open() {}
      setRequestHeader = setRequestHeader;
      send() {
        if (this.onload) this.onload();
      }
    }

    // @ts-expect-error test override
    global.XMLHttpRequest = MockXMLHttpRequest;

    const { APIClient } = await import('../api-client');
    const client = new APIClient('http://api.test');
    const file = new File(['hello'], 'hello.txt', { type: 'text/plain' });
    await client.upload('/upload', file, { onProgress: () => {} });

    expect(getSession).toHaveBeenCalledTimes(1);
    expect(setRequestHeader).toHaveBeenCalledWith(
      'Authorization',
      'Bearer upload-token'
    );
    expect(setRequestHeader).toHaveBeenCalledWith(
      'X-Organization-ID',
      'org-upload'
    );
  });
});
