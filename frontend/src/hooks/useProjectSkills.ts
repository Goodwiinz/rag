'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  projectSkillService,
  type ProjectSkillApproval,
  type ProjectSkillDocument,
  type ProjectSkillRejection,
  type ProjectSkillRollback,
} from '@/services/projectSkillService';

export const projectSkillQueryKeys = {
  root: (projectId: string) => ['project-skills', projectId] as const,
  catalog: (projectId: string) =>
    [...projectSkillQueryKeys.root(projectId), 'catalog'] as const,
  pending: (projectId: string) =>
    [...projectSkillQueryKeys.root(projectId), 'pending'] as const,
  detail: (projectId: string, skillName: string) =>
    [...projectSkillQueryKeys.root(projectId), 'detail', skillName] as const,
  history: (projectId: string, skillName: string) =>
    [...projectSkillQueryKeys.root(projectId), 'history', skillName] as const,
  diff: (projectId: string, skillName: string, fromVersion: number, toVersion: number) =>
    [...projectSkillQueryKeys.root(projectId), 'diff', skillName, fromVersion, toVersion] as const,
};

export function useProjectSkillCatalog(projectId: string, enabled = true) {
  return useQuery({
    queryKey: projectSkillQueryKeys.catalog(projectId),
    queryFn: () => projectSkillService.list(projectId),
    enabled: enabled && Boolean(projectId),
    retry: false,
  });
}

export function useProjectSkill(projectId: string, skillName?: string) {
  return useQuery({
    queryKey: projectSkillQueryKeys.detail(projectId, skillName ?? ''),
    queryFn: () => projectSkillService.get(projectId, skillName!),
    enabled: Boolean(projectId && skillName),
  });
}

export function useProjectSkillHistory(projectId: string, skillName?: string) {
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
) {
  return useQuery({
    queryKey: projectSkillQueryKeys.diff(
      projectId,
      skillName ?? '',
      fromVersion ?? 0,
      toVersion ?? 0
    ),
    queryFn: () =>
      projectSkillService.getDiff(projectId, skillName!, fromVersion!, toVersion!),
    enabled: Boolean(projectId && skillName && fromVersion && toVersion),
  });
}

function useProjectSkillMutation<TVariables>(
  mutationFn: (variables: TVariables) => Promise<unknown>,
  projectId: string
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: projectSkillQueryKeys.root(projectId),
      });
    },
  });
}

export function useCreateProjectSkill(projectId: string) {
  return useProjectSkillMutation(
    (document: ProjectSkillDocument) => projectSkillService.create(projectId, document),
    projectId
  );
}

export function useProposeProjectSkillVersion(projectId: string) {
  return useProjectSkillMutation(
    ({ skillName, document }: { skillName: string; document: ProjectSkillDocument }) =>
      projectSkillService.proposeVersion(projectId, skillName, document),
    projectId
  );
}

export function useApproveProjectSkillChange(projectId: string) {
  return useProjectSkillMutation(
    ({ requestId, approval }: { requestId: string; approval: ProjectSkillApproval }) =>
      projectSkillService.approve(projectId, requestId, approval),
    projectId
  );
}

export function useRejectProjectSkillChange(projectId: string) {
  return useProjectSkillMutation(
    ({ requestId, rejection }: { requestId: string; rejection: ProjectSkillRejection }) =>
      projectSkillService.reject(projectId, requestId, rejection),
    projectId
  );
}

export function useRescanProjectSkillChange(projectId: string) {
  return useProjectSkillMutation(
    (requestId: string) => projectSkillService.rescan(projectId, requestId),
    projectId
  );
}

export function useArchiveProjectSkill(projectId: string) {
  return useProjectSkillMutation(
    (skillName: string) => projectSkillService.archive(projectId, skillName),
    projectId
  );
}

export function useRestoreProjectSkill(projectId: string) {
  return useProjectSkillMutation(
    (skillName: string) => projectSkillService.restore(projectId, skillName),
    projectId
  );
}

export function useRollbackProjectSkill(projectId: string) {
  return useProjectSkillMutation(
    ({ skillName, rollback }: { skillName: string; rollback: ProjectSkillRollback }) =>
      projectSkillService.rollback(projectId, skillName, rollback),
    projectId
  );
}
