import { describe, expect, it } from 'vitest';
import {
  extractCitationIndices,
  getReferencedCitations,
  hasCitations,
  parseMessageWithCitations,
} from '@/utils/citationParser';

describe('citationParser', () => {
  it('parses grouped doc citations into separate citation segments', () => {
    const segments = parseMessageWithCitations(
      'Threats include policy bypass [Doc 2, Doc 3, Doc 4] in multi-agent flows.'
    );

    const citationIndices = segments
      .filter((segment) => segment.type === 'citation')
      .map((segment) => segment.citationIndex);

    expect(citationIndices).toEqual([2, 3, 4]);
  });

  it('detects grouped citations as citations', () => {
    expect(hasCitations('See [Doc 2, Doc 3] for details.')).toBe(true);
  });

  it('extracts unique citation indices from grouped citations', () => {
    expect(
      extractCitationIndices('See [Doc 2, Doc 3, Doc 2] for details.')
    ).toEqual([2, 3]);
  });

  it('returns only citations referenced in the message content', () => {
    const citations = [
      { title: 'Doc 1', score: 0.9 },
      { title: 'Doc 2', score: 0.8 },
      { title: 'Doc 3', score: 0.7 },
    ];

    expect(
      getReferencedCitations('Use [Doc 3] and [1] only.', citations)
    ).toEqual([citations[0], citations[2]]);
  });

  it('returns no citations when the message has no inline references', () => {
    const citations = [{ title: 'Doc 1', score: 0.9 }];

    expect(getReferencedCitations('Hello there.', citations)).toEqual([]);
  });
});

describe('bare bracketed numbers that are not citations (round-3 M11)', () => {
  it('leaves array indexing as plain text', () => {
    // `[0]` is never a citation index, and a bracket chained off a
    // non-citation bracket reads as indexing.
    const segments = parseMessageWithCitations('Read arr[0] then arr[0][2].', {
      citationCount: 3,
    });
    expect(segments.every((segment) => segment.type === 'text')).toBe(true);
  });

  it('keeps a compact citation attached to a word', () => {
    const segments = parseMessageWithCitations('as claimed[1].', {
      citationCount: 2,
    });
    expect(
      segments.find((segment) => segment.type === 'citation')?.citationIndex
    ).toBe(1);
  });

  it('leaves years alone', () => {
    const segments = parseMessageWithCitations('Published [2023] widely.', {
      citationCount: 3,
    });
    expect(segments.every((segment) => segment.type === 'text')).toBe(true);
  });

  it('leaves markdown link references alone', () => {
    const inline = parseMessageWithCitations('See [1](https://example.com).', {
      citationCount: 3,
    });
    const definition = parseMessageWithCitations('[1]: https://example.com', {
      citationCount: 3,
    });
    expect(inline.every((segment) => segment.type === 'text')).toBe(true);
    expect(definition.every((segment) => segment.type === 'text')).toBe(true);
  });

  it('drops bare indices the message cannot resolve', () => {
    const segments = parseMessageWithCitations('As shown in [4].', {
      citationCount: 2,
    });
    expect(segments.every((segment) => segment.type === 'text')).toBe(true);
  });

  it('still treats a resolvable bare index as a citation', () => {
    const segments = parseMessageWithCitations('As shown in [2].', {
      citationCount: 2,
    });
    expect(segments.some((segment) => segment.type === 'citation')).toBe(true);
  });

  it('still honours an explicit label regardless of surrounding syntax', () => {
    const segments = parseMessageWithCitations('Per the paper [Doc 1]:', {
      citationCount: 1,
    });
    expect(
      segments.find((segment) => segment.type === 'citation')?.citationIndex
    ).toBe(1);
  });
});

describe('chained bare citations (verification follow-up)', () => {
  it('keeps both halves of [1][2]', () => {
    const indices = parseMessageWithCitations('evidence [1][2].', {
      citationCount: 3,
    })
      .filter((segment) => segment.type === 'citation')
      .map((segment) => segment.citationIndex);
    expect(indices).toEqual([1, 2]);
  });

  it('still rejects a bracket chained off a non-citation bracket', () => {
    const segments = parseMessageWithCitations('m[0][2] is a cell.', {
      citationCount: 3,
    });
    expect(segments.every((segment) => segment.type === 'text')).toBe(true);
  });
});
