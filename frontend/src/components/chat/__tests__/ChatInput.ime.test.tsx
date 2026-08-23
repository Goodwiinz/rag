/**
 * Unit tests for ChatInput IME composition safety (audit F1)
 *
 * Japanese/Chinese/Korean input: the Enter that confirms an IME candidate
 * must commit the text, not submit it — and with the slash menu open it
 * must not run the highlighted command either.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import React from 'react';
import { screen, fireEvent } from '@testing-library/react';

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

// Mock @assistant-ui/react primitives at the DOM boundary so ChatInput
// can render under test without a real runtime provider.
vi.mock('@assistant-ui/react', async () => {
  const React = await import('react');
  return {
    AssistantRuntimeProvider: ({ children }: any) => <>{children}</>,
    useExternalStoreRuntime: () => ({}),
    ComposerPrimitive: {
      Root: React.forwardRef<HTMLFormElement, any>(function ComposerRoot(
        { children, asChild: _asChild, ...props },
        ref
      ) {
        return (
          <form ref={ref} {...props}>
            {children}
          </form>
        );
      }),
      Input: ({ children, asChild: _asChild, ...props }: any) =>
        React.cloneElement(React.Children.only(children), props),
    },
  };
});

import { ChatInput } from '../ChatInput';
import { renderWithChatRuntime } from './renderWithChatRuntime';

const defaultProps = {
  value: '',
  onChange: vi.fn(),
  onSubmit: vi.fn(),
  onStop: vi.fn(),
  isLoading: false,
  enableRAG: true,
  onRAGToggle: vi.fn(),
};

describe('ChatInput IME composition safety', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('does not submit on Enter while an IME composition is active', () => {
    const onSubmit = vi.fn();
    renderWithChatRuntime(
      <ChatInput {...defaultProps} value="にほんご" onSubmit={onSubmit} />
    );

    const textarea = screen.getByRole('textbox') as HTMLTextAreaElement;

    // The confirm-Enter of the composition arrives flagged isComposing.
    fireEvent.keyDown(textarea, { key: 'Enter', isComposing: true });
    expect(onSubmit).not.toHaveBeenCalled();

    // Control: once composition has ended, Enter submits.
    fireEvent.keyDown(textarea, { key: 'Enter' });
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it('runs no slash command when composing-Enter lands with the menu open', () => {
    const onCommand = vi.fn();
    const onSubmit = vi.fn();
    const onChange = vi.fn();
    renderWithChatRuntime(
      <ChatInput
        {...defaultProps}
        value="/new"
        onChange={onChange}
        onCommand={onCommand}
        onSubmit={onSubmit}
      />
    );

    const textarea = screen.getByRole('textbox');
    expect(screen.getByRole('listbox')).toBeInTheDocument();

    fireEvent.keyDown(textarea, { key: 'Enter', isComposing: true });
    expect(onCommand).not.toHaveBeenCalled();
    expect(onSubmit).not.toHaveBeenCalled();

    // Control: the same key after composition commits runs the command.
    fireEvent.keyDown(textarea, { key: 'Enter' });
    expect(onCommand).toHaveBeenCalledWith('new');
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
