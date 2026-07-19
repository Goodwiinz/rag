import { useState } from 'react';
import type { ReactElement } from 'react';

import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';

interface SkillEditorProps {
  skillName?: string;
  initialDocument?: string;
  isSubmitting?: boolean;
  onSubmit: (documentText: string) => Promise<unknown>;
}

export function SkillEditor({
  skillName,
  initialDocument = '',
  isSubmitting,
  onSubmit,
}: SkillEditorProps): ReactElement {
  const [documentText, setDocumentText] = useState(initialDocument);

  const submitLabel = skillName
    ? `Propose update to ${skillName}`
    : 'Propose skill';
  return (
    <section
      aria-labelledby="skill-editor-heading"
      className="rounded-lg border border-border bg-card p-4"
    >
      <div className="flex items-baseline justify-between gap-3">
        <h2 id="skill-editor-heading" className="font-medium">
          {skillName
            ? `Propose a new version of ${skillName}`
            : 'New project skill'}
        </h2>
        <span className="text-xs text-muted-foreground">SKILL.md only</span>
      </div>
      <label
        htmlFor="skill-document"
        className="mt-3 block text-sm font-medium"
      >
        Skill document
      </label>
      <Textarea
        id="skill-document"
        value={documentText}
        onChange={(event) => setDocumentText(event.target.value)}
        placeholder={
          '---\nname: research-summary\ndescription: Create cited source summaries\n---\n\nInstructions…'
        }
        className="mt-2 min-h-48 font-mono text-sm"
      />
      <div className="mt-3 flex justify-end">
        <Button
          isLoading={isSubmitting}
          disabled={!documentText.trim()}
          onClick={() => void onSubmit(documentText)}
        >
          {submitLabel}
        </Button>
      </div>
    </section>
  );
}
