'use client';

/**
 * ResearchPipeline Component
 * Main container that orchestrates the step-by-step research wizard.
 * Connects PipelineStepper + step components + pipelineStore.
 */

import React, { useEffect, useRef } from 'react';
import { Loader2, RotateCcw } from 'lucide-react';
import { usePipelineStore } from '@/store/pipelineStore';
import { useProjectStore } from '@/store/projectStore';
import { PipelineStepper } from './PipelineStepper';
import { CollectStep } from './steps/CollectStep';
import { ExtractStep } from './steps/ExtractStep';
import { CiteStep } from './steps/CiteStep';
import { DraftStep } from './steps/DraftStep';
import { ExportStep } from './steps/ExportStep';

interface ResearchPipelineProps {
  projectId: string;
}

export const ResearchPipeline: React.FC<ResearchPipelineProps> = ({
  projectId,
}) => {
  const {
    pipeline,
    loading,
    error,
    fetchPipeline,
    advanceStep,
    skipStep,
    goToStep,
    resetPipeline,
    clearError,
  } = usePipelineStore();

  const projectDocuments = useProjectStore((s) => s.projectDocuments);
  const documentsLoading = useProjectStore((s) => s.documentsLoading);
  const removeDocument = useProjectStore((s) => s.removeDocument);

  const fetchedRef = useRef(false);
  useEffect(() => {
    if (fetchedRef.current) return;
    fetchedRef.current = true;
    fetchPipeline(projectId);
  }, [projectId, fetchPipeline]);

  if (loading || !pipeline) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-6 w-6 animate-spin text-sol" />
      </div>
    );
  }

  const handleRemoveDocument = async (documentId: string) => {
    if (!confirm('Remove this document from the project?')) return;
    try {
      await removeDocument(projectId, documentId);
    } catch (err) {
      console.error('Failed to remove document:', err);
    }
  };

  const handleAdvance = () => void advanceStep(projectId);
  const handleSkip = () => void skipStep(projectId);
  const handleGoToStep = (step: number) => void goToStep(projectId, step);
  const handleReset = () => void resetPipeline(projectId);
  const handleBack = () => {
    const prev = Math.max(0, pipeline.current_step - 1);
    void goToStep(projectId, prev);
  };

  return (
    <div className="space-y-2">
      {/* Error banner */}
      {error && (
        <div className="flex items-center justify-between p-3 bg-red-500/10 border border-red-500/30 rounded-lg mb-4">
          <p className="text-red-400 font-mono text-sm">{error}</p>
          <button
            onClick={clearError}
            className="text-xs text-red-400 underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Stepper */}
      <PipelineStepper
        currentStep={pipeline.current_step}
        completedSteps={pipeline.completed_steps}
        skippedSteps={pipeline.skipped_steps}
        invalidatedSteps={pipeline.invalidated_steps}
        onStepClick={handleGoToStep}
      />

      {/* Reset button */}
      {(pipeline.completed_steps.length > 0 ||
        pipeline.skipped_steps.length > 0) && (
        <div className="flex justify-end mb-2">
          <button
            onClick={handleReset}
            className="flex items-center gap-1.5 px-3 py-1 text-gray-500 hover:text-gray-300 font-mono text-xs transition-colors"
          >
            <RotateCcw className="h-3 w-3" />
            Reset Pipeline
          </button>
        </div>
      )}

      {/* Active step content */}
      <div className="bg-[#111] border border-[#1a1a1a] rounded-lg p-6">
        {pipeline.current_step === 0 && (
          <CollectStep
            projectId={projectId}
            documents={projectDocuments}
            documentsLoading={documentsLoading}
            onRemoveDocument={(docId) => {
              void handleRemoveDocument(docId);
            }}
            onContinue={handleAdvance}
          />
        )}

        {pipeline.current_step === 1 && (
          <ExtractStep
            projectId={projectId}
            documents={projectDocuments}
            onContinue={handleAdvance}
            onSkip={handleSkip}
            onBack={handleBack}
          />
        )}

        {pipeline.current_step === 2 && (
          <CiteStep
            projectId={projectId}
            onContinue={handleAdvance}
            onBack={handleBack}
          />
        )}

        {pipeline.current_step === 3 && (
          <DraftStep
            projectId={projectId}
            documentCount={projectDocuments.length}
            onContinue={handleAdvance}
            onBack={handleBack}
          />
        )}

        {pipeline.current_step === 4 && (
          <ExportStep
            projectId={projectId}
            onBack={handleBack}
            onReset={handleReset}
          />
        )}
      </div>
    </div>
  );
};
