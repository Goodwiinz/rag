/**
 * Unit tests for ChatInput streaming/loading behavior
 *
 * Tests the stop button, input disabling, and onStop callback
 * when the component is in loading mode (isLoading=true).
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';

// Mock framer-motion to avoid animation issues in tests
vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
    span: ({ children, ...props }: any) => <span {...props}>{children}</span>,
    button: ({ children, ...props }: any) => (
      <button {...props}>{children}</button>
    ),
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
  useMotionValue: () => ({ set: vi.fn(), get: () => 0 }),
  useSpring: (v: any) => v,
  useTransform: () => ({ set: vi.fn(), get: () => 0 }),
}));

import { ChatInput } from '../ChatInput';

// Default props for all tests
const defaultProps = {
  value: '',
  onChange: vi.fn(),
  onSubmit: vi.fn(),
  onStop: vi.fn(),
  isLoading: false,
  enableRAG: true,
  onRAGToggle: vi.fn(),
};

describe('ChatInput streaming behavior', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('when isLoading is true', () => {
    it('shows a Stop button', () => {
      render(<ChatInput {...defaultProps} isLoading={true} />);

      const stopButton = screen.getByText('Stop');
      expect(stopButton).toBeInTheDocument();
    });

    it('calls onStop when Stop button is clicked', () => {
      const onStop = vi.fn();

      render(<ChatInput {...defaultProps} onStop={onStop} isLoading={true} />);

      const stopButton = screen.getByText('Stop');
      fireEvent.click(stopButton);

      expect(onStop).toHaveBeenCalledTimes(1);
    });

    it('does not show the Send button', () => {
      render(<ChatInput {...defaultProps} isLoading={true} />);

      const sendButton = screen.queryByText('Send');
      expect(sendButton).not.toBeInTheDocument();
    });
  });

  describe('when isLoading is false', () => {
    it('shows the Send button (not Stop)', () => {
      render(<ChatInput {...defaultProps} isLoading={false} value="Hello" />);

      const sendButton = screen.getByText('Send');
      expect(sendButton).toBeInTheDocument();

      const stopButton = screen.queryByText('Stop');
      expect(stopButton).not.toBeInTheDocument();
    });

    it('does not disable the textarea', () => {
      render(<ChatInput {...defaultProps} isLoading={false} />);

      const textarea = screen.getByRole('textbox');
      expect(textarea).not.toBeDisabled();
    });
  });

  describe('shows NOUS label', () => {
    it('displays the agent label in the input bar', () => {
      render(<ChatInput {...defaultProps} />);

      expect(screen.getByText('NOUS')).toBeInTheDocument();
    });
  });
});
