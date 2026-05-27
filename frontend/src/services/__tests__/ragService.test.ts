import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Mocked } from 'vitest';
import { APIErrorClass } from '@/types/api';
import { retrieveRAGContext } from '../ragService';
import { api } from '../api-client';

vi.mock('../api-client', () => ({
  api: {
    post: vi.fn(),
  },
}));

const mockApi = api as Mocked<typeof api>;

describe('retrieveRAGContext', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('calls authenticated hybrid search endpoint', async () => {
    mockApi.post.mockResolvedValue({
      query: 'What is RAG?',
      search_id: 's-1',
      total_results: 1,
      search_time_ms: 12,
      results: [
        {
          document_id: 'doc-1',
          title: 'RAG Intro',
          content_preview: 'RAG combines retrieval and generation.',
          relevance_score: 0.9,
          document_type: 'text',
          metadata: {},
        },
      ],
    });

    await retrieveRAGContext('What is RAG?');

    expect(mockApi.post).toHaveBeenCalledWith(
      '/search/hybrid',
      expect.objectContaining({
        query: 'What is RAG?',
        search_type: 'hybrid',
        include_snippets: true,
      })
    );
  });

  it('logs APIErrorClass status/details when retrieval fails', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    mockApi.post.mockRejectedValue(
      new APIErrorClass({
        message: 'Not Found',
        status_code: 404,
        type: 'http_error',
        details: { detail: 'Not Found' },
      })
    );

    const result = await retrieveRAGContext('missing');

    expect(result).toBeNull();
    expect(consoleErrorSpy).toHaveBeenCalledWith(
      '[RAG] Error details:',
      expect.objectContaining({
        message: 'Not Found',
        status: 404,
        data: { detail: 'Not Found' },
      })
    );
  });
});
