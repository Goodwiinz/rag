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
  useReducedMotion: () => false,
}));

// Isolate the composer from the project picker (Radix + stores) — the /projects
// row just needs to render its trigger for these tests.
vi.mock('@/components/context-rail/ProjectPickerPopover', () => ({
  ProjectPickerPopover: ({ children }: any) => <>{children}</>,
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

  describe('phase-aware status pill', () => {
    it('shows no status pill when idle (and no legacy agent badge)', () => {
      render(<ChatInput {...defaultProps} />);
      expect(screen.queryByText(/Nous is/)).not.toBeInTheDocument();
      expect(screen.queryByText('nous-agent')).not.toBeInTheDocument();
    });

    it('shows "reflecting" while loading before tokens arrive', () => {
      render(
        <ChatInput
          {...defaultProps}
          isLoading
          isStreaming
          streamingContent=""
        />
      );
      expect(screen.getByRole('status')).toHaveTextContent(
        'Nous is reflecting'
      );
    });

    it('shows "writing" once tokens stream', () => {
      render(
        <ChatInput
          {...defaultProps}
          isLoading
          isStreaming
          streamingContent="partial answer"
        />
      );
      expect(screen.getByRole('status')).toHaveTextContent('Nous is writing');
    });

    it('shows "reading sources" while RAG retrieval is in flight', () => {
      render(<ChatInput {...defaultProps} isLoading isRAGLoading />);
      expect(screen.getByRole('status')).toHaveTextContent(
        'Nous is reading sources'
      );
    });
  });

  describe('Ultra Thinking toggle', () => {
    it('renders the Ultra Thinking label and toggles RAG', () => {
      const onRAGToggle = vi.fn();
      render(
        <ChatInput
          {...defaultProps}
          enableRAG={false}
          onRAGToggle={onRAGToggle}
        />
      );
      const toggle = screen.getByText('Ultra Thinking');
      expect(toggle).toBeInTheDocument();
      fireEvent.click(toggle);
      expect(onRAGToggle).toHaveBeenCalledWith(true);
    });
  });

  describe('slash command menu', () => {
    it('opens a listbox of commands when the value is "/"', () => {
      render(<ChatInput {...defaultProps} value="/" />);
      expect(screen.getByRole('listbox')).toBeInTheDocument();
      expect(screen.getByText('/new')).toBeInTheDocument();
      expect(screen.getByText('/projects')).toBeInTheDocument();
    });

    it('does not show the menu for normal text', () => {
      render(<ChatInput {...defaultProps} value="hello" />);
      expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    });

    it('runs the highlighted command on Enter (and does not submit)', () => {
      const onCommand = vi.fn();
      const onSubmit = vi.fn();
      render(
        <ChatInput
          {...defaultProps}
          value="/new"
          onCommand={onCommand}
          onSubmit={onSubmit}
        />
      );
      fireEvent.keyDown(screen.getByRole('textbox'), { key: 'Enter' });
      expect(onCommand).toHaveBeenCalledWith('new');
      expect(onSubmit).not.toHaveBeenCalled();
    });

    it('runs a command when its row is clicked', () => {
      const onCommand = vi.fn();
      render(<ChatInput {...defaultProps} value="/" onCommand={onCommand} />);
      fireEvent.click(screen.getByText('/clear'));
      expect(onCommand).toHaveBeenCalledWith('clear');
    });
  });
});
