/**
 * R4-M18 regression: error paths never set `completedAt`, so a failed item
 * survives every cleanupCompleted() sweep forever.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/services/api-client', () => ({
  api: {
    upload: vi.fn(),
    get: vi.fn(),
  },
}));

import { api } from '@/services/api-client';
import { uploadService } from '@/services/uploadService';

const uploadMock = vi.mocked(api.upload);
const getMock = vi.mocked(api.get);

const flush = async (ms: number): Promise<void> => {
  await vi.advanceTimersByTimeAsync(ms);
};

describe('uploadService failed upload cleanup', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    uploadMock.mockReset();
    getMock.mockReset();
  });

  it('marks a rejected upload completedAt so it is cleanable', async () => {
    uploadMock.mockRejectedValue(new Error('network exploded'));

    const file = new File(['abc'], 'fails.pdf', { type: 'application/pdf' });
    const [id] = uploadService.addToQueue([file]);
    await flush(500);

    const item = uploadService.getQueueItems().find(q => q.id === id);
    expect(item?.status).toBe('error');
    expect(item?.completedAt).toBeDefined();

    const removed = uploadService.cleanupCompleted(0);
    expect(removed).toBeGreaterThanOrEqual(1);
    expect(uploadService.getQueueItems().find(q => q.id === id)).toBeUndefined();
  });
});
