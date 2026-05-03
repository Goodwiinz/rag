import React from 'react';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import type { Assistant } from '@/types/chat';

// ---------------------------------------------------------------------------
// Mock framer-motion — strip framer-specific props so they don't leak into
// native DOM elements and cause React warnings or aria attribute pollution.
// ---------------------------------------------------------------------------
const MOTION_PROPS = new Set([
  'initial',
  'animate',
  'exit',
  'variants',
  'transition',
  'whileHover',
  'whileTap',
  'whileFocus',
  'whileDrag',
  'whileInView',
  'layout',
  'layoutId',
  'onHoverStart',
  'onHoverEnd',
  'onAnimationStart',
  'onAnimationComplete',
  'drag',
  'dragConstraints',
  'dragElastic',
  'dragMomentum',
  'viewport',
]);

function makeMotionComponent(tag: string) {
  // eslint-disable-next-line react/display-name
  return function MotionStub({
    children,
    ...props
  }: React.PropsWithChildren<Record<string, unknown>>) {
    const domProps = Object.fromEntries(
      Object.entries(props).filter(([k]) => !MOTION_PROPS.has(k))
    );
    return React.createElement(tag, domProps, children);
  };
}

// Stable mock object so `controls` keeps the same reference across renders
// (a fresh object would change identity each render and trigger spurious
// effect re-runs).
const mockControls = { start: vi.fn() };

vi.mock('framer-motion', () => ({
  motion: new Proxy(
    {},
    { get: (_target, tag: string) => makeMotionComponent(tag) }
  ),
  AnimatePresence: ({ children }: React.PropsWithChildren) => <>{children}</>,
  useAnimation: () => mockControls,
}));

// ---------------------------------------------------------------------------
// Mock Radix Dialog so it renders its children without a Portal into document
// body (which can cause findByRole issues inside jsdom).
// ---------------------------------------------------------------------------
vi.mock('@/components/ui/dialog', () => ({
  Dialog: ({ children, open }: { children: React.ReactNode; open: boolean }) =>
    open ? <div data-testid="dialog">{children}</div> : null,
  DialogContent: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  DialogHeader: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  DialogTitle: ({ children }: { children: React.ReactNode }) => (
    <h2>{children}</h2>
  ),
  DialogDescription: ({ children }: { children: React.ReactNode }) => (
    <p>{children}</p>
  ),
}));

// ---------------------------------------------------------------------------
// Keep the remaining shadcn UI components real (Button, Input, Avatar, Badge)
// so the rendered HTML is faithful enough to locate the search input.
// ---------------------------------------------------------------------------

import { EnhancedNewChatDialog } from '../enhanced-new-chat-dialog';

// ---------------------------------------------------------------------------
// Shared test fixtures
// ---------------------------------------------------------------------------
const mockAssistant: Assistant = {
  id: 'assistant-1',
  name: 'Test Assistant',
  description: 'A test assistant',
  category: 'general',
  capabilities: ['chat', 'search'],
  color: 'from-blue-400 to-blue-600',
  isActive: true,
};

const secondAssistant: Assistant = {
  id: 'assistant-2',
  name: 'Second Assistant',
  description: 'A second test assistant',
  category: 'general',
  capabilities: ['chat'],
  color: 'from-green-400 to-green-600',
  isActive: true,
};

const defaultProps = {
  open: true,
  onOpenChange: vi.fn(),
  assistants: [mockAssistant],
  onSelectAssistant: vi.fn(),
  recentlyUsed: [mockAssistant],
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe('EnhancedNewChatDialog', () => {
  beforeEach(() => {
    mockControls.start.mockClear();
  });

  afterEach(() => {
    cleanup();
  });

  it('does not snap user selection back to recentlyUsed[0] when recentlyUsed array reference changes', () => {
    // Bug: without the ref guard, the effect re-fires whenever the
    // recentlyUsed reference changes (e.g., parent rerenders with a new
    // array of identical content). The buggy effect would then call
    // setSelectedAssistant(recentlyUsed[0].id), overriding the user's
    // explicit choice of a different assistant.
    const recentlyUsed = [mockAssistant, secondAssistant];
    const props = {
      ...defaultProps,
      assistants: [mockAssistant, secondAssistant],
      recentlyUsed,
    };

    const { rerender } = render(<EnhancedNewChatDialog {...props} />);

    // Auto-selection should pick recentlyUsed[0] (assistant-1) initially.
    const firstButton = screen.getByRole('button', {
      name: /select test assistant/i,
    });
    expect(firstButton).toHaveAttribute('aria-pressed', 'true');

    // User picks the SECOND assistant explicitly.
    const secondButton = screen.getByRole('button', {
      name: /select second assistant/i,
    });
    fireEvent.click(secondButton);

    // Verify the second assistant is now selected.
    expect(
      screen.getByRole('button', { name: /select second assistant/i })
    ).toHaveAttribute('aria-pressed', 'true');
    expect(
      screen.getByRole('button', { name: /select test assistant/i })
    ).toHaveAttribute('aria-pressed', 'false');

    // Parent rerenders with a NEW array reference (same content).
    // With the buggy code (no ref guard, recentlyUsed in deps) the effect
    // re-fires and resets selection to recentlyUsed[0].
    // With the fix (ref guard) selection must stay on the user's choice.
    rerender(
      <EnhancedNewChatDialog {...props} recentlyUsed={[...recentlyUsed]} />
    );

    expect(
      screen.getByRole('button', { name: /select second assistant/i })
    ).toHaveAttribute('aria-pressed', 'true');
    expect(
      screen.getByRole('button', { name: /select test assistant/i })
    ).toHaveAttribute('aria-pressed', 'false');

    // Sanity: dialog still rendering.
    expect(screen.getByTestId('dialog')).toBeInTheDocument();
  });

  it('does not render any element with mangled Tailwind from/ or to/ class patterns', () => {
    // Bug: assistant.color (e.g. "from-blue-400 to-blue-600") was passed
    // through `.replace('to-', 'to/').replace('from-', 'from/')`, producing
    // "from/blue-400 to/blue-600" — invalid Tailwind that does nothing.
    // That branch fires only on UNSELECTED cards, so render with no
    // recentlyUsed (no auto-select) and a second assistant.
    render(
      <EnhancedNewChatDialog
        {...defaultProps}
        assistants={[mockAssistant, secondAssistant]}
        recentlyUsed={[]}
      />
    );

    const elements = document.querySelectorAll('[class]');
    const offenders: string[] = [];
    elements.forEach((el) => {
      const className = el.getAttribute('class') ?? '';
      if (/\bfrom\//.test(className) || /\bto\//.test(className)) {
        offenders.push(className);
      }
    });

    expect(offenders).toEqual([]);
  });

  it('search input resets to empty string when dialog closes and reopens', () => {
    // Bug: setSearchQuery(null) on string state is a type error. We assert
    // both behaviors that prove the reset is correct: (1) after type +
    // close + reopen, the input value reads as "" (string), and (2) React
    // does not warn about a controlled input switching to null.
    const consoleError = vi
      .spyOn(console, 'error')
      .mockImplementation(() => {});

    const { rerender } = render(<EnhancedNewChatDialog {...defaultProps} />);

    const initialInput = screen.getByPlaceholderText(
      /search by name, capability, or category/i
    );
    expect(initialInput).toHaveValue('');

    // Type something so searchQuery is non-empty before the reset effect.
    fireEvent.change(initialInput, { target: { value: 'hello' } });
    expect(
      screen.getByPlaceholderText(/search by name, capability, or category/i)
    ).toHaveValue('hello');

    // Close the dialog — the reset effect should run setSearchQuery("").
    rerender(<EnhancedNewChatDialog {...defaultProps} open={false} />);

    // Re-open the dialog.
    rerender(<EnhancedNewChatDialog {...defaultProps} open={true} />);

    // After reopen, the input must be empty.
    const reopenedInput = screen.getByPlaceholderText(
      /search by name, capability, or category/i
    );
    expect(reopenedInput).toHaveValue('');

    // With the bug (setSearchQuery(null)), React logs a warning that the
    // input switched from controlled to uncontrolled because `value` is
    // null. Asserting no such warning catches the bug directly.
    const nullControlledWarning = consoleError.mock.calls.some((args) => {
      const message = String(args[0] ?? '');
      return (
        message.includes('`value` prop on') &&
        message.includes('should not be null')
      );
    });
    expect(nullControlledWarning).toBe(false);

    consoleError.mockRestore();
  });
});
