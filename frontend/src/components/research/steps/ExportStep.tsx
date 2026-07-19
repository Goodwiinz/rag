'use client';

/**
 * ExportStep - Step 5 (Terminal) of the Research Pipeline
 * Multi-format export: draft + CSV + bibliography.
 * Available once Draft step is complete.
 */

import React, { useCallback, useEffect, useState } from 'react';
import {
  ArrowLeft,
  Download,
  FileText,
  RotateCcw,
  CheckCircle,
  Loader2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { DraftExportModal } from '@/components/research/DraftExportModal';
import { projectService, type Draft } from '@/services/projectService';

interface ExportStepProps {
  projectId: string;
  onBack: () => void;
  onReset: () => void;
}

export const ExportStep: React.FC<ExportStepProps> = ({
  projectId,
  onBack,
  onReset,
}) => {
  const [currentDraft, setCurrentDraft] = useState<Draft | null>(null);
  const [loading, setLoading] = useState(true);
  const [showExportModal, setShowExportModal] = useState(false);
  const [exportInitialFormat, setExportInitialFormat] = useState<
    'markdown' | 'latex'
  >('markdown');

  const loadLatestDraft = useCallback(async () => {
    setLoading(true);
    try {
      const response = await projectService.listDrafts(projectId, {
        limit: 1,
      });
      if (response.drafts.length > 0) {
        const draft = await projectService.getDraft(
          projectId,
          response.drafts[0].id
        );
        setCurrentDraft(draft);
      }
    } catch (err) {
      console.error('Failed to load draft:', err);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void loadLatestDraft();
  }, [loadLatestDraft]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-foreground">
          Export your research
        </h3>
        <p className="text-sm text-muted-foreground mt-1">
          Export your draft, bibliography, and extraction data in various
          formats.
        </p>
      </div>

      {/* Success banner */}
      <div className="flex items-center gap-3 p-4 bg-primary/5 border border-primary/20 rounded-lg">
        <CheckCircle className="h-5 w-5 text-primary flex-shrink-0" />
        <div>
          <p className="text-sm font-medium text-primary">Pipeline complete</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            Your research workflow is finished. Choose your export format below.
          </p>
        </div>
      </div>

      {/* Export options */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Draft export */}
        <button
          onClick={() => {
            setExportInitialFormat('markdown');
            setShowExportModal(true);
          }}
          disabled={!currentDraft}
          className="flex items-center gap-4 p-4 bg-card border border-border rounded-lg hover:border-primary/30 transition-colors text-left disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <div className="p-3 bg-primary/10 rounded-lg">
            <FileText className="h-5 w-5 text-primary" />
          </div>
          <div>
            <p className="text-sm text-foreground">Export draft</p>
            <p className="text-xs text-muted-foreground mt-1">
              Markdown or LaTeX with optional bibliography
            </p>
          </div>
        </button>

        {/* LaTeX export */}
        <button
          onClick={() => {
            setExportInitialFormat('latex');
            setShowExportModal(true);
          }}
          disabled={!currentDraft}
          className="flex items-center gap-4 p-4 bg-card border border-border rounded-lg hover:border-primary/30 transition-colors text-left disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <div className="p-3 bg-primary/10 rounded-lg">
            <Download className="h-5 w-5 text-primary" />
          </div>
          <div>
            <p className="text-sm text-foreground">Export as LaTeX</p>
            <p className="text-xs text-muted-foreground mt-1">
              Full LaTeX document with BibTeX references
            </p>
          </div>
        </button>
      </div>

      {/* Navigation */}
      <div className="flex items-center justify-between pt-4 border-t border-border">
        <Button variant="ghost" onClick={onBack}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back
        </Button>
        <Button variant="outline" onClick={onReset}>
          <RotateCcw className="h-4 w-4 mr-2" />
          Start new pipeline
        </Button>
      </div>

      {currentDraft && (
        <DraftExportModal
          isOpen={showExportModal}
          onClose={() => setShowExportModal(false)}
          draftTitle={currentDraft.title}
          initialFormat={exportInitialFormat}
          onExport={async (format, includeBibliography, bibliographyFormat) => {
            await projectService.downloadDraftExport(
              projectId,
              currentDraft.id,
              format,
              includeBibliography,
              bibliographyFormat
            );
          }}
        />
      )}
    </div>
  );
};
