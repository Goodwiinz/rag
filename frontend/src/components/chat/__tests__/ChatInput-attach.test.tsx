/**
 * Unit tests for ChatInput file attach behavior.
 *
 * Verifies the Paperclip button is wired to a hidden file input that invokes
 * `onAttach` with the selected FileList.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent } from '@testing-library/react';
import { renderWithChatRuntime } from './renderWithChatRuntime';

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

vi.mock('@assistant-ui/react', async () => {
  const React = await import('react');
  return {
    AssistantRuntimeProvider: ({ children }: any) => <>{children}</>,
    useExternalStoreRuntime: () => ({}),
    ComposerPrimitive: {
      Root: React.forwardRef<HTMLFormElement, any>(
        ({ children, asChild: _asChild, ...props }, ref) => (
          <form ref={ref} {...props}>
            {children}
          </form>
        )
      ),
      Input: ({ children, asChild: _asChild, ...props }: any) =>
        React.cloneElement(React.Children.only(children), props),
    },
  };
});

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
    const { container } = renderWithChatRuntime(<ChatInput {...baseProps} />);
    const input = container.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement | null;
    expect(input).not.toBeNull();
    expect(input?.multiple).toBe(true);
  });

  it('calls onAttach with selected files', () => {
    const onAttach = vi.fn();
    const { container } = renderWithChatRuntime(
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
    const { container } = renderWithChatRuntime(
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
    const { container } = renderWithChatRuntime(
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

  it('clears attachment chips and revokes blob URLs on send', () => {
    const revokeObjectURL = vi.fn();
    vi.stubGlobal('URL', {
      ...URL,
      createObjectURL: vi.fn(() => 'blob:mock'),
      revokeObjectURL,
    });

    // A non-empty value is required for the submit guard to fire onSubmit.
    const onSubmit = vi.fn();
    const { container } = renderWithChatRuntime(
      <ChatInput {...baseProps} value="hi" onSubmit={onSubmit} />
    );
    const imageInput = container.querySelector(
      'input[accept="image/*"]'
    ) as HTMLInputElement;
    const image = new File(['x'], 'pic.png', { type: 'image/png' });
    Object.defineProperty(imageInput, 'files', {
      value: [image] as unknown as FileList,
      configurable: true,
    });
    fireEvent.change(imageInput);

    // Chip is present before send.
    expect(container.querySelector('ul[aria-label="Attached files"]')).not.toBeNull();

    const form = container.querySelector('form') as HTMLFormElement;
    fireEvent.submit(form);

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:mock');
    // Chips list is gone (attachments emptied).
    expect(container.querySelector('ul[aria-label="Attached files"]')).toBeNull();

    vi.unstubAllGlobals();
  });
});
