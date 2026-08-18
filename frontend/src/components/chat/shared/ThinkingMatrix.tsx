'use client';

import React from 'react';

/**
 * A 3×3 grid whose cells brighten on a diagonal sweep — the pre-first-token
 * figure, shown while a turn has nothing to display yet. Reads as work in
 * progress where a single pulsing dot reads as a stalled bullet.
 *
 * Shared deliberately: the chat surface has two pre-token pills — `ChatBubble`
 * for the legacy/search paths and `AuiMessage` for the primary dashboard
 * thread — and they had drifted to two copies of the same dot. One component
 * so the next change lands on both.
 *
 * The sweep is CSS keyframes with a per-cell delay (`.nous-matrix-cell`)
 * rather than a React-driven tick: this renders in the streaming hot path
 * under a memoized bubble, and a counter in state would re-render the subtree
 * several times a second to move nine squares.
 *
 * `aria-hidden` because the pill that hosts this is the live region and its
 * label already says what is happening.
 */
export function ThinkingMatrix(): React.ReactElement {
  return (
    <span
      aria-hidden
      className="grid shrink-0 gap-[2px]"
      style={{ gridTemplateColumns: 'repeat(3, 3px)' }}
    >
      {Array.from({ length: 9 }, (_, i) => (
        <span
          key={i}
          className="nous-matrix-cell h-[3px] w-[3px] rounded-[1px] bg-(--nous-sol) opacity-25 dark:bg-(--nous-helios)"
          // Diagonal sweep: cells on the same anti-diagonal light together.
          style={{ animationDelay: `${((i % 3) + Math.floor(i / 3)) * 0.12}s` }}
        />
      ))}
    </span>
  );
}

export default ThinkingMatrix;
