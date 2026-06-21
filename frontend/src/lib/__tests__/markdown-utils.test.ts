import { describe, it, expect } from 'vitest';

import { completeStreamingMarkdown } from '../markdown-utils';

describe('completeStreamingMarkdown', () => {
  it('returns empty/whole content unchanged when balanced', () => {
    expect(completeStreamingMarkdown('')).toBe('');
    expect(completeStreamingMarkdown('plain text, no fences')).toBe(
      'plain text, no fences'
    );
    expect(completeStreamingMarkdown('```js\nconst a = 1;\n```')).toBe(
      '```js\nconst a = 1;\n```'
    );
  });

  it('closes an unterminated fenced code block', () => {
    const partial = '```python\nprint("hi")';
    const out = completeStreamingMarkdown(partial);
    // Now an even number of fences -> renders as a code block, not raw text.
    expect((out.match(/^```/gm) || []).length % 2).toBe(0);
    expect(out.endsWith('```')).toBe(true);
  });

  it('closes a fence even when the open line has no language', () => {
    const out = completeStreamingMarkdown('intro\n```\nhalf a block');
    expect((out.match(/^```/gm) || []).length % 2).toBe(0);
  });

  it('does not double-close an already-closed block', () => {
    const closed = 'a\n```\ncode\n```\nb';
    expect(completeStreamingMarkdown(closed)).toBe(closed);
  });

  it('closes a trailing unterminated inline code span', () => {
    expect(completeStreamingMarkdown('use the `foo')).toBe('use the `foo`');
  });

  it('leaves a balanced inline code span alone', () => {
    expect(completeStreamingMarkdown('use `foo` here')).toBe('use `foo` here');
  });

  it('does not apply inline-tick fix while inside an open fence', () => {
    // Odd fence wins: we close the fence and skip the inline-tick branch.
    const out = completeStreamingMarkdown('```\nlet x = `tpl');
    expect(out.endsWith('```')).toBe(true);
    // No stray inline backtick appended after the fence close.
    expect(out.endsWith('`\n```')).toBe(false);
  });
});
