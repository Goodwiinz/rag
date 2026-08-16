'use client';

/**
 * Shared visual primitives from the assistant-ui Elements design language
 * (https://www.assistant-ui.com/elements), trimmed to what we actually use.
 *
 * Deliberately not installed via `shadcn add "@assistant-ui/elements-surfaces"`:
 * the upstream file pulls the `tw-shimmer` plugin and a `collapsePanel` helper
 * written for Base UI's collapsible (`data-[ending-style]`,
 * `h-(--collapsible-panel-height)`), both of which are inert here — our
 * collapsible is Radix and the shimmer is plain CSS in globals.css.
 */

import type { ComponentProps } from 'react';
import { useLayoutEffect, useRef, useState } from 'react';
import { cn } from '@/lib/utils';

/** Recessed surface for request/result panels. */
export const field = 'bg-foreground/[0.04] dark:bg-foreground/[0.06]';

/**
 * Raised surface for cards that sit on a recessed background — retrieval
 * passages, source cards. Upstream reaches for a layered drop shadow; the
 * NOUS surfaces are separated by a hairline instead, per DESIGN.md.
 */
export const paper = 'bg-(--nous-bg-1) border border-(--nous-border-1)';

/** Small-caps monospace used for field labels and inline chips. */
export const mono = 'font-mono text-[11px] tracking-tight';

/**
 * Upstream emits `.shimmer`, which in our globals.css is the grey
 * skeleton-loader gradient. `.tool-shimmer` is the text-clipped one.
 */
export function ShimmerLabel({
  active = true,
  className,
  ...props
}: ComponentProps<'span'> & { active?: boolean }) {
  return (
    <span
      className={cn(active && 'tool-shimmer motion-reduce:animate-none', className)}
      {...props}
    />
  );
}

const labelSwap =
  'col-start-1 row-start-1 flex w-max items-center gap-1.5 leading-none transition-[opacity,filter] duration-300 ease-[cubic-bezier(0.23,1,0.32,1)] motion-reduce:transition-none';
const labelSwapIn = 'opacity-100 blur-none';
const labelSwapOut = 'pointer-events-none select-none opacity-0 blur-[2px]';

/**
 * Cross-fades between two labels while animating the box to the active label's
 * width, so a status change doesn't jump the surrounding layout.
 */
export function SwapLabel({
  active,
  children,
  className,
}: {
  active: 0 | 1;
  children: [React.ReactNode, React.ReactNode];
  className?: string;
}) {
  const layers = [useRef<HTMLSpanElement>(null), useRef<HTMLSpanElement>(null)];
  const [width, setWidth] = useState<number | null>(null);

  useLayoutEffect(() => {
    const target = layers[active]?.current;
    if (!target) return undefined;
    const measure = () => setWidth(Math.ceil(target.getBoundingClientRect().width));
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(target);
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- refs are stable
  }, [active]);

  return (
    <span
      style={width === null ? undefined : { width }}
      className={cn(
        'grid overflow-x-clip transition-[width] duration-300 ease-[cubic-bezier(0.23,1,0.32,1)] motion-reduce:transition-none',
        className
      )}
    >
      {children.map((layer, index) => (
        <span
          key={index}
          ref={layers[index]}
          aria-hidden={active !== index}
          className={cn(labelSwap, active === index ? labelSwapIn : labelSwapOut)}
        >
          {layer}
        </span>
      ))}
    </span>
  );
}
