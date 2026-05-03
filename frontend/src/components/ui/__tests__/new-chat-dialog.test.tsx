import React from 'react';
import { render, screen, cleanup } from '@testing-library/react';
import { vi, describe, it, expect, afterEach } from 'vitest';

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

import { NewChatDialog, type Assistant } from '../new-chat-dialog';

const fourCapAssistant: Assistant = {
  id: 'a1',
  name: 'Multi Cap',
  description: 'An assistant with four capabilities',
  avatar: '',
  category: 'general',
  capabilities: ['Alpha', 'Beta', 'Gamma', 'Delta'],
  color: 'from-blue-500 to-cyan-500',
};

afterEach(() => {
  cleanup();
});

describe('NewChatDialog', () => {
  it('renders only the first three capabilities and an overflow indicator', () => {
    render(
      <NewChatDialog
        open={true}
        onOpenChange={vi.fn()}
        assistants={[fourCapAssistant]}
        onSelectAssistant={vi.fn()}
      />
    );

    expect(screen.getByText('Alpha')).toBeInTheDocument();
    expect(screen.getByText('Beta')).toBeInTheDocument();
    expect(screen.getByText('Gamma')).toBeInTheDocument();
    expect(screen.queryByText('Delta')).not.toBeInTheDocument();
    expect(screen.getByText('+1')).toBeInTheDocument();
  });
});
