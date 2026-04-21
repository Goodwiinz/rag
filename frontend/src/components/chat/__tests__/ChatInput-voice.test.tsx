/**
 * Unit tests for ChatInput voice input behavior.
 *
 * Verifies the Mic button toggles a Web Speech API SpeechRecognition session
 * and forwards the transcript through `onChange`. When the API is not
 * available on `window`, the button should be disabled.
 */

import { fireEvent, render, screen } from '@testing-library/react';

// Mock framer-motion to avoid animation issues in tests
jest.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
    span: ({ children, ...props }: any) => <span {...props}>{children}</span>,
    button: ({ children, ...props }: any) => (
      <button {...props}>{children}</button>
    ),
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
  useMotionValue: () => ({ set: jest.fn(), get: () => 0 }),
  useSpring: (v: any) => v,
  useTransform: () => ({ set: jest.fn(), get: () => 0 }),
}));

import { ChatInput } from '../ChatInput';

type MockRecognition = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: { results: [[{ transcript: string }]] }) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  start: jest.Mock;
  stop: jest.Mock;
};

function installSpeechRecognition(): { instances: MockRecognition[] } {
  const instances: MockRecognition[] = [];
  const Ctor = jest.fn(() => {
    const recognition: MockRecognition = {
      continuous: false,
      interimResults: false,
      lang: '',
      onresult: null,
      onend: null,
      onerror: null,
      start: jest.fn(),
      stop: jest.fn(),
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
  onChange: jest.fn(),
  onSubmit: jest.fn(),
  onStop: jest.fn(),
  isLoading: false,
  enableRAG: true,
  onRAGToggle: jest.fn(),
};

describe('ChatInput voice input', () => {
  beforeEach(() => {
    jest.clearAllMocks();
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
    const onChange = jest.fn();
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
