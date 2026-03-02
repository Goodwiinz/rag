'use client';

/**
 * DraftViewer Component
 * Displays literature review draft content with citations
 */

import React, { useCallback, useMemo, useRef, useState } from 'react';
import { Download, FileText, Code, History } from 'lucide-react';
import type { Draft } from '@/services/projectService';
import { ToneToolbar } from './ToneToolbar';
import { RewriteDiffView } from './RewriteDiffView';
import { WriterToolbar } from './WriterToolbar';
import { InsertPreview } from './InsertPreview';
import { OutlineDialog } from './OutlineDialog';
import type {
  RewriteResponse,
  WriteResponse,
  OutlineSection,
} from '@/types/scispace';

export interface DraftViewerProps {
  draft: Draft;
  versions?: Array<{ version: number; created_at: string }>;
  documentIds?: string[];
  onVersionChange?: (version: number) => void;
  onExport?: (format: 'markdown' | 'latex') => void;
  onTextRewrite?: (original: string, rewritten: string) => void;
}

export const DraftViewer: React.FC<DraftViewerProps> = ({
  draft,
  versions,
  documentIds,
  onVersionChange,
  onExport,
  onTextRewrite,
}) => {
  const contentRef = useRef<HTMLDivElement>(null);
  const [selectedText, setSelectedText] = useState('');
  const [toneToolbarPos, setToneToolbarPos] = useState<{
    top: number;
    left: number;
  } | null>(null);
  const [rewriteResult, setRewriteResult] = useState<RewriteResponse | null>(
    null
  );
  const [writerToolbarPos, setWriterToolbarPos] = useState<{
    top: number;
    left: number;
  } | null>(null);
  const [writeResult, setWriteResult] = useState<WriteResponse | null>(null);
  const [showOutlineDialog, setShowOutlineDialog] = useState(false);

  const handleTextSelect = useCallback((event: React.MouseEvent) => {
    const selection = window.getSelection();
    if (!selection || !contentRef.current) {
      setSelectedText('');
      setToneToolbarPos(null);
      setWriterToolbarPos(null);
      return;
    }

    if (selection.isCollapsed) {
      // Collapsed selection (cursor click) → WriterToolbar
      setSelectedText('');
      setToneToolbarPos(null);

      // Use click position relative to container
      const containerRect = contentRef.current.getBoundingClientRect();
      const surroundingText = contentRef.current.textContent || '';
      if (surroundingText.trim().length > 0) {
        setWriterToolbarPos({
          top: event.clientY - containerRect.top - 44,
          left: event.clientX - containerRect.left,
        });
      }
      return;
    }

    // Text selection with 5+ words → ToneToolbar
    const text = selection.toString().trim();
    if (text.split(/\s+/).length >= 5) {
      const range = selection.getRangeAt(0);
      const rect = range.getBoundingClientRect();
      const containerRect = contentRef.current.getBoundingClientRect();
      setSelectedText(text);
      setToneToolbarPos({
        top: rect.top - containerRect.top - 44,
        left: rect.left - containerRect.left,
      });
      setWriterToolbarPos(null);
    } else {
      setSelectedText('');
      setToneToolbarPos(null);
      setWriterToolbarPos(null);
    }
  }, []);

  const handleToneRewrite = useCallback((result: RewriteResponse) => {
    setRewriteResult(result);
    setToneToolbarPos(null);
  }, []);

  const handleAcceptRewrite = useCallback(
    (rewritten: string) => {
      if (onTextRewrite && rewriteResult) {
        onTextRewrite(rewriteResult.original, rewritten);
      }
      setRewriteResult(null);
      setSelectedText('');
    },
    [onTextRewrite, rewriteResult]
  );

  const handleRejectRewrite = useCallback(() => {
    setRewriteResult(null);
    setSelectedText('');
  }, []);

  const handleWriteInsert = useCallback((result: WriteResponse) => {
    setWriteResult(result);
    setWriterToolbarPos(null);
  }, []);

  const handleAcceptWrite = useCallback(
    (text: string) => {
      if (onTextRewrite) {
        onTextRewrite('', text);
      }
      setWriteResult(null);
    },
    [onTextRewrite]
  );

  const handleInsertOutline = useCallback(
    (sections: OutlineSection[]) => {
      const outlineText = sections
        .map((s) => `## ${s.title}\n\n${s.description}`)
        .join('\n\n');
      if (onTextRewrite) {
        onTextRewrite('', outlineText);
      }
    },
    [onTextRewrite]
  );

  // Convert [Doc N] citations to clickable links
  const formattedContent = useMemo(() => {
    if (!draft.content) return '';

    return draft.content.replace(
      /\[Doc (\d+)\]/g,
      '<span class="inline-flex items-center px-1.5 py-0.5 rounded bg-[#00ff9f]/10 text-[#00ff9f] text-xs font-mono cursor-pointer hover:bg-[#00ff9f]/20 transition-colors">[Doc $1]</span>'
    );
  }, [draft.content]);

  return (
    <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-[#1a1a1a]">
        <div className="flex items-center gap-3">
          <FileText className="h-5 w-5 text-[#00ff9f]" />
          <div>
            <h3 className="font-mono font-medium text-gray-200">
              {draft.title}
            </h3>
            <p className="text-xs text-gray-500 font-mono">
              Version {draft.version} • {draft.word_count} words •{' '}
              {draft.citation_count} citations
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

          {/* Export Buttons */}
          {onExport && (
            <div className="flex items-center gap-1">
              <button
                onClick={() => onExport('markdown')}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-[#1a1a1a] border border-[#333] rounded text-xs font-mono text-gray-300 hover:border-[#00ff9f] hover:text-[#00ff9f] transition-colors"
                title="Export as Markdown"
              >
                <Download className="h-3 w-3" />
                MD
              </button>
              <button
                onClick={() => onExport('latex')}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-[#1a1a1a] border border-[#333] rounded text-xs font-mono text-gray-300 hover:border-[#00ff9f] hover:text-[#00ff9f] transition-colors"
                title="Export as LaTeX"
              >
                <Code className="h-3 w-3" />
                TeX
              </button>
            </div>
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
        <div
          ref={contentRef}
          className="prose prose-invert prose-sm max-w-none font-mono text-gray-300 relative"
          onMouseUp={handleTextSelect}
          dangerouslySetInnerHTML={{ __html: formatMarkdown(formattedContent) }}
        />
        {toneToolbarPos && selectedText && !rewriteResult && (
          <ToneToolbar
            selectedText={selectedText}
            position={toneToolbarPos}
            onRewrite={handleToneRewrite}
            onClose={() => {
              setToneToolbarPos(null);
              setSelectedText('');
            }}
          />
        )}
        {writerToolbarPos &&
          !selectedText &&
          !writeResult &&
          !rewriteResult && (
            <WriterToolbar
              cursorContext={contentRef.current?.textContent || ''}
              position={writerToolbarPos}
              documentIds={documentIds}
              onInsert={handleWriteInsert}
              onOutlineRequest={() => {
                setShowOutlineDialog(true);
                setWriterToolbarPos(null);
              }}
              onClose={() => setWriterToolbarPos(null)}
            />
          )}
      </div>

      {/* Rewrite Diff */}
      {rewriteResult && (
        <div className="px-4 pb-4">
          <RewriteDiffView
            original={rewriteResult.original}
            rewritten={rewriteResult.rewritten}
            toneApplied={rewriteResult.tone_applied}
            citationsPreserved={rewriteResult.citations_preserved}
            onAccept={handleAcceptRewrite}
            onReject={handleRejectRewrite}
          />
        </div>
      )}

      {/* Write Insert Preview */}
      {writeResult && (
        <div className="px-4 pb-4">
          <InsertPreview
            generated={writeResult.generated}
            citationsUsed={writeResult.citations_used}
            sectionType={writeResult.section_type}
            confidence={writeResult.confidence}
            onAccept={handleAcceptWrite}
            onEditFirst={handleAcceptWrite}
            onDiscard={() => setWriteResult(null)}
          />
        </div>
      )}

      {/* Outline Dialog */}
      <OutlineDialog
        isOpen={showOutlineDialog}
        onInsertOutline={handleInsertOutline}
        onClose={() => setShowOutlineDialog(false)}
      />

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

// Simple markdown to HTML conversion
function formatMarkdown(content: string): string {
  return (
    content
      // Headers
      .replace(
        /^## (.+)$/gm,
        '<h2 class="text-lg font-bold text-[#00ff9f] mt-6 mb-3">$1</h2>'
      )
      .replace(
        /^### (.+)$/gm,
        '<h3 class="text-base font-bold text-[#00d4ff] mt-4 mb-2">$1</h3>'
      )
      // Paragraphs
      .replace(/\n\n/g, '</p><p class="mb-4">')
      // Wrap in paragraph
      .replace(/^(.+)$/gm, '<p class="mb-4">$1</p>')
      // Clean up
      .replace(/<p class="mb-4"><h/g, '<h')
      .replace(/<\/h2><\/p>/g, '</h2>')
      .replace(/<\/h3><\/p>/g, '</h3>')
  );
}

export default DraftViewer;
