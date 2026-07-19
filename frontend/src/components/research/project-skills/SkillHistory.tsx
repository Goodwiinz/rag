import { RotateCcw } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type { ProjectSkill, ProjectSkillVersion } from '@/services/projectSkillService';

interface SkillHistoryProps {
  skill: ProjectSkill;
  versions: ProjectSkillVersion[];
  onRollback: (versionId: string) => void;
  canEdit: boolean;
  isRollingBack?: boolean;
}

function scanVariant(scanState: string): 'success' | 'destructive' | 'warning' | 'outline' {
  if (scanState === 'passed') return 'success';
  if (scanState === 'blocked') return 'destructive';
  if (scanState === 'pending') return 'outline';
  return 'warning';
}

export function SkillHistory({ skill, versions, onRollback, canEdit, isRollingBack }: SkillHistoryProps) {
  return (
    <section aria-labelledby="skill-history-heading" className="rounded-lg border border-border bg-card p-4">
      <h2 id="skill-history-heading" className="font-medium">Version history</h2>
      <ol className="mt-3 divide-y divide-border">
        {versions.map((version) => {
          const isActive = skill.active_version_id === version.id;
          return (
            <li key={version.id} className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">Version {version.version}</span>
                  {isActive && <Badge variant="secondary">Active</Badge>}
                  <Badge variant={scanVariant(version.scan_state)}>{version.scan_state}</Badge>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{version.description}</p>
              </div>
              {canEdit && !isActive && (
                <Button
                  variant="outline"
                  size="sm"
                  isLoading={isRollingBack}
                  onClick={() => onRollback(version.id)}
                >
                  <RotateCcw aria-hidden="true" />
                  Stage rollback to v{version.version}
                </Button>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
