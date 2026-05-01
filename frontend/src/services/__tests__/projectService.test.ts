import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Mock } from 'vitest';
import { projectService } from '../projectService';

describe('projectService.downloadBibliography', () => {
  const createObjectURL = vi.fn(() => 'blob:download-url');
  const revokeObjectURL = vi.fn();
  const appendChild = vi.spyOn(document.body, 'appendChild');
  const removeChild = vi.spyOn(document.body, 'removeChild');

  beforeEach(() => {
    vi.restoreAllMocks();
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
    vi.spyOn(projectService, 'getProjectBibliography')
      .mockResolvedValue({
        project_id: 'proj-1',
        project_name: 'alpha-project',
        format: 'bibtex',
        content: '@article{test}',
        citation_count: 1,
        generated_at: new Date().toISOString(),
      });

    const click = vi.fn();
    const originalCreateElement = document.createElement.bind(document);
    vi.spyOn(document, 'createElement').mockImplementation((tagName: string) => {
      if (tagName === 'a') {
        const anchor = originalCreateElement('a');
        vi.spyOn(anchor, 'click').mockImplementation(click);
        return anchor;
      }
      return originalCreateElement(tagName);
    });

    await projectService.downloadBibliography('proj-1', 'bibtex');

    const createdAnchor = (document.createElement as Mock).mock.results[0]
      .value as HTMLAnchorElement;
    expect(createdAnchor.download).toBe('alpha-project-bibliography.bib');
    expect(click).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:download-url');
  });
});
