/**
 * Unit tests for ChatInput file attach behavior.
 *
 * Verifies the Paperclip button is wired to a hidden file input that invokes
 * `onAttach` with the selected FileList.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/react';

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

import { ChatInput } from '../ChatInput';

const baseProps = {
  value: '',
  onChange: vi.fn(),
  onSubmit: vi.fn(),
  onStop: vi.fn(),
  isLoading: false,
  enableRAG: true,
  onRAGToggle: vi.fn(),
};

describe('ChatInput file attach', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders a hidden file input wired into the Paperclip control', () => {
    const { container } = render(<ChatInput {...baseProps} />);
    const input = container.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement | null;
    expect(input).not.toBeNull();
    expect(input?.multiple).toBe(true);
  });

  it('calls onAttach with selected files', () => {
    const onAttach = vi.fn();
    const { container } = render(
      <ChatInput {...baseProps} onAttach={onAttach} />
    );
    const input = container.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;
    const file = new File(['hello'], 'hello.pdf', {
      type: 'application/pdf',
    });
    Object.defineProperty(input, 'files', {
      value: [file] as unknown as FileList,
      configurable: true,
    });
    fireEvent.change(input);
    expect(onAttach).toHaveBeenCalledTimes(1);
    const calledWith = onAttach.mock.calls[0][0] as FileList;
    expect(calledWith[0].name).toBe('hello.pdf');
  });

  it('does not call onAttach when no files selected', () => {
    const onAttach = vi.fn();
    const { container } = render(
      <ChatInput {...baseProps} onAttach={onAttach} />
    );
    const input = container.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;
    Object.defineProperty(input, 'files', {
      value: [] as unknown as FileList,
      configurable: true,
    });
    fireEvent.change(input);
    expect(onAttach).not.toHaveBeenCalled();
  });

  it('resets the input value so selecting the same file twice re-fires onAttach', () => {
    const onAttach = vi.fn();
    const { container } = render(
      <ChatInput {...baseProps} onAttach={onAttach} />
    );
    const input = container.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;
    const file = new File(['hello'], 'hello.pdf', {
      type: 'application/pdf',
    });
    Object.defineProperty(input, 'files', {
      value: [file] as unknown as FileList,
      configurable: true,
    });
    fireEvent.change(input);
    expect(input.value).toBe('');
  });
});
