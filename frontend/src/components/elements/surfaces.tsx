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
 * skeleton-loader gradient. `.tool-shimmer` is the text-clipped one, and it
 * only paints under `prefers-reduced-motion: no-preference` — it makes the
 * text itself transparent, so stopping just the animation would leave the
 * label invisible rather than still.
 */
export function ShimmerLabel({
  active = true,
  className,
  ...props
}: ComponentProps<'span'> & { active?: boolean }): React.ReactElement {
  return <span className={cn(active && 'tool-shimmer', className)} {...props} />;
}

/** Shows the active label at its native width. */
export function SwapLabel({
  active,
  children,
  className,
}: {
  active: 0 | 1;
  children: [React.ReactNode, React.ReactNode];
  className?: string;
}): React.ReactElement {
  return (
    <span className={cn('flex w-max items-center gap-1.5 leading-none', className)}>
      {children[active]}
    </span>
  );
}
