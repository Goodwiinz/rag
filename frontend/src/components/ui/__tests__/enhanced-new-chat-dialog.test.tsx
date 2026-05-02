import React from 'react';
import { render, screen } from '@testing-library/react';
import { vi, describe, it, expect } from 'vitest';
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

vi.mock('framer-motion', () => ({
  motion: new Proxy(
    {},
    { get: (_target, tag: string) => makeMotionComponent(tag) }
  ),
  AnimatePresence: ({ children }: React.PropsWithChildren) => <>{children}</>,
  useAnimation: () => ({ start: vi.fn() }),
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
  it('auto-selects the first recently-used assistant only once on open (no spurious re-selection)', () => {
    // Bug: selectedAssistant in the useEffect dep array causes the effect to
    // re-fire every time selectedAssistant changes. With the fix (useRef guard +
    // selectedAssistant removed from deps) the effect should only run once per
    // open cycle. We verify that the auto-selection fires exactly once by
    // checking the card is selected after first render and stays selected on
    // rerender (not cleared and re-set).
    const { rerender } = render(<EnhancedNewChatDialog {...defaultProps} />);

    // The first assistant card should be auto-selected (aria-pressed="true").
    const selectButton = screen.getByRole('button', {
      name: /select test assistant/i,
    });
    expect(selectButton).toHaveAttribute('aria-pressed', 'true');

    // Rerender with same props — if selectedAssistant in deps caused a
    // spurious reset+reselect cycle, the card may transiently deselect.
    // After the fix it must remain stably selected.
    rerender(<EnhancedNewChatDialog {...defaultProps} />);

    expect(
      screen.getByRole('button', { name: /select test assistant/i })
    ).toHaveAttribute('aria-pressed', 'true');

    // The dialog renders without throwing (guards against "too many re-renders").
    expect(screen.getByTestId('dialog')).toBeInTheDocument();
  });

  it('search input resets to empty string (not null) when dialog closes and reopens', () => {
    // Bug: setSearchQuery(null) in the else-branch sets string state to null,
    // which is a type error and can cause React to emit a console warning about
    // a controlled input receiving a null value.
    const consoleError = vi
      .spyOn(console, 'error')
      .mockImplementation(() => {});

    const { rerender } = render(<EnhancedNewChatDialog {...defaultProps} />);

    // Verify the input is present and starts empty.
    const inputs = screen.getAllByPlaceholderText(
      /search by name, capability, or category/i
    );
    expect(inputs.length).toBeGreaterThan(0);
    expect(inputs[0]).toHaveValue('');

    // Close the dialog — buggy code runs setSearchQuery(null).
    rerender(<EnhancedNewChatDialog {...defaultProps} open={false} />);

    // Re-open.
    rerender(<EnhancedNewChatDialog {...defaultProps} open={true} />);

    // With the bug: React logs a warning about null on a controlled input.
    // With the fix: setSearchQuery("") — no warning, value is "".
    const nullControlledWarning = consoleError.mock.calls.some((args) =>
      String(args[0]).includes('null')
    );
    expect(nullControlledWarning).toBe(false);

    // The input value must be an empty string after re-open.
    const reopenedInputs = screen.getAllByPlaceholderText(
      /search by name, capability, or category/i
    );
    for (const input of reopenedInputs) {
      expect(input).toHaveValue('');
    }

    consoleError.mockRestore();
  });
});
