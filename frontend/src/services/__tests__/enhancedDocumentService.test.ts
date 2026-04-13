import { EnhancedDocumentService } from '@/services/enhancedDocumentService';
import { apiClient } from '@/services/apiClient';

jest.mock('@/services/apiClient', () => ({
  apiClient: {
    post: jest.fn(),
    get: jest.fn(),
    delete: jest.fn(),
  },
}));

const mockedApiClient = apiClient as jest.Mocked<typeof apiClient>;

describe('EnhancedDocumentService', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    jest.clearAllMocks();
  });

  afterEach(async () => {
    await jest.runOnlyPendingTimersAsync();
    jest.useRealTimers();
  });

  it('polls document status when upload completes without a websocket', async () => {
    mockedApiClient.post.mockResolvedValue({
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

    mockedApiClient.get
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
    const onProgress = jest.fn();
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

    await jest.advanceTimersByTimeAsync(4000);

    expect(mockedApiClient.get).toHaveBeenNthCalledWith(
      1,
      '/documents/doc-123/status'
    );
    expect(mockedApiClient.get).toHaveBeenNthCalledWith(
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
