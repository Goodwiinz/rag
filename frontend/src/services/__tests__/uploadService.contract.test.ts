/**
 * R4-H4 regression: the upload request/response contract.
 *
 * POST /files/upload requires a `title` Form field — omitting it 422s every
 * upload. And the response is FileUploadResponse (document_id, ...), not the
 * old imagined { job_id, file_info } shape, so status polling must target
 * /processing/documents/{document_id}/status (the old code polled
 * /processing/jobs/undefined until the 20-minute timeout).
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/services/api-client', () => ({
  api: {
    upload: vi.fn(),
    get: vi.fn(),
  },
}));

import { api } from '@/services/api-client';
import { uploadService, UploadResponse } from '@/services/uploadService';

const uploadMock = vi.mocked(api.upload);
const getMock = vi.mocked(api.get);

const backendResponse: UploadResponse = {
  document_id: 'doc-123',
  upload_id: 'doc-123',
  id: 'doc-123',
  title: 'paper.pdf',
  filename: 'paper.pdf',
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

describe('uploadService upload contract', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    uploadMock.mockReset();
    getMock.mockReset();
  });

  it('sends the required title form field and polls document status', async () => {
    uploadMock.mockResolvedValue(backendResponse);
    getMock.mockResolvedValue({
      document_id: 'doc-123',
      processing_status: 'completed',
      is_embedded: true,
      is_indexed: true,
      processing_error: null,
    });

    const file = new File(['abc'], 'paper.pdf', { type: 'application/pdf' });
    const [id] = uploadService.addToQueue([file]);
    await flush(500);

    expect(uploadMock).toHaveBeenCalledWith(
      '/files/upload',
      file,
      expect.objectContaining({
        metadata: expect.objectContaining({ title: 'paper.pdf' }),
      })
    );

    // Poll fires against the document-status endpoint with the real id.
    await flush(2500);
    expect(getMock).toHaveBeenCalledWith(
      '/processing/documents/doc-123/status'
    );

    const item = uploadService
      .getQueueItems()
      .find((queued) => queued.id === id);
    expect(item?.documentId).toBe('doc-123');
    expect(item?.status).toBe('completed');
  });

  it('surfaces processing_error when the document fails', async () => {
    uploadMock.mockResolvedValue({ ...backendResponse, document_id: 'doc-f' });
    getMock.mockResolvedValue({
      document_id: 'doc-f',
      processing_status: 'failed',
      is_embedded: false,
      is_indexed: false,
      processing_error: 'extraction blew up',
    });

    const file = new File(['abc'], 'bad.pdf', { type: 'application/pdf' });
    const [id] = uploadService.addToQueue([file]);
    await flush(3000);

    const item = uploadService
      .getQueueItems()
      .find((queued) => queued.id === id);
    expect(item?.status).toBe('error');
    expect(item?.error).toBe('extraction blew up');
  });
});
