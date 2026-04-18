import { projectService } from '../projectService';

describe('projectService.downloadBibliography', () => {
  const createObjectURL = jest.fn(() => 'blob:download-url');
  const revokeObjectURL = jest.fn();
  const appendChild = jest.spyOn(document.body, 'appendChild');
  const removeChild = jest.spyOn(document.body, 'removeChild');

  beforeEach(() => {
    jest.restoreAllMocks();
    appendChild.mockImplementation(() => document.createElement('div'));
    removeChild.mockImplementation(() => document.createElement('div'));
    Object.defineProperty(window, 'URL', {
      writable: true,
      value: {
        createObjectURL,
        revokeObjectURL,
      },
    });
  });

  it('uses the .bib extension for bibtex downloads', async () => {
    jest
      .spyOn(projectService, 'getProjectBibliography')
      .mockResolvedValue({
        project_id: 'proj-1',
        project_name: 'alpha-project',
        format: 'bibtex',
        content: '@article{test}',
        citation_count: 1,
        generated_at: new Date().toISOString(),
      });

    const click = jest.fn();
    const originalCreateElement = document.createElement.bind(document);
    jest.spyOn(document, 'createElement').mockImplementation((tagName: string) => {
      if (tagName === 'a') {
        const anchor = originalCreateElement('a');
        jest.spyOn(anchor, 'click').mockImplementation(click);
        return anchor;
      }
      return originalCreateElement(tagName);
    });

    await projectService.downloadBibliography('proj-1', 'bibtex');

    const createdAnchor = (document.createElement as jest.Mock).mock.results[0]
      .value as HTMLAnchorElement;
    expect(createdAnchor.download).toBe('alpha-project-bibliography.bib');
    expect(click).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:download-url');
  });
});
