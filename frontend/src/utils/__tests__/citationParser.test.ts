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
    expect(extractCitationIndices('See [Doc 2, Doc 3, Doc 2] for details.')).toEqual([
      2, 3,
    ]);
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
