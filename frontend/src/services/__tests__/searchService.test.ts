import { APIErrorClass } from '@/types/api';
import { apiClient } from '../apiClient';
import { searchService } from '../searchService';

jest.mock('../apiClient', () => ({
  apiClient: {
    post: jest.fn(),
  },
}));

const mockApiClient = apiClient as jest.Mocked<typeof apiClient>;

describe('searchService deterministic routing', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('uses /search/hybrid with search_type hybrid by default', async () => {
    mockApiClient.post.mockResolvedValueOnce({
      search_id: 'search-1',
      query: 'prompt injection',
      results: [],
      search_time_ms: 25,
      total_results: 0,
    });

    const result = await searchService.search({ query: 'prompt injection' });

    expect(mockApiClient.post).toHaveBeenCalledWith(
      '/search/hybrid',
      expect.objectContaining({
        query: 'prompt injection',
        search_type: 'hybrid',
      })
    );
    expect(mockApiClient.post).toHaveBeenCalledTimes(1);
    expect(result).toMatchObject({
      success: true,
      data: {
        id: 'search-1',
        query: 'prompt injection',
        metrics: {
          latency_ms: 25,
          documents_retrieved: 0,
        },
        answer: {
          sources: [],
        },
      },
    });
  });

  it('falls back to /search/ with search_type fulltext on 404 from hybrid', async () => {
    mockApiClient.post
      .mockRejectedValueOnce(
        new APIErrorClass({
          message: 'Not Found',
          status_code: 404,
          type: 'http_error',
          details: { detail: 'Not Found' },
        })
      )
      .mockResolvedValueOnce({
        search_id: 'search-1',
        query: 'prompt injection',
        results: [
          {
            document_id: 'doc-1',
            title: 'Doc 1',
            content_preview: 'preview content',
            relevance_score: 0.78,
            document_type: 'PDF',
          },
        ],
        search_time_ms: 25,
        total_results: 1,
      });

    const result = await searchService.search({ query: 'prompt injection' });

    expect(mockApiClient.post).toHaveBeenNthCalledWith(
      1,
      '/search/hybrid',
      expect.objectContaining({
        query: 'prompt injection',
        search_type: 'hybrid',
      })
    );
    expect(mockApiClient.post).toHaveBeenNthCalledWith(
      2,
      '/search/',
      expect.objectContaining({
        query: 'prompt injection',
        search_type: 'fulltext',
      })
    );
    expect(mockApiClient.post).toHaveBeenCalledTimes(2);
    expect(result).toMatchObject({
      success: true,
      data: {
        id: 'search-1',
        query: 'prompt injection',
        answer: {
          sources: [
            {
              document_id: 'doc-1',
              document_title: 'Doc 1',
              snippet: 'preview content',
              confidence: 0.78,
              file_type: 'pdf',
            },
          ],
        },
        metrics: {
          latency_ms: 25,
          documents_retrieved: 1,
        },
      },
    });
  });

  it('does not fall back for non-404 hybrid failures and returns success false', async () => {
    mockApiClient.post.mockRejectedValueOnce(
      new APIErrorClass({
        message: 'Server Error',
        status_code: 500,
        type: 'http_error',
        details: { detail: 'Internal Server Error' },
      })
    );

    const result = await searchService.search({ query: 'prompt injection' });

    expect(mockApiClient.post).toHaveBeenCalledTimes(1);
    expect(mockApiClient.post).toHaveBeenNthCalledWith(
      1,
      '/search/hybrid',
      expect.objectContaining({
        query: 'prompt injection',
        search_type: 'hybrid',
      })
    );
    expect(result).toMatchObject({
      success: false,
      message: 'Server Error',
    });
  });

  it('falls back on Axios-style 404 error response and preserves payload mapping shape', async () => {
    mockApiClient.post
      .mockRejectedValueOnce({
        message: 'Request failed with status code 404',
        response: {
          status: 404,
        },
      })
      .mockResolvedValueOnce({
        search_id: 'search-2',
        query: 'vector search',
        results: [
          {
            document_id: 'doc-2',
            title: 'Doc 2',
            content_preview: 'fallback preview',
            relevance_score: 0.55,
            document_type: 'txt',
          },
        ],
        search_time_ms: 33,
        total_results: 1,
      });

    const result = await searchService.search({ query: 'vector search' });

    expect(mockApiClient.post).toHaveBeenCalledTimes(2);
    expect(mockApiClient.post).toHaveBeenNthCalledWith(
      2,
      '/search/',
      expect.objectContaining({
        query: 'vector search',
        search_type: 'fulltext',
      })
    );
    expect(result).toMatchObject({
      success: true,
      data: {
        id: 'search-2',
        query: 'vector search',
        answer: {
          sources: [
            {
              document_id: 'doc-2',
              document_title: 'Doc 2',
              snippet: 'fallback preview',
              confidence: 0.55,
              file_type: 'txt',
            },
          ],
        },
        metrics: {
          latency_ms: 33,
          documents_retrieved: 1,
        },
      },
    });
  });
});
