import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import ArxivManagement from '@/components/arxiv/ArxivManagement';
import { apiClient } from '@/services/apiClient';

jest.mock('@/services/apiClient', () => ({
  apiClient: {
    get: jest.fn(),
    postWithLongTimeout: jest.fn(),
  },
}));

jest.mock('framer-motion', () => {
  const MotionDiv = ({ children, ...props }: any) => {
    const { initial, animate, exit, transition, layoutId, ...domProps } = props;
    void initial;
    void animate;
    void exit;
    void transition;
    void layoutId;
    return <div {...domProps}>{children}</div>;
  };

  const MotionSection = ({ children, ...props }: any) => {
    const { initial, animate, exit, transition, layoutId, ...domProps } = props;
    void initial;
    void animate;
    void exit;
    void transition;
    void layoutId;
    return <section {...domProps}>{children}</section>;
  };

  return {
    motion: {
      div: MotionDiv,
      section: MotionSection,
    },
    AnimatePresence: ({ children }: any) => <>{children}</>,
  };
});

const mockApiClient = apiClient as jest.Mocked<typeof apiClient>;

const statsResponse = {
  status: 'success',
  timestamp: '2026-01-01T00:00:00Z',
  statistics: {
    total_papers_tracked: 149,
    active_papers: 96,
    deleted_papers: 53,
    categories_tracked: 38,
    top_categories: [
      ['cs.AI', 44],
      ['cs.LG', 41],
    ],
    recent_changes_week: {},
    state_file_path: 'data/arxiv_change_state.json',
  },
};

describe('ArxivManagement', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockApiClient.get.mockResolvedValue(statsResponse as never);
  });

  it('searches, selects, and queues ingestion from the ingest tab', async () => {
    const searchResult = [
      {
        id: '1706.03762',
        title: 'Attention Is All You Need',
        authors: ['Ashish Vaswani'],
        abstract: 'Transformer architecture paper.',
        published: '2017-06-12T00:00:00Z',
        updated: '2017-06-12T00:00:00Z',
        categories: ['cs.CL', 'cs.LG'],
      },
    ];

    mockApiClient.postWithLongTimeout.mockImplementation(
      async (url: string) => {
        if (url === '/arxiv/search') {
          return searchResult as never;
        }

        if (url === '/arxiv/ingest') {
          return {
            message: 'ArXiv paper ingestion started',
            paper_count: 1,
            status: 'processing',
          } as never;
        }

        throw new Error(`Unexpected endpoint: ${url}`);
      }
    );

    render(<ArxivManagement />);

    fireEvent.click(screen.getByRole('tab', { name: 'Ingest Papers' }));

    fireEvent.change(screen.getByLabelText('Search Query'), {
      target: { value: 'transformer' },
    });

    fireEvent.click(screen.getByRole('button', { name: 'Search Papers' }));

    await waitFor(() => {
      expect(mockApiClient.postWithLongTimeout).toHaveBeenCalledWith(
        '/arxiv/search',
        expect.objectContaining({
          query: 'transformer',
          max_results: 50,
        })
      );
    });

    const resultTitle = await screen.findByText('Attention Is All You Need');
    fireEvent.click(resultTitle);

    const queueButton = screen.getByRole('button', { name: 'Queue Ingestion' });
    expect(queueButton).toBeEnabled();

    fireEvent.click(queueButton);

    await waitFor(() => {
      expect(mockApiClient.postWithLongTimeout).toHaveBeenCalledWith(
        '/arxiv/ingest',
        expect.objectContaining({
          paper_ids: ['1706.03762'],
          download_pdfs: false,
          extract_content: true,
        })
      );
    });

    const successMessages = await screen.findAllByText(
      'COMPLETED: 1 papers queued for background ingestion.'
    );
    expect(successMessages.length).toBeGreaterThan(0);
  });

  it('extracts features from paper IDs in the extract tab', async () => {
    mockApiClient.postWithLongTimeout.mockImplementation(
      async (url: string) => {
        if (url === '/arxiv/extraction/extract-features') {
          return {
            status: 'success',
            message: 'Extraction complete',
            processed_count: 2,
            results: [
              {
                paper_id: '1706.03762',
                title: 'Attention Is All You Need',
                extraction_status: 'completed',
                features: {
                  topics: ['transformers', 'sequence modeling'],
                  keyphrases: ['self-attention', 'encoder-decoder'],
                },
              },
              {
                paper_id: '1810.04805',
                title: 'BERT: Pre-training of Deep Bidirectional Transformers',
                extraction_status: 'completed',
                features: {
                  topics: ['language modeling'],
                  keyphrases: ['masked language model'],
                },
              },
            ],
          } as never;
        }

        throw new Error(`Unexpected endpoint: ${url}`);
      }
    );

    render(<ArxivManagement />);

    fireEvent.click(screen.getByRole('tab', { name: 'Extract Features' }));

    fireEvent.change(
      screen.getByLabelText('Paper IDs (one per line or comma-separated)'),
      {
        target: { value: '1706.03762,\n1810.04805' },
      }
    );

    fireEvent.click(screen.getByRole('button', { name: 'Extract Features' }));

    await waitFor(() => {
      expect(mockApiClient.postWithLongTimeout).toHaveBeenCalledWith(
        '/arxiv/extraction/extract-features',
        expect.objectContaining({
          paper_ids: ['1706.03762', '1810.04805'],
          extract_entities: true,
          extract_topics: true,
          extract_keyphrases: true,
          extract_citations: true,
          extract_summaries: true,
          update_knowledge_graph: true,
        })
      );
    });

    expect(
      await screen.findByText('Attention Is All You Need')
    ).toBeInTheDocument();
    expect(
      await screen.findByText(
        'BERT: Pre-training of Deep Bidirectional Transformers'
      )
    ).toBeInTheDocument();
  });
});
