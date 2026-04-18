/**
 * Unit tests for BibliographyExport component
 *
 * Tests rendering, format selection, citation selection,
 * needs-review warnings, and export/download behavior.
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BibliographyExport } from '../BibliographyExport';
import { citationService } from '@/services/citationService';
import type { CitationResponse } from '@/types/research';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

jest.mock('@/services/citationService', () => ({
  citationService: {
    downloadBibliography: jest.fn().mockResolvedValue(undefined),
    exportBibliography: jest.fn().mockResolvedValue(''),
  },
}));

// Mock shadcn Select since it uses Radix portal
jest.mock('@/components/ui/select', () => ({
  Select: ({ children, value, onValueChange }: any) => (
    <div data-testid="select-root">{children}</div>
  ),
  SelectTrigger: ({ children }: any) => (
    <button data-testid="select-trigger">{children}</button>
  ),
  SelectValue: () => <span data-testid="select-value">BibTeX</span>,
  SelectContent: ({ children }: any) => (
    <div data-testid="select-content">{children}</div>
  ),
  SelectItem: ({ children, value }: any) => (
    <div data-testid={`select-item-${value}`}>{children}</div>
  ),
}));

const mockDownload = citationService.downloadBibliography as jest.Mock;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeCitation(
  overrides: Partial<CitationResponse> = {}
): CitationResponse {
  return {
    id: `cit-${Math.random().toString(36).slice(2, 8)}`,
    documentTitle: 'Test Paper',
    documentType: 'paper',
    authors: ['Alice Smith', 'Bob Jones'],
    year: 2024,
    venue: 'NeurIPS',
    score: 0.9,
    metadataSource: 'arxiv',
    needsReview: false,
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T00:00:00Z',
    ...overrides,
  } as CitationResponse;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('BibliographyExport', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders the Export Bibliography heading', () => {
      render(<BibliographyExport citations={[makeCitation()]} />);

      expect(screen.getByText('Export Bibliography')).toBeInTheDocument();
    });

    it('renders format selector options', () => {
      render(<BibliographyExport citations={[makeCitation()]} />);

      expect(screen.getByTestId('select-item-bibtex')).toBeInTheDocument();
      expect(screen.getByTestId('select-item-ieee')).toBeInTheDocument();
      expect(screen.getByTestId('select-item-apa')).toBeInTheDocument();
      expect(screen.getByTestId('select-item-mla')).toBeInTheDocument();
    });

    it('shows "No citations available" when list is empty', () => {
      render(<BibliographyExport citations={[]} />);

      expect(screen.getByText('No citations available')).toBeInTheDocument();
    });

    it('renders each citation with its title', () => {
      const citations = [
        makeCitation({ id: 'c1', documentTitle: 'Paper Alpha' }),
        makeCitation({ id: 'c2', documentTitle: 'Paper Beta' }),
      ];

      render(<BibliographyExport citations={citations} />);

      expect(screen.getByText('Paper Alpha')).toBeInTheDocument();
      expect(screen.getByText('Paper Beta')).toBeInTheDocument();
    });

    it('shows author and year info', () => {
      const citation = makeCitation({
        authors: ['Alice Smith'],
        year: 2023,
      });

      render(<BibliographyExport citations={[citation]} />);

      expect(screen.getByText(/Alice Smith/)).toBeInTheDocument();
      expect(screen.getByText(/2023/)).toBeInTheDocument();
    });
  });

  describe('Needs Review Warning', () => {
    it('shows warning when citations need review', () => {
      const citations = [
        makeCitation({ id: 'c1', needsReview: true }),
        makeCitation({ id: 'c2', needsReview: false }),
      ];

      render(<BibliographyExport citations={citations} />);

      expect(screen.getByText(/1 citation needs? review/i)).toBeInTheDocument();
    });

    it('shows correct count for multiple needing review', () => {
      const citations = [
        makeCitation({ id: 'c1', needsReview: true }),
        makeCitation({ id: 'c2', needsReview: true }),
        makeCitation({ id: 'c3', needsReview: false }),
      ];

      render(<BibliographyExport citations={citations} />);

      expect(screen.getByText(/2 citations need review/)).toBeInTheDocument();
    });

    it('hides warning when no citations need review', () => {
      const citations = [makeCitation({ needsReview: false })];

      render(<BibliographyExport citations={citations} />);

      expect(screen.queryByText(/need review/i)).not.toBeInTheDocument();
    });

    it('shows "Needs Review" badge on individual citations', () => {
      const citation = makeCitation({ needsReview: true });

      render(<BibliographyExport citations={[citation]} />);

      expect(screen.getByText('Needs Review')).toBeInTheDocument();
    });
  });

  describe('Citation Selection', () => {
    it('all citations selected by default', () => {
      const citations = [
        makeCitation({ id: 'c1' }),
        makeCitation({ id: 'c2' }),
      ];

      render(<BibliographyExport citations={citations} />);

      expect(screen.getByText(/2\/2/)).toBeInTheDocument();
    });

    it('shows Deselect All when all selected', () => {
      render(<BibliographyExport citations={[makeCitation()]} />);

      expect(screen.getByText('Deselect All')).toBeInTheDocument();
    });

    it('updates count text when displaying selections', () => {
      const citations = [
        makeCitation({ id: 'c1' }),
        makeCitation({ id: 'c2' }),
        makeCitation({ id: 'c3' }),
      ];

      render(<BibliographyExport citations={citations} />);

      // All 3 selected by default
      expect(screen.getByText('3 citations selected')).toBeInTheDocument();
    });
  });

  describe('Download Button', () => {
    it('shows Download button with format name', () => {
      render(<BibliographyExport citations={[makeCitation()]} />);

      expect(screen.getByText(/Download BIBTEX/i)).toBeInTheDocument();
    });

    it('download button is disabled when no citations selected', () => {
      render(<BibliographyExport citations={[]} />);

      const btn = screen.getByRole('button', { name: /download/i });
      expect(btn).toBeDisabled();
    });

    it('calls downloadBibliography on click', async () => {
      const citation = makeCitation({ id: 'cit-abc' });
      const onComplete = jest.fn();

      render(
        <BibliographyExport
          citations={[citation]}
          onExportComplete={onComplete}
        />
      );

      const btn = screen.getByRole('button', { name: /download/i });
      fireEvent.click(btn);

      await waitFor(() => {
        expect(mockDownload).toHaveBeenCalledWith(
          'bibtex',
          ['cit-abc'],
          undefined,
          'bibliography.bib'
        );
      });

      await waitFor(() => {
        expect(onComplete).toHaveBeenCalled();
      });
    });

    it('passes projectId when provided', async () => {
      const citation = makeCitation({ id: 'cit-xyz' });

      render(
        <BibliographyExport citations={[citation]} projectId="proj-123" />
      );

      fireEvent.click(screen.getByRole('button', { name: /download/i }));

      await waitFor(() => {
        expect(mockDownload).toHaveBeenCalledWith(
          'bibtex',
          ['cit-xyz'],
          'proj-123',
          'bibliography.bib'
        );
      });
    });

    it('handles export error gracefully', async () => {
      mockDownload.mockRejectedValueOnce(new Error('Network error'));
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      render(<BibliographyExport citations={[makeCitation()]} />);

      fireEvent.click(screen.getByRole('button', { name: /download/i }));

      await waitFor(() => {
        expect(consoleSpy).toHaveBeenCalledWith(
          'Bibliography export failed:',
          expect.any(Error)
        );
      });

      consoleSpy.mockRestore();
    });
  });
});
