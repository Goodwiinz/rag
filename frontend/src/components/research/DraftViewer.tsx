'use client';

/**
 * DraftViewer Component
 * Displays literature review draft content with citations using ReactMarkdown
 */

import React, { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Download, FileText, History } from 'lucide-react';
import type { Draft } from '@/services/projectService';

export interface DraftViewerProps {
  draft: Draft;
  versions?: Array<{ version: number; created_at: string }>;
  onVersionChange?: (version: number) => void;
  onExport?: ((format: 'markdown' | 'latex') => void) | (() => void);
}

export const DraftViewer: React.FC<DraftViewerProps> = ({
  draft,
  versions,
  onVersionChange,
  onExport,
}) => {
  // Pre-process content to wrap [Doc N] in special markers for custom rendering
  const processedContent = useMemo(() => {
    if (!draft.content) return '';
    return draft.content;
  }, [draft.content]);

  // Custom component to render [Doc N] citation badges inside text
  const renderTextWithCitations = (text: string) => {
    const parts = text.split(/(\[Doc \d+\])/g);
    return parts.map((part, idx) => {
      const match = part.match(/^\[Doc (\d+)\]$/);
      if (match) {
        return (
          <span
            key={idx}
            className="inline-flex items-center px-1.5 py-0.5 rounded bg-[#00ff9f]/10 text-[#00ff9f] text-xs font-mono cursor-pointer hover:bg-[#00ff9f]/20 transition-colors"
          >
            [Doc {match[1]}]
          </span>
        );
      }
      return part;
    });
  };

  return (
    <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-[#1a1a1a]">
        <div className="flex items-center gap-3">
          <FileText className="h-5 w-5 text-[#00ff9f]" />
          <div>
            <h3 className="font-mono font-medium text-gray-200">{draft.title}</h3>
            <p className="text-xs text-gray-500 font-mono">
              Version {draft.version} • {draft.word_count} words • {draft.citation_count} citations
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Version Selector */}
          {versions && versions.length > 1 && onVersionChange && (
            <div className="flex items-center gap-2">
              <History className="h-4 w-4 text-gray-500" />
              <select
                value={draft.version}
                onChange={(e) => onVersionChange(parseInt(e.target.value, 10))}
                className="px-2 py-1 bg-[#1a1a1a] border border-[#333] rounded text-xs font-mono text-gray-300 focus:outline-none focus:border-[#00ff9f]"
              >
                {versions.map((v) => (
                  <option key={v.version} value={v.version}>
                    v{v.version} - {new Date(v.created_at).toLocaleDateString()}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Export Button */}
          {onExport && (
            <button
              onClick={() => (onExport as () => void)()}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-[#1a1a1a] border border-[#333] rounded text-xs font-mono text-gray-300 hover:border-[#00ff9f] hover:text-[#00ff9f] transition-colors"
              title="Export Draft"
            >
              <Download className="h-3 w-3" />
              Export
            </button>
          )}
        </div>
      </div>

      {/* Themes */}
      {draft.themes && draft.themes.length > 0 && (
        <div className="px-4 py-2 border-b border-[#1a1a1a] flex items-center gap-2">
          <span className="text-xs text-gray-500 font-mono">Themes:</span>
          {draft.themes.map((theme, idx) => (
            <span
              key={idx}
              className="px-2 py-0.5 bg-[#00ff9f]/10 text-[#00ff9f] text-xs font-mono rounded"
            >
              {theme}
            </span>
          ))}
        </div>
      )}

      {/* Content */}
      <div className="p-6 max-h-[600px] overflow-y-auto">
        <div className="prose prose-invert prose-sm max-w-none font-mono text-gray-300">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              h2: ({ children }) => (
                <h2 className="text-lg font-bold text-[#00ff9f] mt-6 mb-3">
                  {children}
                </h2>
              ),
              h3: ({ children }) => (
                <h3 className="text-base font-bold text-[#00d4ff] mt-4 mb-2">
                  {children}
                </h3>
              ),
              p: ({ children }) => {
                // Process children to render citation badges
                const processed = React.Children.map(children, (child) => {
                  if (typeof child === 'string') {
                    return renderTextWithCitations(child);
                  }
                  return child;
                });
                return <p className="mb-4">{processed}</p>;
              },
              li: ({ children }) => {
                const processed = React.Children.map(children, (child) => {
                  if (typeof child === 'string') {
                    return renderTextWithCitations(child);
                  }
                  return child;
                });
                return <li className="mb-1">{processed}</li>;
              },
            }}
          >
            {processedContent}
          </ReactMarkdown>
        </div>
      </div>

      {/* Footer */}
      <div className="px-4 py-2 border-t border-[#1a1a1a] text-xs text-gray-500 font-mono">
        Generated {new Date(draft.created_at).toLocaleString()}
        {draft.is_current && (
          <span className="ml-2 px-1.5 py-0.5 bg-[#00ff9f]/10 text-[#00ff9f] rounded">
            Current
          </span>
        )}
      </div>
    </div>
  );
};

export default DraftViewer;
