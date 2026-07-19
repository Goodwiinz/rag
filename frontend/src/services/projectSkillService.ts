import { api } from '@/services/api-client';
import type { components } from '@/types/generated/api';

export type ProjectSkillCatalog =
  components['schemas']['ProjectSkillCatalogResponse'];
export type ProjectSkill = components['schemas']['SkillResponse'];
export type ProjectSkillVersion = components['schemas']['SkillVersionResponse'];
export type ProjectSkillDiff = components['schemas']['SkillDiffResponse'];
export type ProjectSkillChangeRequest =
  components['schemas']['ChangeRequestResponse'];
export type ProjectSkillDocument =
  components['schemas']['SkillDocumentRequest'];
export type ProjectSkillApproval = components['schemas']['ApprovalRequest'];
export type ProjectSkillRejection = components['schemas']['RejectRequest'];
export type ProjectSkillRollback = components['schemas']['RollbackRequest'];

const path = (projectId: string): string => `/projects/${projectId}/skills`;

export const projectSkillService = {
  list: (projectId: string) => api.get<ProjectSkillCatalog>(path(projectId)),
  get: (projectId: string, skillName: string) =>
    api.get<ProjectSkill>(
      `${path(projectId)}/${encodeURIComponent(skillName)}`
    ),
  getDiff: (
    projectId: string,
    skillName: string,
    fromVersion: number,
    toVersion: number
  ) =>
    api.get<ProjectSkillDiff>(
      `${path(projectId)}/${encodeURIComponent(skillName)}/diff?from_version=${fromVersion}&to_version=${toVersion}`
    ),
  create: (projectId: string, document: ProjectSkillDocument) =>
    api.post<ProjectSkillChangeRequest>(path(projectId), document),
  proposeVersion: (
    projectId: string,
    skillName: string,
    document: ProjectSkillDocument
  ) =>
    api.post<ProjectSkillChangeRequest>(
      `${path(projectId)}/${encodeURIComponent(skillName)}/versions`,
      document
    ),
  approve: (
    projectId: string,
    requestId: string,
    approval: ProjectSkillApproval
  ) =>
    api.post<ProjectSkillChangeRequest>(
      `${path(projectId)}/change-requests/${requestId}/approve`,
      approval
    ),
  reject: (
    projectId: string,
    requestId: string,
    rejection: ProjectSkillRejection
  ) =>
    api.post<ProjectSkillChangeRequest>(
      `${path(projectId)}/change-requests/${requestId}/reject`,
      rejection
    ),
  rescan: (projectId: string, requestId: string) =>
    api.post<ProjectSkillVersion>(
      `${path(projectId)}/change-requests/${requestId}/rescan`
    ),
  archive: (projectId: string, skillName: string) =>
    api.post<ProjectSkillChangeRequest>(
      `${path(projectId)}/${encodeURIComponent(skillName)}/archive`
    ),
  restore: (projectId: string, skillName: string) =>
    api.post<ProjectSkillChangeRequest>(
      `${path(projectId)}/${encodeURIComponent(skillName)}/restore`
    ),
  rollback: (
    projectId: string,
    skillName: string,
    rollback: ProjectSkillRollback
  ) =>
    api.post<ProjectSkillChangeRequest>(
      `${path(projectId)}/${encodeURIComponent(skillName)}/rollback`,
      rollback
    ),
};
