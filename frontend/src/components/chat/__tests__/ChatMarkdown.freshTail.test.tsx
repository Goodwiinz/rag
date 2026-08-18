import { describe, expect, it } from 'vitest';
import React from 'react';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { render } from '@testing-library/react';
import { ChatMarkdown } from '../ChatMarkdown';
import { ChatMarkdownMath } from '../ChatMarkdownMath';

const fresh = (c: HTMLElement): HTMLElement | null =>
  c.querySelector('[data-fresh="true"]');

describe('ChatMarkdown fresh tail', () => {
  it('tags nothing for a committed message', () => {
    const { container } = render(<ChatMarkdown content="All done here." />);
    expect(fresh(container)).toBeNull();
  });

  it('tags the trailing text while streaming', () => {
    const { container } = render(
      <ChatMarkdown content="The quick brown fox jumps over it" freshTail />
    );
    const tail = fresh(container);
    expect(tail).not.toBeNull();
    // The tail is the END of the text, and only part of it.
    const full = container.textContent ?? '';
    const tailText = tail?.textContent ?? '';
    expect(full.endsWith(tailText)).toBe(true);
    expect(tailText.length).toBeGreaterThan(0);
    expect(tailText.length).toBeLessThan(full.length);
  });

  it('keeps markdown formatting while tagging', () => {
    // Tagging after the parse is the whole point: splitting into words first
    // would cost live bold/lists/headings for the duration of the stream.
    const { container } = render(
      <ChatMarkdown
        content="Some **bold** text and a longer trailing sentence"
        freshTail
      />
    );
    expect(container.querySelector('strong')?.textContent).toBe('bold');
    expect(fresh(container)).not.toBeNull();
  });

  it('does not tag inside a code fence', () => {
    const { container } = render(
      <ChatMarkdown content={'prose first\n\n```\nconst x = 1;\n```'} freshTail />
    );
    const tail = fresh(container);
    expect(tail).not.toBeNull();
    expect(tail?.closest('pre')).toBeNull();
    expect(tail?.textContent).not.toContain('const');
  });

  it('follows the growing edge across streaming re-renders', () => {
    const { container, rerender } = render(
      <ChatMarkdown content="The first tokens arrive here" freshTail />
    );
    expect(fresh(container)?.textContent).toContain('arrive');

    rerender(
      <ChatMarkdown
        content="The first tokens arrive here and settle as newer text follows them"
        freshTail
      />
    );
    const tail = fresh(container)?.textContent ?? '';
    // The span now holds the newest characters; the earlier tokens have
    // moved out of it and render as settled ink.
    expect((container.textContent ?? '').endsWith(tail)).toBe(true);
    expect(tail.length).toBeGreaterThan(0);
    expect(tail).not.toContain('first');
  });

  it('tints statically — no CSS animation to go stale on the reused span', () => {
    // React reconciles the tail span across token renders and only swaps its
    // text node, so a CSS animation would run once on the first tokens and
    // never restart — the tint would die 700ms into a multi-second stream.
    // The settle effect must come from characters leaving the span (previous
    // test), never from a keyframe on the span itself.
    const css = readFileSync(
      resolve(process.cwd(), 'app/nous-tokens.css'),
      'utf8'
    );
    const block = /\[data-fresh='true'\]\s*\{[^}]*\}/.exec(css)?.[0] ?? '';
    expect(block).toContain('var(--nous-');
    expect(block).not.toContain('animation');
  });

  it('does not split a surrogate pair at the tail boundary', () => {
    // 10 chars + a 2-unit emoji + 23 chars puts the 24-char boundary between
    // the emoji's surrogate halves; the pair must stay whole in the tail.
    const content = `${'a'.repeat(10)}\u{1F600}${'b'.repeat(23)}`;
    const { container } = render(<ChatMarkdown content={content} freshTail />);
    const tail = fresh(container)?.textContent ?? '';
    expect(tail.startsWith('\u{1F600}')).toBe(true);
  });
});

describe('ChatMarkdown fresh tail around KaTeX', () => {
  it('skips KaTeX markup when the message ends with an expression', () => {
    const { container } = render(
      <ChatMarkdownMath content="The energy relation reads $E=mc^2$" freshTail />
    );
    expect(container.querySelector('.katex')).not.toBeNull();
    const tail = fresh(container);
    expect(tail).not.toBeNull();
    expect(tail?.closest('.katex, .katex-display')).toBeNull();
    expect(container.querySelector('.katex [data-fresh]')).toBeNull();
  });

  it('tints nothing when the whole message is math', () => {
    const { container } = render(
      <ChatMarkdownMath content="$$E=mc^2$$" freshTail />
    );
    expect(container.querySelector('.katex')).not.toBeNull();
    expect(fresh(container)).toBeNull();
  });
});
