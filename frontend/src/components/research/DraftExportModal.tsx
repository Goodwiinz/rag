'use client';

/**
 * DraftExportModal Component
 * Modal for exporting drafts to different formats
 */

import React, { useEffect, useState } from 'react';
import { X, Download, FileText, Code, Loader2 } from 'lucide-react';

export interface DraftExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onExport: (
    format: 'markdown' | 'latex',
    includeBibliography: boolean,
    bibliographyFormat: 'bibtex' | 'biblatex'
  ) => Promise<void>;
  draftTitle: string;
  initialFormat?: 'markdown' | 'latex';
}

export const DraftExportModal: React.FC<DraftExportModalProps> = ({
  isOpen,
  onClose,
  onExport,
  draftTitle,
  initialFormat = 'markdown',
}) => {
  const [format, setFormat] = useState<'markdown' | 'latex'>(initialFormat);
  const [includeBibliography, setIncludeBibliography] = useState(true);
  const [bibliographyFormat, setBibliographyFormat] = useState<
    'bibtex' | 'biblatex'
  >('bibtex');
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setFormat(initialFormat);
    }
  }, [initialFormat, isOpen]);

  if (!isOpen) return null;

  const handleExport = async () => {
    setExporting(true);
    try {
      await onExport(format, includeBibliography, bibliographyFormat);
      onClose();
    } catch (error) {
      console.error('Export failed:', error);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
      <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg w-full max-w-md">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[#1a1a1a]">
          <div className="flex items-center gap-2">
            <Download className="h-5 w-5 text-sol" />
            <h2 className="font-mono font-bold text-gray-200">Export Draft</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-gray-500 hover:text-gray-300 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-4">
          <p className="text-sm text-gray-400 font-mono">
            Exporting: <span className="text-gray-200">{draftTitle}</span>
          </p>

          {/* Format Selection */}
          <div>
            <label className="block text-xs text-gray-500 font-mono uppercase tracking-wide mb-2">
              Export Format
            </label>
            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={() => setFormat('markdown')}
                className={`flex flex-col items-center gap-2 p-4 rounded border transition-colors ${
                  format === 'markdown'
                    ? 'bg-sol/10 border-sol/50 text-sol'
                    : 'bg-[#1a1a1a] border-[#333] text-gray-400 hover:border-[#555]'
                }`}
              >
                <FileText className="h-6 w-6" />
                <span className="text-sm font-mono">Markdown</span>
                <span className="text-xs text-gray-500">.md</span>
              </button>
              <button
                onClick={() => setFormat('latex')}
                className={`flex flex-col items-center gap-2 p-4 rounded border transition-colors ${
                  format === 'latex'
                    ? 'bg-sol/10 border-sol/50 text-sol'
                    : 'bg-[#1a1a1a] border-[#333] text-gray-400 hover:border-[#555]'
                }`}
              >
                <Code className="h-6 w-6" />
                <span className="text-sm font-mono">LaTeX</span>
                <span className="text-xs text-gray-500">.tex + .bib</span>
              </button>
            </div>
          </div>

          {/* Include Bibliography Toggle */}
          <div className="flex items-center justify-between p-3 bg-[#1a1a1a] rounded">
            <div>
              <span className="text-sm text-gray-300 font-mono">
                Include Bibliography
              </span>
              <p className="text-xs text-gray-500 mt-0.5">
                {format === 'latex'
                  ? 'Export references.bib file'
                  : 'Add references section'}
              </p>
            </div>
            <button
              onClick={() => setIncludeBibliography(!includeBibliography)}
              className={`relative w-12 h-6 rounded-full transition-colors ${
                includeBibliography
                  ? 'bg-sol/30 border-sol'
                  : 'bg-[#333] border-[#555]'
              } border`}
            >
              <span
                className={`absolute top-0.5 w-5 h-5 rounded-full transition-transform ${
                  includeBibliography
                    ? 'translate-x-6 bg-sol'
                    : 'translate-x-0.5 bg-gray-500'
                }`}
              />
            </button>
          </div>

          {/* Bibliography Format */}
          {includeBibliography && (
            <div>
              <label className="block text-xs text-gray-500 font-mono uppercase tracking-wide mb-2">
                Bibliography Format
              </label>
              <select
                value={bibliographyFormat}
                onChange={(e) =>
                  setBibliographyFormat(e.target.value as 'bibtex' | 'biblatex')
                }
                className="w-full px-3 py-2 bg-[#1a1a1a] border border-[#333] rounded text-sm font-mono text-gray-300 focus:outline-none focus:border-sol"
              >
                <option value="bibtex">BibTeX</option>
                <option value="biblatex">BibLaTeX</option>
              </select>
            </div>
          )}

          {/* LaTeX Info */}
          {format === 'latex' && (
            <div className="p-3 bg-helios/10 border border-helios/30 rounded text-xs font-mono text-helios">
              LaTeX export includes a .tex file and references.bib. You can
              compile with pdflatex + bibtex.
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 p-4 border-t border-[#1a1a1a]">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-mono text-gray-400 hover:text-gray-300 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleExport}
            disabled={exporting}
            className="flex items-center gap-2 px-4 py-2 bg-sol/10 text-sol border border-sol/30 rounded font-mono text-sm hover:bg-sol/20 transition-colors disabled:opacity-50"
          >
            {exporting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Exporting...
              </>
            ) : (
              <>
                <Download className="h-4 w-4" />
                Export
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default DraftExportModal;
