import { beforeEach, describe, expect, it, vi } from 'vitest';

/**
 * Regression: arXiv search/ingest/extract/track are slow AND non-idempotent.
 * They must go through `postWithLongTimeout`, which disables the client's
 * automatic retries — replaying a POST that already committed work server-side
 * would duplicate ingests/extractions (R6-M15). Since R6-M15 no HTTP verb is
 * auto-retried by default except idempotent ones (GET/HEAD/OPTIONS); callers
 * can still opt a known-idempotent endpoint in via an explicit `retries`.
 */
describe('APIClient.postWithLongTimeout', () => {
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

  const server500 = () => ({
    ok: false,
    status: 500,
    statusText: 'Internal Server Error',
    headers: new Headers({ 'content-type': 'application/json' }),
    json: async () => ({ error: { message: 'boom', status_code: 500 } }),
  });

  it('does NOT retry a 5xx failure (fires fetch exactly once)', async () => {
    const fetchMock = vi.fn().mockResolvedValue(server500());
    global.fetch = fetchMock as unknown as typeof fetch;

    const { APIClient } = await import('../api-client');
    const client = new APIClient('http://api.test');

    await expect(
      client.postWithLongTimeout('/arxiv/ingest', { paper_ids: ['1706.03762'] })
    ).rejects.toMatchObject({ name: 'APIError' });

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('plain post() no longer auto-retries non-idempotent POSTs (R6-M15)', async () => {
    const fetchMock = vi.fn().mockResolvedValue(server500());
    global.fetch = fetchMock as unknown as typeof fetch;

    const { APIClient } = await import('../api-client');
    const client = new APIClient('http://api.test');

    await expect(
      client.post('/arxiv/ingest', { paper_ids: ['1706.03762'] })
    ).rejects.toMatchObject({ name: 'APIError' });

    // R6-M15: POST is not idempotent — replaying a committed create would
    // duplicate it, so the default retry pass is GET/HEAD/OPTIONS only.
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('lets callers override retries explicitly', async () => {
    const fetchMock = vi.fn().mockResolvedValue(server500());
    global.fetch = fetchMock as unknown as typeof fetch;

    const { APIClient } = await import('../api-client');
    const client = new APIClient('http://api.test');

    await expect(
      client.postWithLongTimeout('/arxiv/ingest', undefined, { retries: 1 })
    ).rejects.toMatchObject({ name: 'APIError' });

    // retries: 1 → initial attempt + one retry = 2 fetches.
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
