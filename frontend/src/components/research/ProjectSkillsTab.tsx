'use client';

import { useState } from 'react';
import type { ReactElement } from 'react';

import { Button } from '@/components/ui/button';
import {
  useApproveProjectSkillChange,
  useArchiveProjectSkill,
  useCreateProjectSkill,
  useProjectSkill,
  useProjectSkillCatalog,
  useProposeProjectSkillVersion,
  useRejectProjectSkillChange,
  useRescanProjectSkillChange,
  useRestoreProjectSkill,
  useRollbackProjectSkill,
} from '@/hooks/useProjectSkills';
import { useAuthStore } from '@/stores/authStore';
import type { ProjectSkill } from '@/services/projectSkillService';
import { SkillEditor } from './project-skills/SkillEditor';
import { SkillHistory } from './project-skills/SkillHistory';
import { SkillList } from './project-skills/SkillList';
import { SkillReviewPanel } from './project-skills/SkillReviewPanel';

export function ProjectSkillsTab({
  projectId,
}: {
  projectId: string;
}): ReactElement | null {
  const [selectedSkillName, setSelectedSkillName] = useState<string>();
  const [showNewEditor, setShowNewEditor] = useState(false);
  const [operationError, setOperationError] = useState<string>();
  const { user } = useAuthStore();
  const catalog = useProjectSkillCatalog(projectId);
  const detail = useProjectSkill(projectId, selectedSkillName);
  const create = useCreateProjectSkill(projectId);
  const proposeVersion = useProposeProjectSkillVersion(projectId);
  const approve = useApproveProjectSkillChange(projectId);
  const reject = useRejectProjectSkillChange(projectId);
  const rescan = useRescanProjectSkillChange(projectId);
  const archive = useArchiveProjectSkill(projectId);
  const restore = useRestoreProjectSkill(projectId);
  const rollback = useRollbackProjectSkill(projectId);

  if (catalog.isLoading) {
    return (
      <div
        aria-busy="true"
        aria-label="Loading project skills"
        className="h-48 animate-pulse rounded-lg bg-muted"
      />
    );
  }
  if (catalog.isError) {
    return (
      <div
        role="alert"
        className="rounded-lg border border-border p-4 text-sm text-muted-foreground"
      >
        Skills are unavailable for this project.
      </div>
    );
  }
  const data = catalog.data;
  if (!data) return null;
  const selectedSkill = detail.data;
  const selectedRequest = data.pending_change_requests.find(
    (request) =>
      request.skill_name === selectedSkillName && request.status === 'pending'
  );
  const stageArchive = async (skill: ProjectSkill): Promise<void> => {
    try {
      setOperationError(undefined);
      if (skill.is_archived) await restore.mutateAsync(skill.name);
      else await archive.mutateAsync(skill.name);
    } catch (error) {
      setOperationError(
        error instanceof Error
          ? error.message
          : 'The state change could not be staged.'
      );
    }
  };
  const stageRollback = async (versionId: string): Promise<void> => {
    if (!selectedSkill) return;
    try {
      setOperationError(undefined);
      await rollback.mutateAsync({
        skillName: selectedSkill.name,
        rollback: { version_id: versionId },
      });
    } catch (error) {
      setOperationError(
        error instanceof Error
          ? error.message
          : 'The rollback could not be staged.'
      );
    }
  };

  return (
    <section aria-labelledby="project-skills-heading" className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 id="project-skills-heading" className="text-lg font-semibold">
            Project skills
          </h2>
          <p className="text-sm text-muted-foreground">
            Versioned project instructions are activated only after review.
          </p>
        </div>
        {data.capabilities.can_edit && (
          <Button
            onClick={() => {
              setSelectedSkillName(undefined);
              setShowNewEditor(true);
            }}
          >
            New skill
          </Button>
        )}
      </div>
      {operationError && (
        <p role="alert" className="text-sm text-destructive">
          {operationError}
        </p>
      )}
      <SkillList
        skills={data.skills}
        pendingRequests={data.pending_change_requests}
        selectedSkillName={selectedSkillName}
        canEdit={data.capabilities.can_edit}
        onReview={setSelectedSkillName}
        onStageArchive={(skill): void => void stageArchive(skill)}
      />
      {data.capabilities.can_edit && (showNewEditor || selectedSkill) && (
        <SkillEditor
          key={selectedSkill?.name ?? 'new-skill'}
          skillName={selectedSkill?.name}
          initialDocument={selectedSkill?.active_version?.document_text}
          isSubmitting={
            selectedSkill ? proposeVersion.isPending : create.isPending
          }
          onSubmit={async (documentText): Promise<void> => {
            try {
              setOperationError(undefined);
              if (selectedSkill) {
                await proposeVersion.mutateAsync({
                  skillName: selectedSkill.name,
                  document: { document_text: documentText },
                });
              } else {
                await create.mutateAsync({ document_text: documentText });
              }
              setShowNewEditor(false);
            } catch (error) {
              setOperationError(
                error instanceof Error
                  ? error.message
                  : 'The proposal could not be created.'
              );
            }
          }}
        />
      )}
      {selectedSkillName && detail.isLoading && (
        <div
          aria-busy="true"
          aria-label="Loading skill details"
          className="h-32 animate-pulse rounded-lg bg-muted"
        />
      )}
      {selectedSkill && (
        <div className="grid gap-4 lg:grid-cols-2">
          <SkillHistory
            skill={selectedSkill}
            versions={selectedSkill.versions ?? []}
            canEdit={data.capabilities.can_edit}
            isRollingBack={rollback.isPending}
            onRollback={(versionId): void => void stageRollback(versionId)}
          />
          {data.capabilities.can_admin && (
            <SkillReviewPanel
              projectId={projectId}
              skill={selectedSkill}
              request={selectedRequest}
              currentUserId={user?.id}
              isApproving={approve.isPending}
              onApprove={(requestId, approval): Promise<unknown> =>
                approve.mutateAsync({ requestId, approval })
              }
              onReject={(requestId, auditNote): Promise<unknown> =>
                reject.mutateAsync({
                  requestId,
                  rejection: { audit_note: auditNote },
                })
              }
              onRescan={(requestId): Promise<unknown> =>
                rescan.mutateAsync(requestId)
              }
              onStale={(): void => {
                void catalog.refetch();
                void detail.refetch();
              }}
            />
          )}
        </div>
      )}
    </section>
  );
}
