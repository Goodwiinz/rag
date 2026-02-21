import { APIErrorClass } from '@/types/api';
import { apiClient } from '../apiClient';
import { searchService } from '../searchService';

jest.mock('../apiClient', () => ({
  apiClient: {
    post: jest.fn(),
    get: jest.fn(),
    delete: jest.fn(),
    client: {
      post: jest.fn(),
    },
    createWebSocket: jest.fn(),
  },
}));

const mockApiClient = apiClient as jest.Mocked<typeof apiClient>;

describe('searchService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('uses /search/hybrid with hybrid mode by default', async () => {
    mockApiClient.post.mockResolvedValueOnce({
      search_id: 'search-1',
      query: 'prompt injection',
      results: [
        {
          document_id: 'doc-1',
          title: 'Defense Strategies',
          content_preview: 'Defense in depth for prompt injection.',
          relevance_score: 0.91,
          document_type: 'PDF',
        },
      ],
      search_time_ms: 25,
      total_results: 1,
    });

    const response = await searchService.search({ query: 'prompt injection' });

    expect(response.success).toBe(true);
    expect(response.data.query).toBe('prompt injection');
    expect(mockApiClient.post).toHaveBeenCalledTimes(1);
    expect(mockApiClient.post).toHaveBeenCalledWith(
      '/search/hybrid',
      expect.objectContaining({
        query: 'prompt injection',
        search_type: 'hybrid',
      })
    );
  });

  it('falls back to /search/ when /search/hybrid returns 404', async () => {
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
            title: 'Defense Strategies',
            content_preview: 'Defense in depth for prompt injection.',
            relevance_score: 0.91,
            document_type: 'PDF',
          },
        ],
        search_time_ms: 25,
        total_results: 1,
      });

    const response = await searchService.search({ query: 'prompt injection' });

    expect(response.success).toBe(true);
    expect(response.data.query).toBe('prompt injection');
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
  });

  it('sends addToHistory payload as query params', async () => {
    mockApiClient.post.mockResolvedValueOnce({
      success: true,
      data: undefined,
    });

    await searchService.addToHistory('rag systems', 'search-2');

    expect(mockApiClient.post).toHaveBeenCalledWith('/search/history', null, {
      params: {
        query: 'rag systems',
        result_id: 'search-2',
      },
    });
  });

  it('builds a non-empty assistant answer text from search results', async () => {
    mockApiClient.post.mockResolvedValueOnce({
      search_id: 'search-3',
      query: 'hello',
      results: [
        {
          document_id: 'doc-1',
          title: 'Welcome Guide',
          content_preview: 'This is the first matching snippet.',
          relevance_score: 0.89,
          document_type: 'PDF',
        },
      ],
      search_time_ms: 12,
      total_results: 1,
    });

    const response = await searchService.search({ query: 'hello' });

    expect(response.success).toBe(true);
    expect(response.data.answer.text).not.toEqual('');
    expect(response.data.answer.text).toContain('Welcome Guide');
  });
});
