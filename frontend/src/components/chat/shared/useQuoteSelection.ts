'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

/** Marks content a reader may quote — committed assistant answers only. */
export const QUOTABLE_ATTR = 'data-quotable';

/**
 * A long passage in the composer is noise, not context. Quoting is for a
 * claim, not a chapter.
 */
export const MAX_QUOTE_CHARS = 500;

export interface QuoteSelection {
  text: string;
  /** The selection is being made with the keyboard (shift+arrow, ctrl+A).
   * Only those need the toolbar to take focus; a mouse user is about to
   * click it, and stealing focus mid-drag would be gratuitous. */
  viaKeyboard: boolean;
  /** Viewport coordinates of the selection's top edge, for the toolbar. */
  top: number;
  left: number;
}

function readSelection(viaKeyboard: boolean): QuoteSelection | null {
  if (typeof window === 'undefined') return null;
  const selection = window.getSelection();
  if (!selection || selection.isCollapsed || selection.rangeCount === 0) {
    return null;
  }

  // Trailing whitespace is noise, but LEADING whitespace can be structure:
  // trimming it would strip the indentation off the first line of a selected
  // code block and change what the quote means. Only the surrounding blank
  // lines come off the front.
  const text = selection.toString().replace(/^[\r\n]+/, '').replace(/\s+$/, '');
  if (!text.trim()) return null;

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
    viaKeyboard,
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
  // Which input is driving the current selection. `selectionchange` does not
  // say, and the answer decides whether the toolbar may take focus.
  const viaKeyboardRef = useRef(false);

  const dismiss = useCallback(() => setSelection(null), []);

  useEffect(() => {
    const sync = (): void => setSelection(readSelection(viaKeyboardRef.current));
    const onKeyDown = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') {
        setSelection(null);
        return;
      }
      // Shift+arrow extends a selection; ctrl/cmd+A replaces it.
      if (e.shiftKey || e.key === 'a' || e.key === 'A') {
        viaKeyboardRef.current = true;
      }
    };
    const onPointerDown = (): void => {
      viaKeyboardRef.current = false;
    };

    document.addEventListener('selectionchange', sync);
    document.addEventListener('keydown', onKeyDown);
    document.addEventListener('pointerdown', onPointerDown, true);
    // The toolbar is positioned in viewport coordinates, so a scroll would
    // leave it stranded away from the text it belongs to.
    window.addEventListener('scroll', dismiss, true);
    return () => {
      document.removeEventListener('selectionchange', sync);
      document.removeEventListener('keydown', onKeyDown);
      document.removeEventListener('pointerdown', onPointerDown, true);
      window.removeEventListener('scroll', dismiss, true);
    };
  }, [dismiss]);

  return { selection, dismiss };
}
