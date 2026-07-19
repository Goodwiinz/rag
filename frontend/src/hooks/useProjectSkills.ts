'use client';

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';

import {
  projectSkillService,
  type ProjectSkillApproval,
  type ProjectSkillCatalog,
  type ProjectSkillDiff,
  type ProjectSkillDocument,
  type ProjectSkillRejection,
  type ProjectSkillRollback,
  type ProjectSkill,
} from '@/services/projectSkillService';

export const projectSkillQueryKeys = {
  root: (projectId: string): readonly ['project-skills', string] =>
    ['project-skills', projectId] as const,
  catalog: (
    projectId: string
  ): readonly ['project-skills', string, 'catalog'] =>
    [...projectSkillQueryKeys.root(projectId), 'catalog'] as const,
  pending: (
    projectId: string
  ): readonly ['project-skills', string, 'pending'] =>
    [...projectSkillQueryKeys.root(projectId), 'pending'] as const,
  detail: (
    projectId: string,
    skillName: string
  ): readonly ['project-skills', string, 'detail', string] =>
    [...projectSkillQueryKeys.root(projectId), 'detail', skillName] as const,
  history: (
    projectId: string,
    skillName: string
  ): readonly ['project-skills', string, 'history', string] =>
    [...projectSkillQueryKeys.root(projectId), 'history', skillName] as const,
  diff: (
    projectId: string,
    skillName: string,
    fromVersion: number,
    toVersion: number
  ): readonly ['project-skills', string, 'diff', string, number, number] =>
    [
      ...projectSkillQueryKeys.root(projectId),
      'diff',
      skillName,
      fromVersion,
      toVersion,
    ] as const,
};

export function useProjectSkillCatalog(
  projectId: string,
  enabled = true
): UseQueryResult<ProjectSkillCatalog, Error> {
  return useQuery({
    queryKey: projectSkillQueryKeys.catalog(projectId),
    queryFn: () => projectSkillService.list(projectId),
    enabled: enabled && Boolean(projectId),
    retry: false,
  });
}

export function useProjectSkill(
  projectId: string,
  skillName?: string
): UseQueryResult<ProjectSkill, Error> {
  return useQuery({
    queryKey: projectSkillQueryKeys.detail(projectId, skillName ?? ''),
    queryFn: () => projectSkillService.get(projectId, skillName!),
    enabled: Boolean(projectId && skillName),
  });
}

export function useProjectSkillHistory(
  projectId: string,
  skillName?: string
): UseQueryResult<ProjectSkill, Error> {
  return useQuery({
    queryKey: projectSkillQueryKeys.history(projectId, skillName ?? ''),
    queryFn: () => projectSkillService.get(projectId, skillName!),
    enabled: Boolean(projectId && skillName),
  });
}

export function useProjectSkillDiff(
  projectId: string,
  skillName?: string,
  fromVersion?: number,
  toVersion?: number
): UseQueryResult<ProjectSkillDiff, Error> {
  return useQuery({
    queryKey: projectSkillQueryKeys.diff(
      projectId,
      skillName ?? '',
      fromVersion ?? 0,
      toVersion ?? 0
    ),
    queryFn: () =>
      projectSkillService.getDiff(
        projectId,
        skillName!,
        fromVersion!,
        toVersion!
      ),
    enabled: Boolean(projectId && skillName && fromVersion && toVersion),
  });
}

function useProjectSkillMutation<TVariables>(
  mutationFn: (variables: TVariables) => Promise<unknown>,
  projectId: string
): UseMutationResult<unknown, Error, TVariables> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: async (): Promise<void> => {
      await queryClient.invalidateQueries({
        queryKey: projectSkillQueryKeys.root(projectId),
      });
    },
  });
}

export function useCreateProjectSkill(
  projectId: string
): UseMutationResult<unknown, Error, ProjectSkillDocument> {
  return useProjectSkillMutation(
    (document: ProjectSkillDocument) =>
      projectSkillService.create(projectId, document),
    projectId
  );
}

export function useProposeProjectSkillVersion(
  projectId: string
): UseMutationResult<
  unknown,
  Error,
  { skillName: string; document: ProjectSkillDocument }
> {
  return useProjectSkillMutation(
    ({
      skillName,
      document,
    }: {
      skillName: string;
      document: ProjectSkillDocument;
    }) => projectSkillService.proposeVersion(projectId, skillName, document),
    projectId
  );
}

export function useApproveProjectSkillChange(
  projectId: string
): UseMutationResult<
  unknown,
  Error,
  { requestId: string; approval: ProjectSkillApproval }
> {
  return useProjectSkillMutation(
    ({
      requestId,
      approval,
    }: {
      requestId: string;
      approval: ProjectSkillApproval;
    }) => projectSkillService.approve(projectId, requestId, approval),
    projectId
  );
}

export function useRejectProjectSkillChange(
  projectId: string
): UseMutationResult<
  unknown,
  Error,
  { requestId: string; rejection: ProjectSkillRejection }
> {
  return useProjectSkillMutation(
    ({
      requestId,
      rejection,
    }: {
      requestId: string;
      rejection: ProjectSkillRejection;
    }) => projectSkillService.reject(projectId, requestId, rejection),
    projectId
  );
}

export function useRescanProjectSkillChange(
  projectId: string
): UseMutationResult<unknown, Error, string> {
  return useProjectSkillMutation(
    (requestId: string) => projectSkillService.rescan(projectId, requestId),
    projectId
  );
}

export function useArchiveProjectSkill(
  projectId: string
): UseMutationResult<unknown, Error, string> {
  return useProjectSkillMutation(
    (skillName: string) => projectSkillService.archive(projectId, skillName),
    projectId
  );
}

export function useRestoreProjectSkill(
  projectId: string
): UseMutationResult<unknown, Error, string> {
  return useProjectSkillMutation(
    (skillName: string) => projectSkillService.restore(projectId, skillName),
    projectId
  );
}

export function useRollbackProjectSkill(
  projectId: string
): UseMutationResult<
  unknown,
  Error,
  { skillName: string; rollback: ProjectSkillRollback }
> {
  return useProjectSkillMutation(
    ({
      skillName,
      rollback,
    }: {
      skillName: string;
      rollback: ProjectSkillRollback;
    }) => projectSkillService.rollback(projectId, skillName, rollback),
    projectId
  );
}
