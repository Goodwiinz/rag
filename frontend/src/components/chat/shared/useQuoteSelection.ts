'use client';

import { useCallback, useEffect, useState } from 'react';

/** Marks content a reader may quote — committed assistant answers only. */
export const QUOTABLE_ATTR = 'data-quotable';

/**
 * A long passage in the composer is noise, not context. Quoting is for a
 * claim, not a chapter.
 */
export const MAX_QUOTE_CHARS = 500;

export interface QuoteSelection {
  text: string;
  /** Viewport coordinates of the selection's top edge, for the toolbar. */
  top: number;
  left: number;
}

function readSelection(): QuoteSelection | null {
  if (typeof window === 'undefined') return null;
  const selection = window.getSelection();
  if (!selection || selection.isCollapsed || selection.rangeCount === 0) {
    return null;
  }

  const text = selection.toString().trim();
  if (!text) return null;

  // Only quote from committed assistant content. A selection that starts
  // outside one — or spans out of it — is not a quote of a single answer.
  const range = selection.getRangeAt(0);
  const container =
    range.commonAncestorContainer.nodeType === Node.ELEMENT_NODE
      ? (range.commonAncestorContainer as Element)
      : range.commonAncestorContainer.parentElement;
  if (!container?.closest(`[${QUOTABLE_ATTR}]`)) return null;

  const rect = range.getBoundingClientRect();
  if (rect.width === 0 && rect.height === 0) return null;

  return {
    text: text.slice(0, MAX_QUOTE_CHARS),
    top: rect.top,
    left: rect.left + rect.width / 2,
  };
}

/**
 * Watches for a text selection inside committed assistant content.
 *
 * Listens on `selectionchange` rather than mouseup so a keyboard selection
 * (shift+arrow) raises the toolbar too — selection-triggered UI is easy to
 * make mouse-only by accident.
 */
export function useQuoteSelection(): {
  selection: QuoteSelection | null;
  dismiss: () => void;
} {
  const [selection, setSelection] = useState<QuoteSelection | null>(null);

  const dismiss = useCallback(() => setSelection(null), []);

  useEffect(() => {
    const sync = (): void => setSelection(readSelection());
    const onKeyDown = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') setSelection(null);
    };

    document.addEventListener('selectionchange', sync);
    document.addEventListener('keydown', onKeyDown);
    // The toolbar is positioned in viewport coordinates, so a scroll would
    // leave it stranded away from the text it belongs to.
    window.addEventListener('scroll', dismiss, true);
    return () => {
      document.removeEventListener('selectionchange', sync);
      document.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('scroll', dismiss, true);
    };
  }, [dismiss]);

  return { selection, dismiss };
}
