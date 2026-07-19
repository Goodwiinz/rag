import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';

import { createTestQueryClient } from '@/test/test-utils';
import {
  projectSkillQueryKeys,
  useApproveProjectSkillChange,
  useProjectSkill,
  useProjectSkillCatalog,
  useProjectSkillDiff,
} from '@/hooks/useProjectSkills';
import { projectSkillService } from '@/services/projectSkillService';

vi.mock('@/services/projectSkillService', () => ({
  projectSkillService: {
    list: vi.fn(),
    get: vi.fn(),
    getDiff: vi.fn(),
    approve: vi.fn(),
    create: vi.fn(),
    proposeVersion: vi.fn(),
    reject: vi.fn(),
    rescan: vi.fn(),
    archive: vi.fn(),
    restore: vi.fn(),
    rollback: vi.fn(),
  },
}));

function wrapper({
  children,
}: {
  children: React.ReactNode;
}): React.ReactElement {
  return (
    <QueryClientProvider client={createTestQueryClient()}>
      {children}
    </QueryClientProvider>
  );
}

describe('project skill query hooks', () => {
  it('uses project-scoped stable keys and does not load detail or diff until selected', async () => {
    vi.mocked(projectSkillService.list).mockResolvedValue({
      skills: [],
      pending_change_requests: [],
      capabilities: { can_edit: true, can_admin: false },
    });
    const { result } = renderHook(
      () => ({
        catalog: useProjectSkillCatalog('project-1'),
        detail: useProjectSkill('project-1', undefined),
        diff: useProjectSkillDiff('project-1', undefined, undefined, undefined),
      }),
      { wrapper }
    );

    await waitFor(() => expect(result.current.catalog.isSuccess).toBe(true));
    expect(projectSkillService.list).toHaveBeenCalledWith('project-1');
    expect(projectSkillService.get).not.toHaveBeenCalled();
    expect(projectSkillService.getDiff).not.toHaveBeenCalled();
    expect(projectSkillQueryKeys.catalog('project-1')).toEqual([
      'project-skills',
      'project-1',
      'catalog',
    ]);
    expect(projectSkillQueryKeys.detail('project-1', 'release-notes')).toEqual([
      'project-skills',
      'project-1',
      'detail',
      'release-notes',
    ]);
    expect(
      projectSkillQueryKeys.diff('project-1', 'release-notes', 1, 2)
    ).toEqual(['project-skills', 'project-1', 'diff', 'release-notes', 1, 2]);
  });

  it('invalidates the catalog, pending, detail, history, and diff namespaces after approval', async () => {
    vi.mocked(projectSkillService.approve).mockResolvedValue({
      id: 'request-1',
    } as never);
    const client = createTestQueryClient();
    const invalidateQueries = vi.spyOn(client, 'invalidateQueries');
    const localWrapper = ({
      children,
    }: {
      children: React.ReactNode;
    }): React.ReactElement => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
    const { result } = renderHook(
      () => useApproveProjectSkillChange('project-1'),
      { wrapper: localWrapper }
    );

    await act(async () => {
      await result.current.mutateAsync({
        requestId: 'request-1',
        approval: {
          self_approval_acknowledged: false,
          warning_acknowledged: false,
          audit_note: null,
        },
      });
    });

    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: projectSkillQueryKeys.root('project-1'),
    });
  });
});
