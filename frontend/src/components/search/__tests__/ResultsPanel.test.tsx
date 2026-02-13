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

    // Check main action buttons have aria-label equal to their title
    const copyButtons = screen.getAllByTitle('Copy');
    const mainCopyButton = copyButtons[0];
    expect(mainCopyButton).toHaveAttribute('aria-label', 'Copy');

    const shareButton = screen.getByTitle('Share');
    expect(shareButton).toHaveAttribute('aria-label', 'Share');

    const exportButton = screen.getByTitle('Export');
    expect(exportButton).toHaveAttribute('aria-label', 'Export');

    const rateButton = screen.getByTitle('Rate');
    expect(rateButton).toHaveAttribute('aria-label', 'Rate');
  });

  it('has accessible labels for source card actions', () => {
    render(<ResultsPanel {...defaultProps} />);

    // Check source card buttons
    const previewButtons = screen.getAllByTitle('Preview');
    expect(previewButtons[0]).toHaveAttribute('aria-label', 'Preview document');

    const copyButtons = screen.getAllByTitle('Copy');
    const sourceCopyButton = copyButtons[1];
    expect(sourceCopyButton).toHaveAttribute('aria-label', 'Copy source snippet');
  });

  it('has accessible feedback dialog form', async () => {
    render(<ResultsPanel {...defaultProps} />);

    // Open dialog
    const rateButton = screen.getByTitle('Rate');
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
