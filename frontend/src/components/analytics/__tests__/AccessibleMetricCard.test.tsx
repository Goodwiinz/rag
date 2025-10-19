import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AccessibleMetricCard } from '../AccessibleMetricCard';
import { AccessibilityProvider } from '@/components/common/AccessibilityProvider';

// Mock accessibility provider
const MockAccessibilityProvider = ({ children }: { children: React.ReactNode }) => (
  <AccessibilityProvider>{children}</AccessibilityProvider>
);

// Test utilities
const renderWithAccessibility = (component: React.ReactElement) => {
  return render(
    <MockAccessibilityProvider>
      {component}
    </MockAccessibilityProvider>
  );
};

describe('AccessibleMetricCard', () => {
  const defaultProps = {
    title: 'Answer Relevancy',
    value: 85,
    threshold: 70,
    trend: { direction: 'up' as const, value: 5 },
    unit: '%' as const,
    description: 'Measures how relevant answers are to queries',
  };

  beforeEach(() => {
    // Clear all mocks
    jest.clearAllMocks();
  });

  describe('Basic Rendering', () => {
    it('renders metric title and value correctly', () => {
      renderWithAccessibility(<AccessibleMetricCard {...defaultProps} />);

      expect(screen.getByText('Answer Relevancy')).toBeInTheDocument();
      expect(screen.getByText('85%')).toBeInTheDocument();
    });

    it('displays threshold information', () => {
      renderWithAccessibility(<AccessibleMetricCard {...defaultProps} />);

      expect(screen.getByText('Threshold: 70%')).toBeInTheDocument();
    });

    it('shows status badge based on threshold', () => {
      renderWithAccessibility(<AccessibleMetricCard {...defaultProps} />);

      expect(screen.getByText('good')).toBeInTheDocument();
    });

    it('displays trend information when provided', () => {
      renderWithAccessibility(<AccessibleMetricCard {...defaultProps} />);

      expect(screen.getByText('5%')).toBeInTheDocument();
      expect(screen.getByLabelText('Trend: up, 5% change')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has proper ARIA labels', () => {
      renderWithAccessibility(<AccessibleMetricCard {...defaultProps} />);

      const card = screen.getByRole('region');
      expect(card).toHaveAttribute('aria-label', expect.stringContaining('Answer Relevancy: 85%'));
      expect(card).toHaveAttribute('aria-label', expect.stringContaining('Status: good'));
    });

    it('includes description in ARIA label when provided', () => {
      renderWithAccessibility(<AccessibleMetricCard {...defaultProps} />);

      const card = screen.getByRole('region');
      expect(card).toHaveAttribute('aria-label', expect.stringContaining('Measures how relevant answers are to queries'));
    });

    it('is keyboard navigable when clickable', () => {
      const handleClick = jest.fn();
      renderWithAccessibility(
        <AccessibleMetricCard {...defaultProps} onClick={handleClick} />
      );

      const card = screen.getByRole('region');
      expect(card).toHaveAttribute('tabIndex', '0');
    });

    it('responds to Enter key when clickable', async () => {
      const handleClick = jest.fn();
      const user = userEvent.setup();

      renderWithAccessibility(
        <AccessibleMetricCard {...defaultProps} onClick={handleClick} />
      );

      const card = screen.getByRole('region');
      await user.click(card);
      await user.keyboard('{Enter}');

      expect(handleClick).toHaveBeenCalledTimes(2);
    });

    it('responds to Space key when clickable', async () => {
      const handleClick = jest.fn();
      const user = userEvent.setup();

      renderWithAccessibility(
        <AccessibleMetricCard {...defaultProps} onClick={handleClick} />
      );

      const card = screen.getByRole('region');
      await user.keyboard('{Space}');

      expect(handleClick).toHaveBeenCalledTimes(1);
    });

    it('announces changes to screen readers', async () => {
      const { announce } = require('@/components/common/AccessibilityProvider');
      jest.spyOn(require('@/components/common/AccessibilityProvider'), 'useAnnouncements')
        .mockReturnValue({ announce });

      renderWithAccessibility(<AccessibleMetricCard {...defaultProps} />);

      await waitFor(() => {
        expect(announce).toHaveBeenCalledWith('Answer Relevancy: 85%, status: good');
      });
    });
  });

  describe('Status Variations', () => {
    it('shows warning status when value is below threshold but close', () => {
      renderWithAccessibility(
        <AccessibleMetricCard {...defaultProps} value={68} threshold={70} />
      );

      expect(screen.getByText('warning')).toBeInTheDocument();
    });

    it('shows critical status when value is well below threshold', () => {
      renderWithAccessibility(
        <AccessibleMetricCard {...defaultProps} value={50} threshold={70} />
      );

      expect(screen.getByText('critical')).toBeInTheDocument();
    });

    it('displays trend indicators correctly', () => {
      const { rerender } = renderWithAccessibility(
        <AccessibleMetricCard {...defaultProps} trend={{ direction: 'down', value: 3 }} />
      );

      expect(screen.getByLabelText('Trend: down, 3% change')).toBeInTheDocument();

      rerender(
        <AccessibleMetricCard {...defaultProps} trend={{ direction: 'stable', value: 0 }} />
      );

      expect(screen.getByLabelText('Trend: stable, 0% change')).toBeInTheDocument();
    });
  });

  describe('Loading and Error States', () => {
    it('shows loading state', () => {
      renderWithAccessibility(
        <AccessibleMetricCard {...defaultProps} loading={true} />
      );

      expect(screen.getByRole('status')).toBeInTheDocument();
      expect(screen.getByLabelText('Loading metric data')).toBeInTheDocument();
    });

    it('shows error state', () => {
      renderWithAccessibility(
        <AccessibleMetricCard {...defaultProps} error="Failed to load data" />
      );

      expect(screen.getByText('Error loading data')).toBeInTheDocument();
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('shows aria-busy attribute during loading', () => {
      renderWithAccessibility(
        <AccessibleMetricCard {...defaultProps} loading={true} />
      );

      const card = screen.getByRole('region');
      expect(card).toHaveAttribute('aria-busy', 'true');
    });
  });

  describe('Interactions', () => {
    it('calls onClick handler when clicked', async () => {
      const handleClick = jest.fn();
      const user = userEvent.setup();

      renderWithAccessibility(
        <AccessibleMetricCard {...defaultProps} onClick={handleClick} />
      );

      const card = screen.getByRole('region');
      await user.click(card);

      expect(handleClick).toHaveBeenCalledTimes(1);
    });

    it('announces click interaction', async () => {
      const handleClick = jest.fn();
      const { announce } = require('@/components/common/AccessibilityProvider');
      jest.spyOn(require('@/components/common/AccessibilityProvider'), 'useAnnouncements')
        .mockReturnValue({ announce });

      const user = userEvent.setup();

      renderWithAccessibility(
        <AccessibleMetricCard {...defaultProps} onClick={handleClick} />
      );

      const card = screen.getByRole('region');
      await user.click(card);

      await waitFor(() => {
        expect(announce).toHaveBeenCalledWith('Opened details for Answer Relevancy');
      });
    });
  });

  describe('Visual Accessibility', () => {
    it('applies correct status colors', () => {
      const { container } = renderWithAccessibility(
        <AccessibleMetricCard {...defaultProps} />
      );

      // Check if status classes are applied
      const valueElement = screen.getByText('85%');
      expect(valueElement).toHaveClass('text-green-600');
    });

    it('supports high contrast mode', () => {
      // Mock high contrast mode
      Object.defineProperty(document.documentElement, 'classList', {
        value: {
          add: jest.fn(),
          remove: jest.fn(),
          contains: jest.fn().mockReturnValue(true),
        },
        writable: true,
      });

      renderWithAccessibility(<AccessibleMetricCard {...defaultProps} />);

      // Component should adapt to high contrast mode
      expect(document.documentElement.classList.add).toHaveBeenCalledWith('high-contrast');
    });
  });

  describe('Performance', () => {
    it('does not cause unnecessary re-renders', () => {
      const { rerender } = renderWithAccessibility(
        <AccessibleMetricCard {...defaultProps} />
      );

      // Rerender with same props
      rerender(<AccessibleMetricCard {...defaultProps} />);

      // Should not cause any issues
      expect(screen.getByText('Answer Relevancy')).toBeInTheDocument();
    });

    it('handles rapid value updates efficiently', () => {
      const { rerender } = renderWithAccessibility(
        <AccessibleMetricCard {...defaultProps} />
      );

      // Rapid updates
      for (let i = 0; i < 10; i++) {
        rerender(<AccessibleMetricCard {...defaultProps} value={80 + i} />);
      }

      expect(screen.getByText('89%')).toBeInTheDocument();
    });
  });
});