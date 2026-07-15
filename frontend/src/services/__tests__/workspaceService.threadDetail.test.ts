import { beforeEach, describe, expect, it, vi } from 'vitest';

import { api } from '@/services/api-client';
import { workspaceService } from '@/services/workspaceService';

vi.mock('@/services/api-client', () => ({
  api: { get: vi.fn() },
}));

describe('workspaceService.getThread', () => {
  beforeEach(() => vi.clearAllMocks());

  it('can request metadata without transcript rows', async () => {
    vi.mocked(api.get).mockResolvedValue({ id: 'thread-1', messages: [] });

    await workspaceService.getThread('thread-1', { includeMessages: false });

    expect(api.get).toHaveBeenCalledWith(
      '/api/v2/threads/thread-1?include_messages=false'
    );
  });

  it('can explicitly request transcript rows', async () => {
    vi.mocked(api.get).mockResolvedValue({ id: 'thread-1', messages: [] });

    await workspaceService.getThread('thread-1', { includeMessages: true });

    expect(api.get).toHaveBeenCalledWith(
      '/api/v2/threads/thread-1?include_messages=true'
    );
  });
});
