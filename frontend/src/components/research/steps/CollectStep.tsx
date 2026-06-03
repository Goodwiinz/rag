'use client';

/**
 * CollectStep - Step 1 of the Research Pipeline
 * Displays project documents with a "Continue" button.
 * Completion criteria: >= 1 document in project.
 */

import React from 'react';
import { FileText, Trash2, ArrowRight, Loader2 } from 'lucide-react';
import type { ProjectDocument } from '@/services/projectService';

interface CollectStepProps {
  projectId: string;
  documents: ProjectDocument[];
  documentsLoading: boolean;
  onRemoveDocument: (documentId: string) => void;
  onContinue: () => void;
}

export const CollectStep: React.FC<CollectStepProps> = ({
  documents,
  documentsLoading,
  onRemoveDocument,
  onContinue,
}) => {
  const canContinue = documents.length > 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-mono font-semibold text-white">
            Collect Documents
          </h3>
          <p className="text-sm text-muted-foreground mt-1">
            Add documents to your project from the Documents page, then continue
            to the next step.
          </p>
        </div>
        <span className="text-sm font-mono text-muted-foreground">
          {documents.length} document{documents.length !== 1 ? 's' : ''}
        </span>
      </div>

      {documentsLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-sol" />
        </div>
      ) : documents.length === 0 ? (
        <div className="text-center py-12 bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg">
          <FileText className="h-12 w-12 text-foreground mx-auto mb-4" />
          <p className="text-muted-foreground font-mono">
            No documents in this project
          </p>
          <p className="text-sm text-muted-foreground mt-2">
            Add documents from the Documents page to get started
          </p>
        </div>
      ) : (
        <div className="space-y-2 max-h-[400px] overflow-y-auto">
          {documents.map((doc) => (
            <div
              key={doc.id}
              className="flex items-center justify-between p-3 bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg hover:border-[#333] transition-colors"
            >
              <div className="flex items-center gap-3">
                <FileText className="h-4 w-4 text-sol" />
                <div>
                  <p className="font-mono text-sm text-muted-foreground">
                    {doc.document?.title ||
                      doc.document?.filename ||
                      'Untitled'}
                  </p>
                  <p className="text-xs text-muted-foreground font-mono">
                    Added{' '}
                    {new Date(
                      doc.added_at || doc.document?.created_at || Date.now()
                    ).toLocaleDateString()}
                  </p>
                </div>
              </div>
              <button
                onClick={() => onRemoveDocument(doc.document_id)}
                className="p-1.5 text-muted-foreground hover:text-red-400 transition-colors"
                title="Remove from project"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="flex justify-end pt-4 border-t border-[#1a1a1a]">
        <button
          onClick={onContinue}
          disabled={!canContinue}
          className="flex items-center gap-2 px-5 py-2.5 bg-sol/10 text-sol border border-sol/30 rounded font-mono text-sm hover:bg-sol/20 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
        >
          Continue
          <ArrowRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
};
