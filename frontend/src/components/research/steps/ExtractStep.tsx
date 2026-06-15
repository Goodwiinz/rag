'use client';

/**
 * ExtractStep - Step 2 of the Research Pipeline (Optional/Skippable)
 * Wraps ExtractionMatrix with Skip + Continue navigation.
 * Completion criteria: matrix created + >= 1 row extracted, or skipped.
 */

import React from 'react';
import { ArrowRight, ArrowLeft, SkipForward, Grid3X3 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ExtractionMatrix } from '@/components/research/ExtractionMatrix';
import type { ProjectDocument } from '@/services/projectService';

interface ExtractStepProps {
  projectId: string;
  documents: ProjectDocument[];
  onContinue: () => void;
  onSkip: () => void;
  onBack: () => void;
}

export const ExtractStep: React.FC<ExtractStepProps> = ({
  projectId,
  documents,
  onContinue,
  onSkip,
  onBack,
}) => {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-foreground">
            Extract data
          </h3>
          <p className="text-sm text-muted-foreground mt-1">
            Create an extraction matrix to systematically extract data from your
            documents. You can skip this step if not needed.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Grid3X3 className="h-4 w-4 text-primary" />
          <span className="text-xs text-muted-foreground bg-primary/10 px-2 py-0.5 rounded border border-primary/20">
            Optional
          </span>
        </div>
      </div>

      <div className="bg-card border border-border rounded-lg p-4">
        <ExtractionMatrix
          projectId={projectId}
          documents={documents.map((doc) => ({
            id: doc.document_id,
            title: doc.document?.title || doc.document?.filename || 'Untitled',
          }))}
        />
      </div>

      <div className="flex items-center justify-between pt-4 border-t border-border">
        <Button variant="ghost" onClick={onBack}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back
        </Button>
        <div className="flex items-center gap-3">
          <Button variant="outline" onClick={onSkip}>
            <SkipForward className="h-4 w-4 mr-2" />
            Skip
          </Button>
          <Button onClick={onContinue}>
            Continue
            <ArrowRight className="h-4 w-4 ml-2" />
          </Button>
        </div>
      </div>
    </div>
  );
};
