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
  const originalResearchIds = process.env.NEXT_PUBLIC_RESEARCH_DOCUMENT_IDS;

  beforeEach(() => {
    jest.clearAllMocks();
    process.env.NEXT_PUBLIC_RESEARCH_DOCUMENT_IDS = originalResearchIds;
  });

  afterAll(() => {
    process.env.NEXT_PUBLIC_RESEARCH_DOCUMENT_IDS = originalResearchIds;
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

  it('maps deterministic trace and quality fields from backend response', async () => {
    mockApiClient.post.mockResolvedValueOnce({
      search_id: 'search-3',
      query: 'deterministic quality check',
      results: [],
      search_time_ms: 18,
      total_results: 0,
      confidence: 0.64,
      coverage: 0.42,
      decision_trace_id: 'trace-xyz-123',
      deterministic_status: 'INSUFFICIENT_EVIDENCE',
      deterministic_message:
        'Insufficient cross-source evidence to produce a deterministic answer.',
      suggestions: ['Narrow query scope'],
    });

    const result = await searchService.search({ query: 'deterministic quality check' });

    expect(result.success).toBe(true);
    expect(result.data.answer.confidence).toBe(0.64);
    expect(result.data.answer.coverage).toBe(0.42);
    expect(result.data.answer.decisionTraceId).toBe('trace-xyz-123');
    expect(result.data.deterministicStatus).toBe('INSUFFICIENT_EVIDENCE');
    expect(result.data.deterministicMessage).toContain('Insufficient cross-source evidence');
    expect(result.data.refinementSuggestions).toEqual(['Narrow query scope']);
  });

  it('sends selected document_ids filter to backend for research mode queries', async () => {
    mockApiClient.post.mockResolvedValueOnce({
      search_id: 'search-4',
      query: 'filtered search',
      results: [],
      search_time_ms: 15,
      total_results: 0,
    });

    await searchService.search({
      query: 'filtered search',
      filters: { document_ids: ['doc-a', 'doc-b'] },
    });

    expect(mockApiClient.post).toHaveBeenCalledWith(
      '/search/hybrid',
      expect.objectContaining({
        filters: expect.objectContaining({
          document_ids: ['doc-a', 'doc-b'],
        }),
      })
    );
  });

  it('uses NEXT_PUBLIC_RESEARCH_DOCUMENT_IDS as default source filter when request filter is missing', async () => {
    process.env.NEXT_PUBLIC_RESEARCH_DOCUMENT_IDS = 'doc-x, doc-y';
    mockApiClient.post.mockResolvedValueOnce({
      search_id: 'search-5',
      query: 'env filtered search',
      results: [],
      search_time_ms: 14,
      total_results: 0,
    });

    await searchService.search({ query: 'env filtered search' });

    expect(mockApiClient.post).toHaveBeenCalledWith(
      '/search/hybrid',
      expect.objectContaining({
        filters: expect.objectContaining({
          document_ids: ['doc-x', 'doc-y'],
        }),
      })
    );
  });
});
