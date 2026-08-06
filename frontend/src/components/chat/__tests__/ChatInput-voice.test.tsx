/**
 * Unit tests for ChatInput voice input behavior.
 *
 * Verifies the Mic button toggles a Web Speech API SpeechRecognition session
 * and forwards the transcript through `onChange`. When the API is not
 * available on `window`, the button should be disabled.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Mock } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';

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

type MockRecognition = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: { results: [[{ transcript: string }]] }) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  start: Mock;
  stop: Mock;
};

function installSpeechRecognition(): { instances: MockRecognition[] } {
  const instances: MockRecognition[] = [];
  const Ctor = vi.fn(() => {
    const recognition: MockRecognition = {
      continuous: false,
      interimResults: false,
      lang: '',
      onresult: null,
      onend: null,
      onerror: null,
      start: vi.fn(),
      stop: vi.fn(),
    };
    instances.push(recognition);
    return recognition;
  });
  (window as unknown as Record<string, unknown>).SpeechRecognition =
    Ctor as unknown as object;
  return { instances };
}

function uninstallSpeechRecognition(): void {
  delete (window as unknown as Record<string, unknown>).SpeechRecognition;
  delete (window as unknown as Record<string, unknown>).webkitSpeechRecognition;
}

const baseProps = {
  value: '',
  onChange: vi.fn(),
  onSubmit: vi.fn(),
  onStop: vi.fn(),
  isLoading: false,
  enableRAG: true,
  onRAGToggle: vi.fn(),
};

describe('ChatInput voice input', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    uninstallSpeechRecognition();
  });
  afterEach(uninstallSpeechRecognition);

  it('disables the Mic button when SpeechRecognition is unavailable', () => {
    render(<ChatInput {...baseProps} />);
    const button = screen.getByLabelText('Voice input not supported');
    expect(button).toBeDisabled();
  });

  it('starts recognition when Mic is clicked and surfaces transcript via onChange', () => {
    const { instances } = installSpeechRecognition();
    const onChange = vi.fn();
    render(<ChatInput {...baseProps} onChange={onChange} />);
    fireEvent.click(screen.getByLabelText('Voice input'));
    expect(instances).toHaveLength(1);
    const r = instances[0];
    expect(r.start).toHaveBeenCalledTimes(1);
    expect(r.lang).toBe('en-US');
    r.onresult?.({ results: [[{ transcript: 'hello world' }]] });
    r.onend?.();
    expect(onChange).toHaveBeenCalledWith('hello world');
  });

  it('stops recognition when Mic is clicked while listening', () => {
    const { instances } = installSpeechRecognition();
    render(<ChatInput {...baseProps} />);
    fireEvent.click(screen.getByLabelText('Voice input'));
    fireEvent.click(screen.getByLabelText('Stop voice input'));
    expect(instances[0].stop).toHaveBeenCalledTimes(1);
  });
});
