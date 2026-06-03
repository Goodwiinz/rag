import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Mocked } from 'vitest';
import { EnhancedDocumentService } from '@/services/enhancedDocumentService';
import { api } from '@/services/api-client';

vi.mock('@/services/api-client', () => ({
  api: {
    post: vi.fn(),
    get: vi.fn(),
    delete: vi.fn(),
  },
}));

const mockedApi = api as Mocked<typeof api>;
const originalApiUrl = process.env.NEXT_PUBLIC_API_URL;
const originalWsUrl = process.env.NEXT_PUBLIC_WS_URL;
const originalWebsocketUrl = process.env.NEXT_PUBLIC_WEBSOCKET_URL;
const originalTestOrigin = (
  globalThis as typeof globalThis & {
    __TEST_BROWSER_ORIGIN__?: string;
  }
).__TEST_BROWSER_ORIGIN__;

type ServiceWithPrivateWebSocketUrl = {
  getWebSocketUrl(path: string): string;
};

const restoreEnv = (key: string, value: string | undefined) => {
  if (value === undefined) {
    delete process.env[key];
    return;
  }

  process.env[key] = value;
};

describe('EnhancedDocumentService', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
  });

  afterEach(async () => {
    await vi.runOnlyPendingTimersAsync();
    vi.useRealTimers();
    restoreEnv('NEXT_PUBLIC_API_URL', originalApiUrl);
    restoreEnv('NEXT_PUBLIC_WS_URL', originalWsUrl);
    restoreEnv('NEXT_PUBLIC_WEBSOCKET_URL', originalWebsocketUrl);
    (
      globalThis as typeof globalThis & { __TEST_BROWSER_ORIGIN__?: string }
    ).__TEST_BROWSER_ORIGIN__ = originalTestOrigin;
  });

  it('derives upload progress WebSocket URLs from the deployed API origin', () => {
    delete process.env.NEXT_PUBLIC_API_URL;
    delete process.env.NEXT_PUBLIC_WS_URL;
    delete process.env.NEXT_PUBLIC_WEBSOCKET_URL;
    (
      globalThis as typeof globalThis & { __TEST_BROWSER_ORIGIN__?: string }
    ).__TEST_BROWSER_ORIGIN__ = 'https://dev-app.gen-text.app/documents';

    const service =
      new EnhancedDocumentService() as unknown as ServiceWithPrivateWebSocketUrl;

    expect(
      service.getWebSocketUrl('/api/v2/documents/upload/progress/abc/ws')
    ).toBe(
      'wss://dev-api.gen-text.app/api/v2/documents/upload/progress/abc/ws'
    );
  });

  it('polls document status when upload completes without a websocket', async () => {
    mockedApi.post.mockResolvedValue({
      document_id: 'doc-123',
      upload_id: 'upload-123',
      title: 'Upload Test',
      filename: 'upload-test.txt',
      document_type: 'document',
      file_size_bytes: 18,
      file_size_mb: 0,
      mime_type: 'text/plain',
      processing_status: 'queued',
      upload_progress: 100,
      message: 'File uploaded successfully',
      created_at: '2026-04-13T00:00:00.000Z',
    });

    mockedApi.get
      .mockResolvedValueOnce({
        document_id: 'doc-123',
        processing_status: 'processing',
        progress_percentage: 45,
        current_step: 'Extracting content',
      })
      .mockResolvedValueOnce({
        document_id: 'doc-123',
        processing_status: 'indexed',
        progress_percentage: 100,
        current_step: 'Indexed',
      });

    const service = new EnhancedDocumentService();
    const onProgress = vi.fn();
    const file = new File(['hello upload test'], 'upload-test.txt', {
      type: 'text/plain',
    });

    const result = await service.uploadDocument(
      file,
      { title: 'Upload Test' },
      onProgress
    );

    expect(result.response.document_id).toBe('doc-123');
    expect(result.websocket).toBeNull();

    await vi.advanceTimersByTimeAsync(4000);

    expect(mockedApi.get).toHaveBeenNthCalledWith(
      1,
      '/documents/doc-123/status'
    );
    expect(mockedApi.get).toHaveBeenNthCalledWith(
      2,
      '/documents/doc-123/status'
    );

    expect(onProgress).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'progress_update',
        upload_id: 'upload-123',
        progress_percentage: 45,
        current_step: 'Extracting content',
      })
    );
    expect(onProgress).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'upload_complete',
        upload_id: 'upload-123',
        result: expect.objectContaining({
          document_id: 'doc-123',
          title: 'Upload Test',
          status: 'indexed',
        }),
      })
    );
  });
});
