import React from 'react';
import { render, cleanup } from '@testing-library/react';
import { vi, describe, it, expect, afterEach } from 'vitest';
import { Home } from 'lucide-react';

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

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => '/',
  useSearchParams: () => new URLSearchParams(),
}));

import { EmptyState } from '../EmptyState';

afterEach(() => {
  cleanup();
});

describe('EmptyState', () => {
  it('renders an anchor for href actions and does NOT nest a button inside it', () => {
    const { container } = render(
      <EmptyState
        icon={Home}
        title="Nothing here"
        description="It's empty."
        action={{ label: 'Go home', href: '/' }}
      />
    );

    // There must be an anchor tag with the action label.
    const anchor = container.querySelector('a');
    expect(anchor).not.toBeNull();
    expect(anchor?.getAttribute('href')).toBe('/');
    expect(anchor?.textContent).toContain('Go home');

    // There must NOT be a <button> nested inside the <a> (invalid HTML).
    const nestedButton = anchor?.querySelector('button');
    expect(nestedButton).toBeNull();
  });

  it('renders a button for onClick actions (no anchor)', () => {
    const onClick = vi.fn();
    const { container } = render(
      <EmptyState
        icon={Home}
        title="Nothing here"
        description="It's empty."
        action={{ label: 'Click me', onClick }}
      />
    );

    expect(container.querySelector('a')).toBeNull();
    const button = container.querySelector('button');
    expect(button).not.toBeNull();
    expect(button?.textContent).toContain('Click me');
  });
});
