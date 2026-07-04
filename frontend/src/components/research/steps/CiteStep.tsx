'use client';

import React, { useEffect, useState } from 'react';
import {
  ArrowRight,
  ArrowLeft,
  BookOpen,
  Loader2,
  Download,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, bibFormat]);

  const hasCitations = (bibliography?.citation_count ?? 0) > 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-foreground">
            Manage citations
          </h3>
          <p className="text-sm text-muted-foreground mt-1">
            Review and manage citations extracted from your documents. At least
            one citation is needed to continue.
          </p>
        </div>
      </div>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Format:</span>
          <select
            value={bibFormat}
            onChange={(e) => {
              const format = e.target.value as typeof bibFormat;
              setBibFormat(format);
            }}
            className="px-3 py-1.5 bg-background border border-border rounded text-sm text-foreground focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring"
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
          className="flex items-center gap-2 px-4 py-2 bg-primary/10 text-primary border border-primary/30 rounded text-sm hover:bg-primary/20 transition-colors disabled:opacity-50"
        >
          <Download className="h-4 w-4" />
          Download
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </div>
      ) : bibliography ? (
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm text-muted-foreground">
              {bibliography.citation_count} citation
              {bibliography.citation_count !== 1 ? 's' : ''}
            </span>
            <span className="text-xs text-muted-foreground">
              Generated {new Date(bibliography.generated_at).toLocaleString()}
            </span>
          </div>
          <pre className="text-sm text-foreground overflow-x-auto whitespace-pre-wrap max-h-[350px] overflow-y-auto">
            {bibliography.content}
          </pre>
        </div>
      ) : (
        <div className="text-center py-12 bg-card border border-border rounded-lg">
          <BookOpen className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <p className="text-muted-foreground">No citations available</p>
          <p className="text-sm text-muted-foreground mt-2">
            Citations are automatically extracted from your project documents
          </p>
        </div>
      )}

      <div className="flex items-center justify-between pt-4 border-t border-border">
        <Button variant="ghost" onClick={onBack}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back
        </Button>
        <Button onClick={onContinue} disabled={!hasCitations}>
          Continue
          <ArrowRight className="h-4 w-4 ml-2" />
        </Button>
      </div>
    </div>
  );
};
