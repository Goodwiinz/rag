import { describe, expect, it, vi } from 'vitest';

import { exportThread } from '@/services/export-service';

const downloadPost = vi.fn();
vi.mock('@/services/api-client', () => ({
  api: {
    downloadPost: (...args: unknown[]) => downloadPost(...args),
  },
}));

describe('exportThread', () => {
  // Regression: api-client's baseURL already ends in /api/v1. Prefixing it
  // again produced POST /api/v1/api/v1/export/... -> 404, surfaced in the UI
  // as the generic "Export failed. Please try again." toast.
  it('requests a path relative to the api-client base, not a second /api/v1', async () => {
    await exportThread('thread-1', 'json');

    const [url] = downloadPost.mock.calls[0] as [string, string];
    expect(url).toMatch(/^\/export\/thread\/thread-1\?/);
    expect(url).not.toContain('/api/v1');
  });
});
