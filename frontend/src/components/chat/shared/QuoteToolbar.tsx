'use client';

import React, { useEffect, useRef } from 'react';
import { Quote } from 'lucide-react';
import { createPortal } from 'react-dom';
import {
  useQuoteSelection,
  type QuoteSelection,
} from './useQuoteSelection';

/** Format a passage as a markdown quote so it reads as a citation, not prose.
 *
 * The leading newline is load-bearing. Append mode joins onto an existing
 * draft, and a `>` that lands mid-line is a literal angle bracket, not a
 * blockquote — so the payload opens its own line. ChatSurface honours a
 * payload that starts with a newline instead of inserting its usual space. */
function asQuoteBlock(text: string): string {
  return `\n${text
    .split('\n')
    .map((line) => `> ${line}`)
    .join('\n')}\n\n`;
}

function Toolbar({
  selection,
  onQuote,
}: {
  selection: QuoteSelection;
  onQuote: () => void;
}): React.ReactElement {
  const ref = useRef<HTMLButtonElement>(null);

  // Focus only a keyboard-driven selection, and only once it stops growing.
  // Taking focus on the first shift+arrow pointed every later arrow key at
  // the button instead of the passage, so a keyboard user could never select
  // more than the first increment. A mouse user is never focused at all —
  // they are about to click.
  const settled = selection.viaKeyboard ? selection.text : null;
  useEffect(() => {
    if (settled === null) return;
    const t = setTimeout(() => ref.current?.focus({ preventScroll: true }), 500);
    return () => clearTimeout(t);
  }, [settled]);

  return (
    <div
      role="toolbar"
      aria-label="Selected passage"
      className="fixed z-50 -translate-x-1/2 -translate-y-full pb-2"
      style={{ top: selection.top, left: selection.left }}
    >
      <button
        ref={ref}
        type="button"
        // Pressing the mouse collapses the selection, which unmounts this
        // toolbar before a click could land — so mousedown suppresses that,
        // and the click it does NOT cancel carries the action. Routing the
        // action through click (rather than mousedown) also keeps the
        // button's semantic activation working: Enter, Space, screen-reader
        // and voice-control activation all synthesise click and nothing else.
        onMouseDown={(e) => e.preventDefault()}
        onClick={onQuote}
        className="inline-flex items-center gap-1.5 rounded-full border border-(--nous-border-1) bg-(--nous-bg-2) px-3 py-1.5 font-nous-ui text-[12px] text-(--nous-fg-1) shadow-[0_4px_14px_rgba(var(--nous-erebus-rgb),0.12)] transition-colors hover:bg-(--nous-bg-3) focus:outline-hidden focus-visible:ring-2 focus-visible:ring-(--nous-sol)/40"
      >
        <Quote className="h-3.5 w-3.5 text-(--nous-fg-3)" aria-hidden />
        Quote
      </button>
    </div>
  );
}

/**
 * Raises a "Quote" action when the reader selects text inside a committed
 * assistant answer, and hands the passage to the composer as a markdown
 * blockquote.
 *
 * It reuses the existing `populate-chat-input` bridge in append mode — the
 * same channel the artifact panel's Cite uses — so the passage lands as
 * visible, editable text in the composer rather than as hidden context riding
 * along with the next message. Removing it is just deleting the text.
 *
 * Mounted once by the chat surface; there is no per-message wiring.
 */
export function QuoteToolbar(): React.ReactElement | null {
  const { selection, dismiss } = useQuoteSelection();

  if (!selection || typeof document === 'undefined') return null;

  const quote = (): void => {
    window.dispatchEvent(
      new CustomEvent('populate-chat-input', {
        detail: { text: asQuoteBlock(selection.text), mode: 'append' },
      })
    );
    window.getSelection()?.removeAllRanges();
    dismiss();
  };

  return createPortal(
    <Toolbar selection={selection} onQuote={quote} />,
    document.body
  );
}

export default QuoteToolbar;
