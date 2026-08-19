import { afterEach, describe, expect, it, vi } from 'vitest';
import React from 'react';
import { fireEvent, render, screen, act } from '@testing-library/react';
import { QuoteToolbar } from '../QuoteToolbar';
import { MAX_QUOTE_CHARS } from '../useQuoteSelection';

/**
 * jsdom has no real selection geometry, so the Range is stubbed. What these
 * tests pin is the logic around it: what counts as quotable, when the action
 * appears and clears, and what reaches the composer.
 */
function selectInside(container: HTMLElement, text: string): void {
  const node = container.firstChild as Node;
  const range = {
    commonAncestorContainer: node,
    getBoundingClientRect: () => ({ top: 100, left: 40, width: 60, height: 18 }),
  };
  vi.spyOn(window, 'getSelection').mockReturnValue({
    isCollapsed: false,
    rangeCount: 1,
    toString: () => text,
    getRangeAt: () => range,
    removeAllRanges: vi.fn(),
  } as unknown as Selection);
  act(() => {
    document.dispatchEvent(new Event('selectionchange'));
  });
}

function clearSelection(): void {
  vi.spyOn(window, 'getSelection').mockReturnValue({
    isCollapsed: true,
    rangeCount: 0,
    toString: () => '',
  } as unknown as Selection);
  act(() => {
    document.dispatchEvent(new Event('selectionchange'));
  });
}

afterEach(() => {
  vi.restoreAllMocks();
  // Remove only our own hosts — clearing document.body would yank React's
  // portal container out from under its cleanup.
  document.querySelectorAll('[data-test-host]').forEach((n) => n.remove());
});

function makeHost(text: string, quotable = true): HTMLElement {
  const host = document.createElement('div');
  host.setAttribute('data-test-host', '');
  if (quotable) host.setAttribute('data-quotable', '');
  // A text node is required: the range anchors to it.
  host.textContent = text;
  document.body.appendChild(host);
  return host;
}

describe('QuoteToolbar', () => {
  it('offers to quote a selection inside committed assistant content', () => {
    const host = makeHost('Retrieval grounds the answer.');

    render(<QuoteToolbar />);
    selectInside(host, 'Retrieval grounds the answer.');

    expect(screen.getByRole('button', { name: /quote/i })).toBeInTheDocument();
  });

  it('ignores a selection outside quotable content', () => {
    // A user message, or the streaming bubble, carries no data-quotable —
    // quoting a turn that is still being written would quote a moving target.
    const host = makeHost('Something the user typed.', false);

    render(<QuoteToolbar />);
    selectInside(host, 'Something the user typed.');

    expect(screen.queryByRole('button', { name: /quote/i })).toBeNull();
  });

  it('hands the passage to the composer as an appended blockquote', () => {
    const host = makeHost('Grounding reduces fabrication.');

    const listener = vi.fn();
    window.addEventListener('populate-chat-input', listener);

    render(<QuoteToolbar />);
    selectInside(host, 'Grounding reduces fabrication.');
    // click, not mouseDown: mousedown only suppresses the selection collapse
    // so this toolbar survives; the action rides the click, which is also
    // what Enter, Space and assistive-technology activation synthesise.
    fireEvent.click(screen.getByRole('button', { name: /quote/i }));

    expect(listener).toHaveBeenCalledTimes(1);
    const detail = (listener.mock.calls[0][0] as CustomEvent).detail;
    expect(detail.mode).toBe('append');
    expect(detail.text).toContain('> Grounding reduces fabrication.');
    // Opens its own line: appended after a draft, a `>` mid-line is a literal
    // angle bracket and markdown renders no blockquote at all.
    expect(detail.text.startsWith('\n')).toBe(true);

    window.removeEventListener('populate-chat-input', listener);
  });

  it('keeps the indentation of quoted code', () => {
    // Trimming the selection would strip the leading spaces off the first
    // line and silently change the structure of the quoted snippet.
    const host = makeHost('code');

    const listener = vi.fn();
    window.addEventListener('populate-chat-input', listener);

    render(<QuoteToolbar />);
    selectInside(host, '\n    return owned_ids\n');
    fireEvent.click(screen.getByRole('button', { name: /quote/i }));

    const detail = (listener.mock.calls[0][0] as CustomEvent).detail;
    expect(detail.text).toContain('>     return owned_ids');

    window.removeEventListener('populate-chat-input', listener);
  });

  it('does not take focus while a keyboard selection is still growing', () => {
    // selectionchange fires on the first shift+arrow. Focusing the button
    // there pointed every later arrow key at the button instead of the
    // passage, so the selection could never grow past one increment.
    const host = makeHost('A claim worth quoting.');

    render(<QuoteToolbar />);
    act(() => {
      document.dispatchEvent(
        new KeyboardEvent('keydown', { key: 'ArrowRight', shiftKey: true })
      );
    });
    selectInside(host, 'A claim');

    expect(screen.getByRole('button', { name: /quote/i })).not.toBe(
      document.activeElement
    );
  });

  it('never takes focus from a mouse selection', () => {
    const host = makeHost('A claim worth quoting.');

    render(<QuoteToolbar />);
    act(() => {
      document.dispatchEvent(new Event('pointerdown', { bubbles: true }));
    });
    selectInside(host, 'A claim worth quoting.');

    vi.useFakeTimers();
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    vi.useRealTimers();

    expect(screen.getByRole('button', { name: /quote/i })).not.toBe(
      document.activeElement
    );
  });

  it('dismisses on Escape and when the selection clears', () => {
    const host = makeHost('A claim worth quoting.');

    render(<QuoteToolbar />);
    selectInside(host, 'A claim worth quoting.');
    expect(screen.getByRole('button', { name: /quote/i })).toBeInTheDocument();

    act(() => {
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    });
    expect(screen.queryByRole('button', { name: /quote/i })).toBeNull();

    selectInside(host, 'A claim worth quoting.');
    clearSelection();
    expect(screen.queryByRole('button', { name: /quote/i })).toBeNull();
  });

  it('caps a very long passage', () => {
    const host = makeHost('a long passage');

    const listener = vi.fn();
    window.addEventListener('populate-chat-input', listener);

    render(<QuoteToolbar />);
    selectInside(host, 'x'.repeat(MAX_QUOTE_CHARS + 250));
    fireEvent.click(screen.getByRole('button', { name: /quote/i }));

    const detail = (listener.mock.calls[0][0] as CustomEvent).detail;
    // "> " prefix plus the trailing blank line, but not the extra 250 chars.
    expect(detail.text.length).toBeLessThan(MAX_QUOTE_CHARS + 20);

    window.removeEventListener('populate-chat-input', listener);
  });
});
