/**
 * fetchProject in-flight dedup (Sentry JAVASCRIPT-NEXTJS-3Q).
 *
 * /chat's layout effect and the project page re-invoke fetchProject on render
 * churn before the first GET settles; without dedup each call issued another
 * identical /projects/{id} request, queueing over HTTP/1.1.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Mocked } from 'vitest';
import { useProjectStore } from '../projectStore';
import { projectService } from '@/services/projectService';
import type { Project } from '@/services/projectService';

vi.mock('@/services/projectService', () => ({
  projectService: {
    getProject: vi.fn(),
  },
}));

const mockService = projectService as Mocked<typeof projectService>;

const project = (id: string): Project =>
  ({ id, name: `Project ${id}` }) as Project;

describe('projectStore.fetchProject dedup', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useProjectStore.setState({ currentProject: null, loading: false, error: null });
  });

  it('shares one request across concurrent calls for the same id', async () => {
    let resolve!: (p: Project) => void;
    mockService.getProject.mockReturnValue(
      new Promise<Project>((r) => {
        resolve = r;
      })
    );

    const { fetchProject } = useProjectStore.getState();
    const first = fetchProject('p1');
    const second = fetchProject('p1');

    expect(mockService.getProject).toHaveBeenCalledTimes(1);
    resolve(project('p1'));
    await Promise.all([first, second]);

    expect(useProjectStore.getState().currentProject?.id).toBe('p1');
  });

  it('fetches again once the previous request settled', async () => {
    mockService.getProject.mockResolvedValue(project('p1'));
    const { fetchProject } = useProjectStore.getState();

    await fetchProject('p1');
    await fetchProject('p1');

    expect(mockService.getProject).toHaveBeenCalledTimes(2);
  });

  it('does not dedup a different project id', async () => {
    let resolveP1!: (p: Project) => void;
    mockService.getProject
      .mockReturnValueOnce(
        new Promise<Project>((r) => {
          resolveP1 = r;
        })
      )
      .mockResolvedValueOnce(project('p2'));

    const { fetchProject } = useProjectStore.getState();
    const first = fetchProject('p1');
    const second = fetchProject('p2');

    expect(mockService.getProject).toHaveBeenCalledTimes(2);
    resolveP1(project('p1'));
    await Promise.all([first, second]);

    // A third call for p2 after settle fetches fresh (slot was not clobbered
    // by p1's cleanup).
    mockService.getProject.mockResolvedValueOnce(project('p2'));
    await fetchProject('p2');
    expect(mockService.getProject).toHaveBeenCalledTimes(3);
  });
});
