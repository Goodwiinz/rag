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
        <Loader2 className="h-6 w-6 animate-spin text-[#D4A039]" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-mono font-semibold text-white">
          Export Your Research
        </h3>
        <p className="text-sm text-gray-400 mt-1">
          Export your draft, bibliography, and extraction data in various
          formats.
        </p>
      </div>

      {/* Success banner */}
      <div className="flex items-center gap-3 p-4 bg-[#D4A039]/5 border border-[#D4A039]/20 rounded-lg">
        <CheckCircle className="h-5 w-5 text-[#D4A039] flex-shrink-0" />
        <div>
          <p className="text-sm font-mono text-[#D4A039]">Pipeline Complete</p>
          <p className="text-xs text-gray-400 mt-0.5">
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
          className="flex items-center gap-4 p-4 bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg hover:border-[#D4A039]/30 transition-colors text-left disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <div className="p-3 bg-[#D4A039]/10 rounded-lg">
            <FileText className="h-5 w-5 text-[#D4A039]" />
          </div>
          <div>
            <p className="font-mono text-sm text-white">Export Draft</p>
            <p className="text-xs text-gray-500 mt-1">
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
          className="flex items-center gap-4 p-4 bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg hover:border-[#00d4ff]/30 transition-colors text-left disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <div className="p-3 bg-[#00d4ff]/10 rounded-lg">
            <Download className="h-5 w-5 text-[#00d4ff]" />
          </div>
          <div>
            <p className="font-mono text-sm text-white">Export as LaTeX</p>
            <p className="text-xs text-gray-500 mt-1">
              Full LaTeX document with BibTeX references
            </p>
          </div>
        </button>
      </div>

      {/* Navigation */}
      <div className="flex items-center justify-between pt-4 border-t border-[#1a1a1a]">
        <button
          onClick={onBack}
          className="flex items-center gap-2 px-4 py-2 text-gray-400 hover:text-white font-mono text-sm transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </button>
        <button
          onClick={onReset}
          className="flex items-center gap-2 px-4 py-2 text-gray-400 border border-gray-700 rounded font-mono text-sm hover:text-white hover:border-gray-500 transition-colors"
        >
          <RotateCcw className="h-4 w-4" />
          Start New Pipeline
        </button>
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
