'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Download, FileText, Loader2, AlertTriangle } from 'lucide-react';
import { citationService } from '@/services/citationService';
import type { CitationResponse } from '@/types/research';
import { cn } from '@/lib/utils';

export interface BibliographyExportProps {
  citations: CitationResponse[];
  projectId?: string;
  className?: string;
  onExportComplete?: () => void;
}

type BibliographyFormat = 'bibtex' | 'ieee' | 'apa' | 'mla';

const FORMAT_OPTIONS: { value: BibliographyFormat; label: string; description: string }[] = [
  {
    value: 'bibtex',
    label: 'BibTeX',
    description: 'LaTeX compatible format (.bib)',
  },
  {
    value: 'ieee',
    label: 'IEEE',
    description: 'IEEE citation style (.txt)',
  },
  {
    value: 'apa',
    label: 'APA',
    description: 'American Psychological Association (.txt)',
  },
  {
    value: 'mla',
    label: 'MLA',
    description: 'Modern Language Association (.txt)',
  },
];

/**
 * BibliographyExport Component
 *
 * Allows users to export citations as formatted bibliography files.
 * Supports multiple citation formats: BibTeX, IEEE, APA, MLA
 *
 * Features:
 * - Format selection dropdown
 * - Citation selection checkboxes
 * - "Needs review" warnings for incomplete metadata
 * - Download functionality
 */
export function BibliographyExport({
  citations,
  projectId,
  className,
  onExportComplete,
}: BibliographyExportProps) {
  const [selectedFormat, setSelectedFormat] = useState<BibliographyFormat>('bibtex');
  const [selectedCitations, setSelectedCitations] = useState<Set<string>>(
    new Set(citations.map((c) => c.id))
  );
  const [isExporting, setIsExporting] = useState(false);

  const needsReviewCount = citations.filter((c) => c.needsReview).length;
  const selectedCount = selectedCitations.size;

  const handleToggleCitation = (citationId: string) => {
    setSelectedCitations((prev) => {
      const next = new Set(prev);
      if (next.has(citationId)) {
        next.delete(citationId);
      } else {
        next.add(citationId);
      }
      return next;
    });
  };

  const handleSelectAll = () => {
    if (selectedCitations.size === citations.length) {
      setSelectedCitations(new Set());
    } else {
      setSelectedCitations(new Set(citations.map((c) => c.id)));
    }
  };

  const handleExport = async () => {
    if (selectedCitations.size === 0) {
      return;
    }

    setIsExporting(true);
    try {
      const citationIds = Array.from(selectedCitations);
      const extension = selectedFormat === 'bibtex' ? 'bib' : selectedFormat;
      await citationService.downloadBibliography(
        selectedFormat,
        citationIds,
        projectId,
        `bibliography.${extension}`
      );

      onExportComplete?.();
    } catch (error) {
      console.error('Bibliography export failed:', error);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className={cn('space-y-6', className)}>
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold text-[var(--terminal-text)] font-mono">
            Export Bibliography
          </h3>
          <p className="text-sm text-[var(--terminal-text-muted)] font-mono mt-1">
            Select citations and format to export
          </p>
        </div>
        <FileText className="w-5 h-5 text-[var(--phosphor-green)]" />
      </div>

      {/* Format Selector */}
      <div className="space-y-2">
        <label className="text-sm font-mono font-medium text-[var(--terminal-text)] uppercase tracking-wider">
          Format
        </label>
        <Select value={selectedFormat} onValueChange={(v) => setSelectedFormat(v as BibliographyFormat)}>
          <SelectTrigger className="w-full bg-[var(--terminal-surface)] border-[var(--terminal-border)] font-mono">
            <SelectValue />
          </SelectTrigger>
          <SelectContent className="bg-[var(--terminal-surface)] border-[var(--terminal-border)]">
            {FORMAT_OPTIONS.map((format) => (
              <SelectItem key={format.value} value={format.value} className="font-mono">
                <div className="flex flex-col">
                  <span className="font-bold">{format.label}</span>
                  <span className="text-xs text-[var(--terminal-text-muted)]">
                    {format.description}
                  </span>
                </div>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Needs Review Warning */}
      {needsReviewCount > 0 && (
        <div className="p-4 rounded-lg border border-[var(--amber-gold)]/30 bg-[var(--amber-gold)]/5">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-[var(--amber-gold)] mt-0.5" />
            <div>
              <p className="text-sm font-mono font-bold text-[var(--amber-gold)]">
                {needsReviewCount} citation{needsReviewCount > 1 ? 's' : ''} need review
              </p>
              <p className="text-xs font-mono text-[var(--terminal-text-muted)] mt-1">
                Some citations have incomplete metadata. Review and edit before exporting for best results.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Citation Selection */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <label className="text-sm font-mono font-medium text-[var(--terminal-text)] uppercase tracking-wider">
            Citations ({selectedCount}/{citations.length})
          </label>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleSelectAll}
            className="h-7 text-xs font-mono"
          >
            {selectedCitations.size === citations.length ? 'Deselect All' : 'Select All'}
          </Button>
        </div>

        <div className="max-h-64 overflow-y-auto space-y-2 border border-[var(--terminal-border)] rounded-lg p-3 bg-[var(--terminal-surface)]">
          {citations.length === 0 ? (
            <p className="text-sm text-[var(--terminal-text-muted)] font-mono text-center py-4">
              No citations available
            </p>
          ) : (
            citations.map((citation) => (
              <div
                key={citation.id}
                className="flex items-start gap-3 p-2 rounded hover:bg-[var(--terminal-elevated)] transition-colors"
              >
                <Checkbox
                  checked={selectedCitations.has(citation.id)}
                  onCheckedChange={() => handleToggleCitation(citation.id)}
                  className="mt-0.5"
                />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-mono text-[var(--terminal-text)] line-clamp-2">
                    {citation.documentTitle || 'Untitled'}
                  </p>
                  <p className="text-xs font-mono text-[var(--terminal-text-muted)] mt-1">
                    {citation.authors && citation.authors.length > 0
                      ? citation.authors.slice(0, 3).join(', ') +
                        (citation.authors.length > 3 ? ', et al.' : '')
                      : 'Unknown authors'}{' '}
                    {citation.year && `(${citation.year})`}
                  </p>
                  {citation.needsReview && (
                    <span className="inline-flex items-center gap-1 mt-1 px-2 py-0.5 rounded text-[9px] font-mono font-bold uppercase tracking-wider bg-[var(--amber-gold)]/10 text-[var(--amber-gold)] border border-[var(--amber-gold)]/20">
                      <AlertTriangle className="w-3 h-3" />
                      Needs Review
                    </span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Export Button */}
      <div className="flex items-center justify-end gap-3 pt-4 border-t border-[var(--terminal-border)]">
        <p className="text-xs font-mono text-[var(--terminal-text-muted)]">
          {selectedCount} citation{selectedCount !== 1 ? 's' : ''} selected
        </p>
        <Button
          onClick={handleExport}
          disabled={selectedCount === 0 || isExporting}
          className="font-mono text-xs font-bold bg-[var(--phosphor-green)] text-[var(--terminal-bg)] hover:shadow-[0_0_20px_var(--phosphor-green-glow)] disabled:opacity-50"
        >
          {isExporting ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Exporting...
            </>
          ) : (
            <>
              <Download className="w-4 h-4 mr-2" />
              Download {selectedFormat.toUpperCase()}
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
