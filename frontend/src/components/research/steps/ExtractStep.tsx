'use client';

/**
 * ExtractStep - Step 2 of the Research Pipeline (Optional/Skippable)
 * Wraps ExtractionMatrix with Skip + Continue navigation.
 * Completion criteria: matrix created + >= 1 row extracted, or skipped.
 */

import React from 'react';
import { ArrowRight, ArrowLeft, SkipForward, Grid3X3 } from 'lucide-react';
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
          <h3 className="text-lg font-mono font-semibold text-white">
            Extract Data
          </h3>
          <p className="text-sm text-gray-400 mt-1">
            Create an extraction matrix to systematically extract data from your
            documents. You can skip this step if not needed.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Grid3X3 className="h-4 w-4 text-[#00d4ff]" />
          <span className="text-xs font-mono text-gray-500 bg-[#00d4ff]/10 px-2 py-0.5 rounded border border-[#00d4ff]/20">
            Optional
          </span>
        </div>
      </div>

      <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg p-4">
        <ExtractionMatrix
          projectId={projectId}
          documents={documents.map((doc) => ({
            id: doc.document_id,
            title: doc.document?.title || doc.document?.filename || 'Untitled',
          }))}
        />
      </div>

      <div className="flex items-center justify-between pt-4 border-t border-[#1a1a1a]">
        <button
          onClick={onBack}
          className="flex items-center gap-2 px-4 py-2 text-gray-400 hover:text-white font-mono text-sm transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </button>
        <div className="flex items-center gap-3">
          <button
            onClick={onSkip}
            className="flex items-center gap-2 px-4 py-2 text-gray-400 border border-gray-700 rounded font-mono text-sm hover:text-white hover:border-gray-500 transition-colors"
          >
            <SkipForward className="h-4 w-4" />
            Skip
          </button>
          <button
            onClick={onContinue}
            className="flex items-center gap-2 px-5 py-2.5 bg-[#D4A039]/10 text-[#D4A039] border border-[#D4A039]/30 rounded font-mono text-sm hover:bg-[#D4A039]/20 transition-colors"
          >
            Continue
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
};
