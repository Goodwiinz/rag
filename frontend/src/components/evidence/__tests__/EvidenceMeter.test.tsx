/**
 * Unit tests for EvidenceMeter component
 * 
 * Tests the visual evidence agreement meter that displays consensus
 * level across retrieved sources for research claims.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { 
  EvidenceMeter, 
  EvidenceMeterSkeleton, 
  EvidenceMeterEmpty 
} from '../EvidenceMeter';
import * as useEvidenceMeterModule from '@/hooks/useEvidenceMeter';
import type { EvidenceMeterData } from '@/types/evidence';

// Mock framer-motion to avoid animation issues in tests
jest.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
    span: ({ children, ...props }: any) => <span {...props}>{children}</span>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

// Mock the hook module
jest.mock('@/hooks/useEvidenceMeter', () => ({
  useEvidenceMeter: jest.fn(),
  useEvidenceBreakdown: jest.fn(),
  getConsensusText: jest.fn(),
  getConsensusColor: jest.fn(),
  getConsensusEmoji: jest.fn(),
}));

// Create test query client
const createTestQueryClient = () => new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      gcTime: 0,
    },
  },
});

// Test wrapper
const TestWrapper = ({ children }: { children: React.ReactNode }) => {
  const queryClient = createTestQueryClient();
  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
};

// Sample test data
const mockMeterData: EvidenceMeterData = {
  claim: 'Vitamin D reduces COVID severity',
  claim_hash: 'abc123',
  total_sources: 10,
  supporting: 7,
  opposing: 2,
  neutral: 1,
  not_addressed: 0,
  consensus_level: 'moderate_agreement',
  average_confidence: 0.87,
  retracted_sources: 0,
  cached: true,
  reproducibility_hash: 'test_hash',
};

const mockMixedData: EvidenceMeterData = {
  ...mockMeterData,
  supporting: 4,
  opposing: 4,
  neutral: 2,
  consensus_level: 'mixed',
};

const mockLowConfidenceData: EvidenceMeterData = {
  ...mockMeterData,
  average_confidence: 0.72,
};

const mockRetractedData: EvidenceMeterData = {
  ...mockMeterData,
  retracted_sources: 2,
};

describe('EvidenceMeter', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    
    // Default mock implementations
    (useEvidenceMeterModule.getConsensusText as jest.Mock).mockReturnValue('7 of 10 sources agree');
    (useEvidenceMeterModule.getConsensusColor as jest.Mock).mockReturnValue('text-green-500');
    (useEvidenceMeterModule.getConsensusEmoji as jest.Mock).mockReturnValue('🟢');
    (useEvidenceMeterModule.useEvidenceBreakdown as jest.Mock).mockReturnValue({
      data: null,
      isLoading: false,
      error: null,
    });
  });

  describe('Loading State', () => {
    it('renders loading skeleton while fetching data', () => {
      (useEvidenceMeterModule.useEvidenceMeter as jest.Mock).mockReturnValue({
        data: null,
        isLoading: true,
        error: null,
      });

      render(
        <TestWrapper>
          <EvidenceMeter claim="test claim" />
        </TestWrapper>
      );

      expect(screen.getByTestId('evidence-meter-skeleton')).toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('renders error message when fetch fails', () => {
      (useEvidenceMeterModule.useEvidenceMeter as jest.Mock).mockReturnValue({
        data: null,
        isLoading: false,
        error: new Error('API error'),
      });

      render(
        <TestWrapper>
          <EvidenceMeter claim="test claim" />
        </TestWrapper>
      );

      expect(screen.getByTestId('evidence-meter-error')).toBeInTheDocument();
      expect(screen.getByText('Failed to load evidence meter')).toBeInTheDocument();
    });
  });

  describe('Empty State', () => {
    it('renders empty state when no sources found', () => {
      (useEvidenceMeterModule.useEvidenceMeter as jest.Mock).mockReturnValue({
        data: { ...mockMeterData, total_sources: 0 },
        isLoading: false,
        error: null,
      });

      render(
        <TestWrapper>
          <EvidenceMeter claim="test claim" />
        </TestWrapper>
      );

      expect(screen.getByTestId('evidence-meter-empty')).toBeInTheDocument();
    });
  });

  describe('Success State', () => {
    it('renders meter with consensus text', () => {
      (useEvidenceMeterModule.useEvidenceMeter as jest.Mock).mockReturnValue({
        data: mockMeterData,
        isLoading: false,
        error: null,
      });

      render(
        <TestWrapper>
          <EvidenceMeter claim="Vitamin D reduces COVID severity" />
        </TestWrapper>
      );

      expect(screen.getByTestId('evidence-meter')).toBeInTheDocument();
      expect(screen.getByText('7 of 10 sources agree')).toBeInTheDocument();
    });

    it('displays correct emoji for consensus level', () => {
      (useEvidenceMeterModule.useEvidenceMeter as jest.Mock).mockReturnValue({
        data: mockMeterData,
        isLoading: false,
        error: null,
      });

      render(
        <TestWrapper>
          <EvidenceMeter claim="test" />
        </TestWrapper>
      );

      expect(screen.getByText('🟢')).toBeInTheDocument();
    });

    it('shows legend with correct counts', () => {
      (useEvidenceMeterModule.useEvidenceMeter as jest.Mock).mockReturnValue({
        data: mockMeterData,
        isLoading: false,
        error: null,
      });

      render(
        <TestWrapper>
          <EvidenceMeter claim="test" />
        </TestWrapper>
      );

      expect(screen.getByText('Supporting (7)')).toBeInTheDocument();
      expect(screen.getByText('Neutral (1)')).toBeInTheDocument();
      expect(screen.getByText('Opposing (2)')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has proper ARIA attributes on meter', () => {
      (useEvidenceMeterModule.useEvidenceMeter as jest.Mock).mockReturnValue({
        data: mockMeterData,
        isLoading: false,
        error: null,
      });

      render(
        <TestWrapper>
          <EvidenceMeter claim="test" />
        </TestWrapper>
      );

      const meter = screen.getByRole('meter');
      expect(meter).toHaveAttribute('aria-label');
      expect(meter).toHaveAttribute('aria-valuenow');
      expect(meter).toHaveAttribute('aria-valuemin', '0');
      expect(meter).toHaveAttribute('aria-valuemax', '100');
    });

    it('expand button has aria-expanded attribute', () => {
      (useEvidenceMeterModule.useEvidenceMeter as jest.Mock).mockReturnValue({
        data: mockMeterData,
        isLoading: false,
        error: null,
      });

      render(
        <TestWrapper>
          <EvidenceMeter claim="test" />
        </TestWrapper>
      );

      const expandButton = screen.getByRole('button');
      expect(expandButton).toHaveAttribute('aria-expanded', 'false');
    });

    it('has screen reader text for expand/collapse', () => {
      (useEvidenceMeterModule.useEvidenceMeter as jest.Mock).mockReturnValue({
        data: mockMeterData,
        isLoading: false,
        error: null,
      });

      render(
        <TestWrapper>
          <EvidenceMeter claim="test" />
        </TestWrapper>
      );

      expect(screen.getByText('Expand breakdown')).toBeInTheDocument();
    });
  });

  describe('Confidence Warning', () => {
    it('shows confidence warning when below 85%', () => {
      (useEvidenceMeterModule.useEvidenceMeter as jest.Mock).mockReturnValue({
        data: mockLowConfidenceData,
        isLoading: false,
        error: null,
      });

      render(
        <TestWrapper>
          <EvidenceMeter claim="test" />
        </TestWrapper>
      );

      expect(screen.getByTestId('confidence-indicator')).toBeInTheDocument();
    });

    it('does not show confidence warning when above 85%', () => {
      (useEvidenceMeterModule.useEvidenceMeter as jest.Mock).mockReturnValue({
        data: mockMeterData,
        isLoading: false,
        error: null,
      });

      render(
        <TestWrapper>
          <EvidenceMeter claim="test" />
        </TestWrapper>
      );

      expect(screen.queryByTestId('confidence-indicator')).not.toBeInTheDocument();
    });
  });

  describe('Retracted Sources Warning', () => {
    it('shows warning when retracted sources found', () => {
      (useEvidenceMeterModule.useEvidenceMeter as jest.Mock).mockReturnValue({
        data: mockRetractedData,
        isLoading: false,
        error: null,
      });

      render(
        <TestWrapper>
          <EvidenceMeter claim="test" />
        </TestWrapper>
      );

      expect(screen.getByText(/2 retracted sources found/)).toBeInTheDocument();
    });
  });

  describe('Expand/Collapse Breakdown', () => {
    it('toggles breakdown panel on button click', () => {
      (useEvidenceMeterModule.useEvidenceMeter as jest.Mock).mockReturnValue({
        data: mockMeterData,
        isLoading: false,
        error: null,
      });

      render(
        <TestWrapper>
          <EvidenceMeter claim="test" />
        </TestWrapper>
      );

      const button = screen.getByRole('button');
      
      // Initially collapsed
      expect(button).toHaveAttribute('aria-expanded', 'false');
      
      // Click to expand
      fireEvent.click(button);
      expect(button).toHaveAttribute('aria-expanded', 'true');
      
      // Click to collapse
      fireEvent.click(button);
      expect(button).toHaveAttribute('aria-expanded', 'false');
    });
  });
});

describe('EvidenceMeterSkeleton', () => {
  it('renders skeleton elements', () => {
    render(<EvidenceMeterSkeleton />);
    expect(screen.getByTestId('evidence-meter-skeleton')).toBeInTheDocument();
  });

  it('accepts custom className', () => {
    render(<EvidenceMeterSkeleton className="custom-class" />);
    expect(screen.getByTestId('evidence-meter-skeleton')).toHaveClass('custom-class');
  });
});

describe('EvidenceMeterEmpty', () => {
  it('renders empty state message', () => {
    render(<EvidenceMeterEmpty />);
    expect(screen.getByTestId('evidence-meter-empty')).toBeInTheDocument();
    expect(screen.getByText('No sources found for this claim')).toBeInTheDocument();
  });

  it('accepts custom className', () => {
    render(<EvidenceMeterEmpty className="custom-class" />);
    expect(screen.getByTestId('evidence-meter-empty')).toHaveClass('custom-class');
  });
});

describe('getConsensusText helper', () => {
  const { getConsensusText } = jest.requireActual('@/hooks/useEvidenceMeter');

  it('returns correct text for strong agreement', () => {
    const data: EvidenceMeterData = {
      ...mockMeterData,
      consensus_level: 'strong_agreement',
    };
    expect(getConsensusText(data)).toContain('7 of 10 sources agree');
  });

  it('returns limited evidence text for <3 sources', () => {
    const data: EvidenceMeterData = {
      ...mockMeterData,
      supporting: 2,
      opposing: 0,
      neutral: 0,
      total_sources: 2,
    };
    expect(getConsensusText(data)).toContain('Limited evidence');
  });

  it('returns no sources found for empty data', () => {
    const data: EvidenceMeterData = {
      ...mockMeterData,
      total_sources: 0,
      supporting: 0,
      opposing: 0,
      neutral: 0,
    };
    expect(getConsensusText(data)).toBe('No sources found');
  });

  it('returns mixed evidence text for mixed consensus', () => {
    const data: EvidenceMeterData = {
      ...mockMixedData,
    };
    expect(getConsensusText(data)).toContain('Mixed evidence');
  });
});
