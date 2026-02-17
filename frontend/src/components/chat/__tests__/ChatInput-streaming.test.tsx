/**
 * Unit tests for ChatInput streaming behavior
 *
 * Tests the stop button, input disabling, and onStop callback
 * when the component is in streaming mode (isStreaming=true).
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';

// Mock framer-motion to avoid animation issues in tests
jest.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
    span: ({ children, ...props }: any) => <span {...props}>{children}</span>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

import { ChatInput } from '../ChatInput';

// Default props for all tests
const defaultProps = {
  value: '',
  onChange: jest.fn(),
  onSubmit: jest.fn(),
  onStop: jest.fn(),
  showToolbar: false,
  allowFileUpload: false,
  allowVoiceInput: false,
};

describe('ChatInput streaming behavior', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('when isStreaming is true', () => {
    it('shows a stop button with correct aria-label', () => {
      render(<ChatInput {...defaultProps} isStreaming={true} />);

      const stopButton = screen.getByRole('button', {
        name: 'Stop generating',
      });
      expect(stopButton).toBeInTheDocument();
    });

    it('calls onStop when stop button is clicked', () => {
      const onStop = jest.fn();

      render(
        <ChatInput {...defaultProps} onStop={onStop} isStreaming={true} />
      );

      const stopButton = screen.getByRole('button', {
        name: 'Stop generating',
      });
      fireEvent.click(stopButton);

      expect(onStop).toHaveBeenCalledTimes(1);
    });

    it('disables the textarea', () => {
      render(<ChatInput {...defaultProps} isStreaming={true} />);

      const textarea = screen.getByRole('textbox');
      expect(textarea).toBeDisabled();
    });

    it('does not show the send button', () => {
      render(<ChatInput {...defaultProps} isStreaming={true} />);

      // The send button should NOT be present; only the stop button
      const sendButton = screen.queryByRole('button', { name: 'Send message' });
      expect(sendButton).not.toBeInTheDocument();
    });
  });

  describe('when isStreaming is false', () => {
    it('shows the send button (not the stop button)', () => {
      render(<ChatInput {...defaultProps} isStreaming={false} value="Hello" />);

      const sendButton = screen.getByRole('button', { name: 'Send message' });
      expect(sendButton).toBeInTheDocument();

      const stopButton = screen.queryByRole('button', {
        name: 'Stop generating',
      });
      expect(stopButton).not.toBeInTheDocument();
    });

    it('does not disable the textarea', () => {
      render(<ChatInput {...defaultProps} isStreaming={false} />);

      const textarea = screen.getByRole('textbox');
      expect(textarea).not.toBeDisabled();
    });
  });

  describe('when isStreaming is not provided', () => {
    it('defaults to showing the send button', () => {
      render(<ChatInput {...defaultProps} value="Hello" />);

      const sendButton = screen.getByRole('button', { name: 'Send message' });
      expect(sendButton).toBeInTheDocument();
    });
  });
});
