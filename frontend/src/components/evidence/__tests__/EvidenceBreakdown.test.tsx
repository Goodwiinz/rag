/**
 * Unit tests for EvidenceBreakdown component
 * 
 * Tests the expandable panel that shows sources grouped by their stance
 * on a claim, with click-to-navigate functionality.
 */

import { Mock, beforeEach, describe, expect, it, vi } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { EvidenceBreakdown } from '../EvidenceBreakdown';
import { StanceBadge } from '../StanceBadge';
import { ConfidenceIndicator, ConfidenceBadge } from '../ConfidenceIndicator';
import * as useEvidenceMeterModule from '@/hooks/useEvidenceMeter';
import type { StanceClassification } from '@/types/evidence';

// Mock framer-motion
vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
    span: ({ children, ...props }: any) => <span {...props}>{children}</span>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

// Mock the hook
vi.mock('@/hooks/useEvidenceMeter', () => ({
  useEvidenceBreakdown: vi.fn(),
}));

// Test query client
const createTestQueryClient = () => new QueryClient({
  defaultOptions: {
    queries: { retry: false, gcTime: 0 },
  },
});

const TestWrapper = ({ children }: { children: React.ReactNode }) => {
  const queryClient = createTestQueryClient();
  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
};

// Sample test data
const mockSources: StanceClassification[] = [
  {
    source_id: 'src-1',
    title: 'Vitamin D Meta-Analysis Study',
    stance: 'supporting',
    confidence: 0.92,
    justification_excerpt: 'Our meta-analysis found a 40% reduction in ICU admission rates.',
    is_retracted: false,
  },
  {
    source_id: 'src-2',
    title: 'COVID Treatment Review',
    stance: 'supporting',
    confidence: 0.88,
    justification_excerpt: 'Evidence supports vitamin D supplementation.',
    is_retracted: false,
  },
  {
    source_id: 'src-3',
    title: 'Contrary Findings Report',
    stance: 'opposing',
    confidence: 0.85,
    justification_excerpt: 'No significant correlation was found between vitamin D and outcomes.',
    is_retracted: false,
  },
  {
    source_id: 'src-4',
    title: 'Observational Study',
    stance: 'neutral',
    confidence: 0.78,
    justification_excerpt: 'Results were inconclusive and require further investigation.',
    is_retracted: false,
  },
  {
    source_id: 'src-5',
    title: 'Retracted Paper',
    stance: 'supporting',
    confidence: 0.90,
    justification_excerpt: 'This paper was later retracted.',
    is_retracted: true,
  },
];

describe('EvidenceBreakdown', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (useEvidenceMeterModule.useEvidenceBreakdown as Mock).mockReturnValue({
      data: null,
      isLoading: false,
      error: null,
    });
  });

  describe('Rendering with provided sources', () => {
    it('renders breakdown panel with sources', () => {
      render(
        <TestWrapper>
          <EvidenceBreakdown
            claimHash="abc123"
            claim="Vitamin D reduces COVID severity"
            sources={mockSources}
          />
        </TestWrapper>
      );

      expect(screen.getByTestId('evidence-breakdown')).toBeInTheDocument();
    });

    it('groups sources by stance', () => {
      render(
        <TestWrapper>
          <EvidenceBreakdown
            claimHash="abc123"
            claim="test claim"
            sources={mockSources}
          />
        </TestWrapper>
      );

      // Check section headers with counts
      expect(screen.getByText('Supporting Sources (3)')).toBeInTheDocument();
      expect(screen.getByText('Opposing Sources (1)')).toBeInTheDocument();
      expect(screen.getByText('Neutral Sources (1)')).toBeInTheDocument();
    });

    it('displays source titles', () => {
      render(
        <TestWrapper>
          <EvidenceBreakdown
            claimHash="abc123"
            claim="test"
            sources={mockSources}
          />
        </TestWrapper>
      );

      expect(screen.getByText('Vitamin D Meta-Analysis Study')).toBeInTheDocument();
      expect(screen.getByText('Contrary Findings Report')).toBeInTheDocument();
    });

    it('displays justification excerpts', () => {
      render(
        <TestWrapper>
          <EvidenceBreakdown
            claimHash="abc123"
            claim="test"
            sources={mockSources}
          />
        </TestWrapper>
      );

      expect(screen.getByText(/40% reduction in ICU admission/)).toBeInTheDocument();
    });

    it('shows retracted source warning', () => {
      render(
        <TestWrapper>
          <EvidenceBreakdown
            claimHash="abc123"
            claim="test"
            sources={mockSources}
          />
        </TestWrapper>
      );

      expect(screen.getByText('This source has been retracted')).toBeInTheDocument();
    });
  });

  describe('Loading state', () => {
    it('shows skeleton when loading from API', () => {
      (useEvidenceMeterModule.useEvidenceBreakdown as Mock).mockReturnValue({
        data: null,
        isLoading: true,
        error: null,
      });

      render(
        <TestWrapper>
          <EvidenceBreakdown
            claimHash="abc123"
            claim="test"
            sources={[]} // Empty to trigger API fetch
          />
        </TestWrapper>
      );

      expect(screen.getByTestId('breakdown-skeleton')).toBeInTheDocument();
    });
  });

  describe('Error state', () => {
    it('shows error message when API fails', () => {
      (useEvidenceMeterModule.useEvidenceBreakdown as Mock).mockReturnValue({
        data: null,
        isLoading: false,
        error: new Error('API error'),
      });

      render(
        <TestWrapper>
          <EvidenceBreakdown
            claimHash="abc123"
            claim="test"
            sources={[]}
          />
        </TestWrapper>
      );

      expect(screen.getByTestId('breakdown-error')).toBeInTheDocument();
    });
  });

  describe('Empty state', () => {
    it('shows empty message when no sources', () => {
      (useEvidenceMeterModule.useEvidenceBreakdown as Mock).mockReturnValue({
        data: { sources: [] },
        isLoading: false,
        error: null,
      });

      render(
        <TestWrapper>
          <EvidenceBreakdown
            claimHash="abc123"
            claim="test"
            sources={[]}
          />
        </TestWrapper>
      );

      expect(screen.getByTestId('breakdown-empty')).toBeInTheDocument();
    });
  });

  describe('Click to navigate', () => {
    it('calls onSourceClick when source is clicked', () => {
      const handleClick = vi.fn();

      render(
        <TestWrapper>
          <EvidenceBreakdown
            claimHash="abc123"
            claim="test"
            sources={mockSources}
            onSourceClick={handleClick}
          />
        </TestWrapper>
      );

      const sourceItem = screen.getByTestId('source-item-src-1');
      fireEvent.click(sourceItem);

      expect(handleClick).toHaveBeenCalledWith('src-1');
    });

    it('handles keyboard navigation', () => {
      const handleClick = vi.fn();

      render(
        <TestWrapper>
          <EvidenceBreakdown
            claimHash="abc123"
            claim="test"
            sources={mockSources}
            onSourceClick={handleClick}
          />
        </TestWrapper>
      );

      const sourceItem = screen.getByTestId('source-item-src-1');
      fireEvent.keyDown(sourceItem, { key: 'Enter' });

      expect(handleClick).toHaveBeenCalledWith('src-1');
    });

    it('has correct role and aria-label when clickable', () => {
      const handleClick = vi.fn();

      render(
        <TestWrapper>
          <EvidenceBreakdown
            claimHash="abc123"
            claim="test"
            sources={mockSources}
            onSourceClick={handleClick}
          />
        </TestWrapper>
      );

      const sourceItem = screen.getByTestId('source-item-src-1');
      expect(sourceItem).toHaveAttribute('role', 'button');
      expect(sourceItem).toHaveAttribute('aria-label');
    });
  });

  describe('Collapsible sections', () => {
    it('supporting and opposing sections are open by default', () => {
      render(
        <TestWrapper>
          <EvidenceBreakdown
            claimHash="abc123"
            claim="test"
            sources={mockSources}
          />
        </TestWrapper>
      );

      // Supporting sources should be visible
      expect(screen.getByText('Vitamin D Meta-Analysis Study')).toBeInTheDocument();
      // Opposing sources should be visible
      expect(screen.getByText('Contrary Findings Report')).toBeInTheDocument();
    });

    it('toggles section on trigger click', () => {
      render(
        <TestWrapper>
          <EvidenceBreakdown
            claimHash="abc123"
            claim="test"
            sources={mockSources}
          />
        </TestWrapper>
      );

      // Find supporting section trigger
      const supportingTrigger = screen.getByText('Supporting Sources (3)').closest('button');
      expect(supportingTrigger).toHaveAttribute('aria-expanded', 'true');
      
      // Click to collapse
      if (supportingTrigger) {
        fireEvent.click(supportingTrigger);
        expect(supportingTrigger).toHaveAttribute('aria-expanded', 'false');
      }
    });
  });

  describe('Accessibility', () => {
    it('has region role with aria-label', () => {
      render(
        <TestWrapper>
          <EvidenceBreakdown
            claimHash="abc123"
            claim="Vitamin D reduces COVID severity"
            sources={mockSources}
          />
        </TestWrapper>
      );

      const breakdown = screen.getByTestId('evidence-breakdown');
      expect(breakdown).toHaveAttribute('role', 'region');
      expect(breakdown).toHaveAttribute('aria-label', expect.stringContaining('Evidence breakdown'));
    });
  });
});

describe('StanceBadge', () => {
  it('renders supporting badge with correct styling', () => {
    render(<StanceBadge stance="supporting" />);
    
    const badge = screen.getByTestId('stance-badge-supporting');
    expect(badge).toHaveTextContent('Supporting');
    expect(badge).toHaveTextContent('✓');
  });

  it('renders opposing badge with correct styling', () => {
    render(<StanceBadge stance="opposing" />);
    
    const badge = screen.getByTestId('stance-badge-opposing');
    expect(badge).toHaveTextContent('Opposing');
    expect(badge).toHaveTextContent('✗');
  });

  it('renders neutral badge with correct styling', () => {
    render(<StanceBadge stance="neutral" />);
    
    const badge = screen.getByTestId('stance-badge-neutral');
    expect(badge).toHaveTextContent('Neutral');
    expect(badge).toHaveTextContent('–');
  });

  it('shows confidence when below 85%', () => {
    render(<StanceBadge stance="supporting" confidence={0.72} showConfidence />);
    
    expect(screen.getByText('(72%)')).toBeInTheDocument();
  });

  it('does not show confidence when above 85%', () => {
    render(<StanceBadge stance="supporting" confidence={0.92} showConfidence />);
    
    expect(screen.queryByText('(92%)')).not.toBeInTheDocument();
  });

  it('has accessible aria-label', () => {
    render(<StanceBadge stance="supporting" confidence={0.72} showConfidence />);
    
    const badge = screen.getByTestId('stance-badge-supporting');
    expect(badge).toHaveAttribute('aria-label', expect.stringContaining('Supporting'));
    expect(badge).toHaveAttribute('aria-label', expect.stringContaining('72%'));
  });
});

describe('ConfidenceIndicator', () => {
  it('renders when confidence is below threshold', () => {
    render(<ConfidenceIndicator confidence={0.72} />);
    
    expect(screen.getByTestId('confidence-indicator')).toBeInTheDocument();
    expect(screen.getByText('72%')).toBeInTheDocument();
  });

  it('does not render when confidence is above threshold', () => {
    render(<ConfidenceIndicator confidence={0.92} />);
    
    expect(screen.queryByTestId('confidence-indicator')).not.toBeInTheDocument();
  });

  it('uses custom threshold', () => {
    render(<ConfidenceIndicator confidence={0.75} threshold={0.70} />);
    
    expect(screen.queryByTestId('confidence-indicator')).not.toBeInTheDocument();
  });

  it('has accessible aria-label', () => {
    render(<ConfidenceIndicator confidence={0.72} />);
    
    const indicator = screen.getByTestId('confidence-indicator');
    expect(indicator).toHaveAttribute('aria-label', 'Classification confidence: 72%');
  });
});

describe('ConfidenceBadge', () => {
  it('renders confidence percentage', () => {
    render(<ConfidenceBadge confidence={0.85} />);
    
    expect(screen.getByTestId('confidence-badge')).toBeInTheDocument();
    expect(screen.getByText('85%')).toBeInTheDocument();
  });

  it('has accessible aria-label', () => {
    render(<ConfidenceBadge confidence={0.85} />);
    
    const badge = screen.getByTestId('confidence-badge');
    expect(badge).toHaveAttribute('aria-label', 'Confidence: 85%');
  });
});
