import React from 'react';
import { render, screen, fireEvent, waitFor } from '../../__tests__/testUtils';
import ResultsPanel from '../ResultsPanel';

describe('ResultsPanel Accessibility', () => {
  const mockResult = {
    id: 'test-id',
    query: 'test query',
    answer: {
      text: 'Test answer',
      answer_type: 'factual',
      confidence: 0.95,
      sources: [
        {
          document_id: 'doc-1',
          document_title: 'Test Document',
          snippet: 'Test snippet',
          confidence: 0.9,
          file_type: 'pdf',
          page_number: 1
        }
      ],
      language_detected: 'en'
    },
    entities: [],
    relationships: [],
    metrics: {
      latency_ms: 100,
      retrieval_quality: 90,
      faithfulness_score: 90,
      contextual_relevancy: 90,
      hallucination_score: 10,
      answer_relevancy: 90,
      documents_retrieved: 1,
      entities_found: 0,
      relationships_found: 0
    },
    processing_time_ms: 100,
    created_at: new Date().toISOString(),
    user_id: 'user-1'
  };

  const defaultProps = {
    result: mockResult as any,
    onSourceClick: jest.fn(),
    onDocumentPreview: jest.fn(),
    onShare: jest.fn(),
    onExport: jest.fn(),
    onFeedback: jest.fn(),
  };

  it('has accessible labels for main action buttons', () => {
    render(<ResultsPanel {...defaultProps} />);

    // Check main action buttons
    const mainCopyButton = screen.getAllByRole('button', { name: 'Copy' })[0];
    expect(mainCopyButton).toBeInTheDocument();

    const shareButton = screen.getByRole('button', { name: 'Share' });
    expect(shareButton).toBeInTheDocument();

    const exportButton = screen.getByRole('button', { name: 'Export' });
    expect(exportButton).toBeInTheDocument();

    const rateButton = screen.getByRole('button', { name: 'Rate' });
    expect(rateButton).toBeInTheDocument();
  });

  it('has accessible labels for source card actions', () => {
    render(<ResultsPanel {...defaultProps} />);

    // Check source card buttons
    const previewButtons = screen.getAllByRole('button', { name: 'Preview document' });
    expect(previewButtons.length).toBeGreaterThan(0);

    const sourceCopyButtons = screen.getAllByRole('button', { name: 'Copy source snippet' });
    expect(sourceCopyButtons.length).toBeGreaterThan(0);
  });

  it('has accessible feedback dialog form', async () => {
    render(<ResultsPanel {...defaultProps} />);

    // Open dialog
    const rateButton = screen.getByRole('button', { name: 'Rate' });
    fireEvent.click(rateButton);

    // Check label association
    await waitFor(() => {
      expect(screen.getByText('Additional feedback (optional)')).toBeInTheDocument();
    });

    const label = screen.getByText('Additional feedback (optional)');
    expect(label).toHaveAttribute('for', 'feedback-comment');

    const textarea = screen.getByPlaceholderText('Tell us more...');
    expect(textarea).toHaveAttribute('id', 'feedback-comment');
  });
});
