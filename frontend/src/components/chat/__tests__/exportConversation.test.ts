import {
  ExportableMessage,
  downloadFile,
  exportAsJson,
  exportAsMarkdown,
} from '../shared/exportConversation';

const sample: ExportableMessage[] = [
  { role: 'user', content: 'hello', timestamp: 0 },
  { role: 'assistant', content: 'hi there', timestamp: 1000 },
];

describe('exportAsMarkdown', () => {
  it('prefixes with title as H1', () => {
    const md = exportAsMarkdown('Demo', sample);
    expect(md.startsWith('# Demo\n\n')).toBe(true);
  });

  it('renders user and assistant role headers', () => {
    const md = exportAsMarkdown('Demo', sample);
    expect(md).toContain('**You**');
    expect(md).toContain('**Assistant**');
  });

  it('includes ISO timestamps', () => {
    const md = exportAsMarkdown('Demo', sample);
    expect(md).toContain(new Date(0).toISOString());
    expect(md).toContain(new Date(1000).toISOString());
  });

  it('separates messages with ---', () => {
    const md = exportAsMarkdown('Demo', sample);
    expect(md.split('\n---\n').length).toBe(2);
  });

  it('handles empty message list', () => {
    expect(exportAsMarkdown('Empty', [])).toBe('# Empty\n\n');
  });
});

describe('exportAsJson', () => {
  it('produces valid parseable JSON containing title + messages', () => {
    const json = exportAsJson('Demo', sample);
    const parsed = JSON.parse(json);
    expect(parsed.title).toBe('Demo');
    expect(parsed.messages).toHaveLength(2);
    expect(parsed.messages[0].content).toBe('hello');
  });

  it('uses 2-space indentation', () => {
    const json = exportAsJson('X', sample);
    expect(json).toContain('  "title"');
  });
});

describe('downloadFile', () => {
  it('creates and clicks an anchor element, then revokes the URL', () => {
    const createObjectURL = jest.fn(() => 'blob:mock');
    const revokeObjectURL = jest.fn();
    // Override URL methods
    (
      URL as unknown as { createObjectURL: typeof createObjectURL }
    ).createObjectURL = createObjectURL;
    (
      URL as unknown as { revokeObjectURL: typeof revokeObjectURL }
    ).revokeObjectURL = revokeObjectURL;
    const clickSpy = jest.fn();
    const origCreateElement = document.createElement.bind(document);
    const createElementSpy = jest
      .spyOn(document, 'createElement')
      .mockImplementation((tag: string) => {
        const el = origCreateElement(tag);
        if (tag === 'a') {
          (el as HTMLAnchorElement).click = clickSpy;
        }
        return el;
      });

    downloadFile('x.md', 'text/markdown', '# hi');

    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(clickSpy).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:mock');
    createElementSpy.mockRestore();
  });
});
