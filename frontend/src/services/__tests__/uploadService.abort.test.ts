/**
 * R4-M19 regression: uploadFile created an AbortController but never passed
 * its signal into api.upload, so removeFromQueue()'s controller.abort() did
 * nothing — the underlying request kept running.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

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

describe('uploadService abort wiring', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    uploadMock.mockReset();
    getMock.mockReset();
    uploadService.cancelAllUploads();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('aborts the api.upload signal when the item is removed from the queue', async () => {
    let capturedSignal: AbortSignal | undefined;
    uploadMock.mockImplementation((_endpoint, _file, options) => {
      capturedSignal = options?.signal;
      return new Promise(() => {}); // hang forever
    });

    const file = new File(['abc'], 'hangs.pdf', { type: 'application/pdf' });
    const [id] = uploadService.addToQueue([file]);
    await vi.advanceTimersByTimeAsync(10);

    expect(capturedSignal?.aborted).toBe(false);

    uploadService.removeFromQueue(id);

    expect(capturedSignal?.aborted).toBe(true);
  });
});
