'use client';

/**
 * CiteStep - Step 3 of the Research Pipeline
 * Displays citations from the project's bibliography.
 * Completion criteria: >= 1 citation exists.
 */

import React, { useEffect, useState } from 'react';
import {
  ArrowRight,
  ArrowLeft,
  BookOpen,
  Loader2,
  Download,
} from 'lucide-react';
import { useProjectStore } from '@/store/projectStore';

interface CiteStepProps {
  projectId: string;
  onContinue: () => void;
  onBack: () => void;
}

export const CiteStep: React.FC<CiteStepProps> = ({
  projectId,
  onContinue,
  onBack,
}) => {
  const bibliography = useProjectStore((s) => s.bibliography);
  const loading = useProjectStore((s) => s.loading);
  const fetchBibliography = useProjectStore((s) => s.fetchBibliography);
  const downloadBibliography = useProjectStore((s) => s.downloadBibliography);
  const [bibFormat, setBibFormat] = useState<'bibtex' | 'ieee' | 'apa' | 'mla'>(
    'bibtex'
  );
  useEffect(() => {
    fetchBibliography(projectId, bibFormat);
    // Only re-fetch when projectId or bibFormat changes, not when the
    // store function reference changes (which would cause an infinite loop).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, bibFormat]);

  const hasCitations = (bibliography?.citation_count ?? 0) > 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-mono font-semibold text-white">
            Manage Citations
          </h3>
          <p className="text-sm text-muted-foreground mt-1">
            Review and manage citations extracted from your documents. At least
            one citation is needed to continue.
          </p>
        </div>
      </div>

      {/* Format selector + download */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground font-mono">
            Format:
          </span>
          <select
            value={bibFormat}
            onChange={(e) => {
              const format = e.target.value as typeof bibFormat;
              setBibFormat(format);
            }}
            className="px-3 py-1.5 bg-[#1a1a1a] border border-[#333] rounded text-sm font-mono text-muted-foreground focus:outline-none focus:border-sol"
          >
            <option value="bibtex">BibTeX</option>
            <option value="ieee">IEEE</option>
            <option value="apa">APA</option>
            <option value="mla">MLA</option>
          </select>
        </div>
        <button
          onClick={() => {
            void downloadBibliography(projectId, bibFormat);
          }}
          disabled={!hasCitations}
          className="flex items-center gap-2 px-4 py-2 bg-sol/10 text-sol border border-sol/30 rounded font-mono text-sm hover:bg-sol/20 transition-colors disabled:opacity-50"
        >
          <Download className="h-4 w-4" />
          Download
        </button>
      </div>

      {/* Bibliography content */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-sol" />
        </div>
      ) : bibliography ? (
        <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm text-muted-foreground font-mono">
              {bibliography.citation_count} citation
              {bibliography.citation_count !== 1 ? 's' : ''}
            </span>
            <span className="text-xs text-foreground font-mono">
              Generated {new Date(bibliography.generated_at).toLocaleString()}
            </span>
          </div>
          <pre className="text-sm text-muted-foreground font-mono overflow-x-auto whitespace-pre-wrap max-h-[350px] overflow-y-auto">
            {bibliography.content}
          </pre>
        </div>
      ) : (
        <div className="text-center py-12 bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg">
          <BookOpen className="h-12 w-12 text-foreground mx-auto mb-4" />
          <p className="text-muted-foreground font-mono">
            No citations available
          </p>
          <p className="text-sm text-muted-foreground mt-2">
            Citations are automatically extracted from your project documents
          </p>
        </div>
      )}

      <div className="flex items-center justify-between pt-4 border-t border-[#1a1a1a]">
        <button
          onClick={onBack}
          className="flex items-center gap-2 px-4 py-2 text-muted-foreground hover:text-white font-mono text-sm transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </button>
        <button
          onClick={onContinue}
          disabled={!hasCitations}
          className="flex items-center gap-2 px-5 py-2.5 bg-sol/10 text-sol border border-sol/30 rounded font-mono text-sm hover:bg-sol/20 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
        >
          Continue
          <ArrowRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
};
