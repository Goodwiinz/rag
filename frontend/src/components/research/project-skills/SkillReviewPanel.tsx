import { useMemo, useState } from 'react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Textarea } from '@/components/ui/textarea';
import { useProjectSkillDiff } from '@/hooks/useProjectSkills';
import type {
  ProjectSkill,
  ProjectSkillChangeRequest,
  ProjectSkillVersion,
} from '@/services/projectSkillService';

interface SkillReviewPanelProps {
  projectId: string;
  skill: ProjectSkill;
  request?: ProjectSkillChangeRequest;
  currentUserId?: string;
  onApprove: (requestId: string, approval: { self_approval_acknowledged: boolean; warning_acknowledged: boolean; audit_note: string | null }) => Promise<unknown>;
  onReject: (requestId: string, auditNote: string) => Promise<unknown>;
  onRescan: (requestId: string) => Promise<unknown>;
  isApproving?: boolean;
}

function findingVersions(skill: ProjectSkill): ProjectSkillVersion[] {
  return skill.versions ?? (skill.active_version ? [skill.active_version] : []);
}

function errorStatus(error: unknown): number | undefined {
  if (!error || typeof error !== 'object') return undefined;
  const nested = (error as { error?: { status_code?: number } }).error;
  return nested?.status_code;
}

export function SkillReviewPanel({
  projectId,
  skill,
  request,
  currentUserId,
  onApprove,
  onReject,
  onRescan,
  isApproving,
}: SkillReviewPanelProps) {
  const [warningAcknowledged, setWarningAcknowledged] = useState(false);
  const [selfApprovalAcknowledged, setSelfApprovalAcknowledged] = useState(false);
  const [note, setNote] = useState('');
  const [message, setMessage] = useState<string>();
  const versions = useMemo(
    () => [...findingVersions(skill)].sort((a, b) => b.version - a.version),
    [skill]
  );
  const activeVersion = skill.active_version;
  const proposedVersion = versions.find((version) => version.id === request?.proposed_version_id) ?? versions[0];
  const findings = versions.flatMap((version) => version.scan_findings);
  const blockers = findings.filter((finding) => finding.severity === 'blocker');
  const warnings = findings.filter((finding) => finding.severity === 'warning');
  const isSelfApproval = Boolean(request && currentUserId === request.requester_id);
  const requiresNote = warnings.length > 0 || isSelfApproval;
  const diff = useProjectSkillDiff(
    projectId,
    skill.name,
    activeVersion?.version,
    proposedVersion?.version
  );
  const canApprove = Boolean(
    request &&
      blockers.length === 0 &&
      (!warnings.length || warningAcknowledged) &&
      (!isSelfApproval || selfApprovalAcknowledged) &&
      (!requiresNote || note.trim())
  );

  if (!request) {
    return <p className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">No pending review for this skill.</p>;
  }

  const approve = async () => {
    setMessage(undefined);
    try {
      await onApprove(request.id, {
        self_approval_acknowledged: selfApprovalAcknowledged,
        warning_acknowledged: warningAcknowledged,
        audit_note: note.trim() || null,
      });
      setMessage('Approval recorded. The catalog has been refreshed.');
    } catch (error) {
      setMessage(errorStatus(error) === 409
        ? 'This request was superseded by a newer change. The catalog has been refreshed.'
        : 'The approval could not be completed. Review the latest catalog and try again.');
    }
  };

  return (
    <section aria-labelledby="skill-review-heading" className="space-y-4 rounded-lg border border-border bg-card p-4">
      <div>
        <h2 id="skill-review-heading" className="font-medium">Review pending change</h2>
        <p className="mt-1 text-sm text-muted-foreground">{request.action} requested for {skill.name}</p>
      </div>
      {findings.length > 0 && (
        <div className="space-y-2" aria-label="Scanner findings">
          {findings.map((finding) => (
            <Alert key={`${finding.code}-${finding.line ?? 0}`} variant={finding.severity === 'blocker' ? 'destructive' : 'default'}>
              <AlertTitle>{finding.severity === 'blocker' ? 'Blocker' : 'Warning'}: {finding.code}</AlertTitle>
              <AlertDescription>{finding.message}{finding.line ? ` (line ${finding.line})` : ''}</AlertDescription>
            </Alert>
          ))}
        </div>
      )}
      {diff.isLoading && <div aria-busy="true" aria-label="Loading canonical diff" className="h-24 animate-pulse rounded bg-muted" />}
      {diff.data && <pre aria-label="Canonical diff" className="max-h-64 overflow-auto rounded-md bg-muted p-3 text-xs">{diff.data.diff || 'No textual changes.'}</pre>}
      {warnings.length > 0 && (
        <label className="flex items-start gap-2 text-sm">
          <Checkbox checked={warningAcknowledged} onCheckedChange={(checked) => setWarningAcknowledged(checked === true)} />
          I acknowledge the scanner warnings and have recorded why this change is safe.
        </label>
      )}
      {isSelfApproval && (
        <label className="flex items-start gap-2 text-sm">
          <Checkbox checked={selfApprovalAcknowledged} onCheckedChange={(checked) => setSelfApprovalAcknowledged(checked === true)} />
          I acknowledge this is a self-approval and include an audit note.
        </label>
      )}
      {(requiresNote || blockers.length > 0) && (
        <>
          <label htmlFor="review-audit-note" className="block text-sm font-medium">Audit note</label>
          <Textarea id="review-audit-note" value={note} onChange={(event) => setNote(event.target.value)} />
        </>
      )}
      {message && <p role="status" className="text-sm text-muted-foreground">{message}</p>}
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" size="sm" onClick={() => void onRescan(request.id)}>Rescan</Button>
        <Button variant="outline" size="sm" disabled={!note.trim()} onClick={() => void onReject(request.id, note.trim())}>Reject</Button>
        <Button disabled={!canApprove} isLoading={isApproving} onClick={() => void approve()}>Approve</Button>
      </div>
    </section>
  );
}
