import { Archive, FilePenLine, History } from 'lucide-react';
import type { ReactElement } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type {
  ProjectSkill,
  ProjectSkillChangeRequest,
} from '@/services/projectSkillService';

interface SkillListProps {
  skills: ProjectSkill[];
  pendingRequests: ProjectSkillChangeRequest[];
  selectedSkillName?: string;
  canEdit: boolean;
  onReview: (skillName: string) => void;
  onStageArchive: (skill: ProjectSkill) => void;
}

export function SkillList({
  skills,
  pendingRequests,
  selectedSkillName,
  canEdit,
  onReview,
  onStageArchive,
}: SkillListProps): ReactElement {
  if (skills.length === 0) {
    return (
      <div
        role="status"
        className="rounded-lg border border-dashed border-border p-8 text-center"
      >
        <h2 className="text-base font-semibold">No project skills yet</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Add instructions your project agents can use after an administrator
          approves them.
        </p>
      </div>
    );
  }

  return (
    <ul aria-label="Project skills" className="space-y-2">
      {skills.map((skill) => {
        const pending = pendingRequests.some(
          (request) =>
            request.skill_name === skill.name && request.status === 'pending'
        );
        const activeVersion = skill.active_version;
        return (
          <li
            key={skill.id}
            className="rounded-lg border border-border bg-card p-4"
          >
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="font-medium text-foreground">{skill.name}</h2>
                  {activeVersion && (
                    <Badge variant="secondary">
                      Active v{activeVersion.version}
                    </Badge>
                  )}
                  {pending && <Badge variant="warning">Pending approval</Badge>}
                  {skill.is_archived && (
                    <Badge variant="outline">Archived</Badge>
                  )}
                </div>
                <p className="mt-1 text-sm text-muted-foreground">
                  {activeVersion?.description ?? 'No active version'}
                </p>
                {activeVersion && (
                  <Badge
                    variant={
                      activeVersion.scan_state === 'passed'
                        ? 'success'
                        : activeVersion.scan_state === 'blocked'
                          ? 'destructive'
                          : 'warning'
                    }
                  >
                    Scan: {activeVersion.scan_state}
                  </Badge>
                )}
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onReview(skill.name)}
                  aria-pressed={selectedSkillName === skill.name}
                >
                  <History aria-hidden="true" />
                  Review {skill.name}
                </Button>
                {canEdit && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onStageArchive(skill)}
                  >
                    {skill.is_archived ? (
                      <FilePenLine aria-hidden="true" />
                    ) : (
                      <Archive aria-hidden="true" />
                    )}
                    {skill.is_archived ? 'Stage restore' : 'Stage archive'}
                  </Button>
                )}
              </div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
