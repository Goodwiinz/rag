/**
 * @vitest-environment node
 */
import { describe, expect, test } from 'vitest';
import {
  countVisualRows,
  hasMarkdown,
  renderMarkdown,
  stripAnsi,
} from '../markdown';

describe('hasMarkdown', () => {
  test('detects headings, bullets, fences, inline emphasis', () => {
    expect(hasMarkdown('# Title')).toBe(true);
    expect(hasMarkdown('- item')).toBe(true);
    expect(hasMarkdown('1. one')).toBe(true);
    expect(hasMarkdown('```ts\ncode\n```')).toBe(true);
    expect(hasMarkdown('a `code span` here')).toBe(true);
    expect(hasMarkdown('a **bold** word')).toBe(true);
    expect(hasMarkdown('a *italic* word')).toBe(true);
    expect(hasMarkdown('a _emph_ word')).toBe(true);
  });

  test('returns false for plain prose', () => {
    expect(hasMarkdown('hello world, this is a sentence.')).toBe(false);
    expect(hasMarkdown('')).toBe(false);
  });
});

describe('renderMarkdown', () => {
  test('renders headings as bold (text content preserved)', () => {
    const out = renderMarkdown('# Hello');
    expect(stripAnsi(out)).toBe('Hello');
    expect(out).toContain('\x1b[1m');
  });

  test('replaces bullets with • and recurses into inline', () => {
    const out = renderMarkdown('- one\n- two');
    expect(stripAnsi(out)).toBe('• one\n• two');
  });

  test('renumbers ordered lists by preserving the number', () => {
    const out = renderMarkdown('1. a\n2. b');
    expect(stripAnsi(out)).toBe('1. a\n2. b');
  });

  test('renders inline bold/italic/code with ANSI', () => {
    const out = renderMarkdown('a **bold** and `code`');
    expect(stripAnsi(out)).toBe('a bold and code');
    expect(out).toContain('\x1b[1m');
    expect(out).toContain('\x1b[36m');
  });

  test('preserves fenced code body verbatim', () => {
    const out = renderMarkdown('```\nlet x = 1;\n```');
    expect(stripAnsi(out)).toBe('```\nlet x = 1;\n```');
  });

  test('does not match emphasis across lines', () => {
    const out = renderMarkdown('one *two\nthree* four');
    // The * at end of "two" has no closing partner on same line, so no match
    expect(stripAnsi(out)).toBe('one *two\nthree* four');
  });
});

describe('countVisualRows', () => {
  test('returns 0 for empty', () => {
    expect(countVisualRows('', 80)).toBe(0);
  });

  test('counts wrapped rows when a line exceeds columns', () => {
    expect(countVisualRows('x'.repeat(81), 80)).toBe(2);
    expect(countVisualRows('x'.repeat(160), 80)).toBe(2);
    expect(countVisualRows('x'.repeat(161), 80)).toBe(3);
  });

  test('counts each blank line as one row', () => {
    expect(countVisualRows('a\n\nb', 80)).toBe(3);
  });

  test('ignores ANSI escape codes when measuring width', () => {
    const styled = '\x1b[1mhello\x1b[22m';
    expect(countVisualRows(styled, 80)).toBe(1);
  });
});
