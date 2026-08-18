import { describe, expect, it } from 'vitest';
import React from 'react';
import { render } from '@testing-library/react';
import { ChatMarkdown } from '../ChatMarkdown';

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
});
