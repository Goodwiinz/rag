import { describe, expect, it } from 'vitest';
import { appendToDraft } from '../appendToDraft';

describe('appendToDraft', () => {
  it('starts a quoted passage on its own line when a draft exists', () => {
    // The bug this pins: joining with a space left `>` mid-line, where
    // markdown reads it as a literal angle bracket and renders no blockquote.
    const out = appendToDraft('what about', '\n> Grounding helps.\n\n');
    expect(out).toBe('what about\n> Grounding helps.\n\n');
    expect(out.split('\n')[1].startsWith('>')).toBe(true);
  });

  it('keeps the space join for inline payloads', () => {
    // The artifact panel's Cite appends a reference that belongs in the
    // sentence being typed, not on a line of its own.
    expect(appendToDraft('see also', '[Doc 3]')).toBe('see also [Doc 3]');
  });

  it('drops the leading newline into an empty composer', () => {
    expect(appendToDraft('', '\n> Grounding helps.\n\n')).toBe(
      '> Grounding helps.\n\n '
    );
  });

  it('leaves an inline payload in an empty composer alone', () => {
    expect(appendToDraft('', '[Doc 3]')).toBe('[Doc 3] ');
  });
});
