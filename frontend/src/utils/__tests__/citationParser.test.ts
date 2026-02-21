import {
  extractCitationIndices,
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
});
