/**
 * R4-L26 regression: pollProcessingStatus kept chaining setTimeout for up to
 * 20 minutes even after removeFromQueue()/cancelAllUploads() dropped the
 * item, and a 'cancelled' processing_status was never treated as terminal.
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

const backendResponse = {
  document_id: 'doc-poll',
  upload_id: 'doc-poll',
  id: 'doc-poll',
  title: 'poll.pdf',
  filename: 'poll.pdf',
  document_type: 'pdf',
  file_size_bytes: 3,
  file_size_mb: 0.001,
  mime_type: 'application/pdf',
  processing_status: 'queued',
  upload_timestamp: '2026-08-19T00:00:00Z',
  created_at: '2026-08-19T00:00:00Z',
  message: 'ok',
  upload_progress: 100,
};

const flush = async (ms: number): Promise<void> => {
  await vi.advanceTimersByTimeAsync(ms);
};

describe('uploadService poll lifecycle', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    uploadMock.mockReset();
    getMock.mockReset();
  });

  it('stops polling once the item is removed from the queue', async () => {
    uploadMock.mockResolvedValue(backendResponse);
    getMock.mockResolvedValue({
      document_id: 'doc-poll',
      processing_status: 'processing',
      is_embedded: false,
      is_indexed: false,
      processing_error: null,
    });

    const file = new File(['abc'], 'poll.pdf', { type: 'application/pdf' });
    const [id] = uploadService.addToQueue([file]);
    await flush(500); // upload resolves, first poll scheduled

    const callsBeforeRemoval = getMock.mock.calls.length;
    uploadService.removeFromQueue(id);

    await flush(60_000);
    expect(getMock.mock.calls.length).toBe(callsBeforeRemoval);
  });

  it('treats a cancelled processing_status as terminal', async () => {
    uploadMock.mockResolvedValue({ ...backendResponse, document_id: 'doc-cancel' });
    getMock.mockResolvedValue({
      document_id: 'doc-cancel',
      processing_status: 'cancelled',
      is_embedded: false,
      is_indexed: false,
      processing_error: null,
    });

    const file = new File(['abc'], 'cancel.pdf', { type: 'application/pdf' });
    const [id] = uploadService.addToQueue([file]);
    await flush(3000);

    const item = uploadService.getQueueItems().find(q => q.id === id);
    expect(item?.status).toBe('error');
    expect(item?.error).toBe('Processing cancelled');
  });
});
