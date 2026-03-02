'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Eye, Pencil, Save, X } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type {
  ProjectDocument,
  ProjectNote,
  ProjectNoteCreate,
} from '@/services/projectService';
import { ToneToolbar } from './ToneToolbar';
import { RewriteDiffView } from './RewriteDiffView';
import type { RewriteResponse } from '@/types/scispace';

export interface NoteEditorValue extends ProjectNoteCreate {
  title: string;
}

export interface NoteEditorProps {
  isOpen: boolean;
  initialNote?: ProjectNote | null;
  availableDocuments?: ProjectDocument[];
  onClose: () => void;
  onSave: (value: NoteEditorValue) => Promise<void>;
}

export function NoteEditor({
  isOpen,
  initialNote,
  availableDocuments = [],
  onClose,
  onSave,
}: NoteEditorProps) {
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [tagInput, setTagInput] = useState('');
  const [tags, setTags] = useState<string[]>([]);
  const [linkedDocumentIds, setLinkedDocumentIds] = useState<string[]>([]);
  const [preview, setPreview] = useState(false);
  const [saving, setSaving] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [selectedText, setSelectedText] = useState('');
  const [selectionRange, setSelectionRange] = useState<{
    start: number;
    end: number;
  } | null>(null);
  const [toneToolbarPos, setToneToolbarPos] = useState<{
    top: number;
    left: number;
  } | null>(null);
  const [rewriteResult, setRewriteResult] = useState<RewriteResponse | null>(
    null
  );

  useEffect(() => {
    if (!isOpen) return;
    setTitle(initialNote?.title ?? '');
    setContent(initialNote?.content ?? '');
    setTags(initialNote?.tags ?? []);
    setLinkedDocumentIds(initialNote?.linked_document_ids ?? []);
    setTagInput('');
    setPreview(false);
  }, [initialNote, isOpen]);

  const canSave = useMemo(
    () => title.trim().length > 0 && !saving,
    [title, saving]
  );

  const handleTextSelect = useCallback(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    const start = ta.selectionStart;
    const end = ta.selectionEnd;
    const text = content.slice(start, end).trim();
    if (text.split(/\s+/).length >= 5) {
      setSelectedText(text);
      setSelectionRange({ start, end });
      setToneToolbarPos({ top: -44, left: 0 });
    } else {
      setSelectedText('');
      setSelectionRange(null);
      setToneToolbarPos(null);
    }
  }, [content]);

  const handleToneRewrite = useCallback((result: RewriteResponse) => {
    setRewriteResult(result);
    setToneToolbarPos(null);
  }, []);

  const handleAcceptRewrite = useCallback(
    (rewritten: string) => {
      if (selectionRange) {
        const before = content.slice(0, selectionRange.start);
        const after = content.slice(selectionRange.end);
        setContent(before + rewritten + after);
      }
      setRewriteResult(null);
      setSelectedText('');
      setSelectionRange(null);
    },
    [content, selectionRange]
  );

  const handleRejectRewrite = useCallback(() => {
    setRewriteResult(null);
    setSelectedText('');
    setSelectionRange(null);
  }, []);

  if (!isOpen) return null;

  const handleAddTag = () => {
    const next = tagInput.trim();
    if (!next || tags.includes(next)) return;
    setTags((prev) => [...prev, next]);
    setTagInput('');
  };

  const toggleDocumentLink = (documentId: string) => {
    setLinkedDocumentIds((prev) =>
      prev.includes(documentId)
        ? prev.filter((id) => id !== documentId)
        : [...prev, documentId]
    );
  };

  const handleSubmit = async () => {
    if (!title.trim()) return;
    setSaving(true);
    try {
      await onSave({
        title: title.trim(),
        content,
        tags,
        linked_document_ids: linkedDocumentIds,
      });
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
      <div className="bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg w-full max-w-3xl max-h-[85vh] overflow-hidden">
        <div className="flex items-center justify-between p-4 border-b border-[#1a1a1a]">
          <h2 className="text-lg font-mono font-bold text-[#00ff9f]">
            {initialNote ? 'Edit Note' : 'Create Note'}
          </h2>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPreview((prev) => !prev)}
              className="px-3 py-1.5 text-xs font-mono border border-[#333] rounded text-gray-300 hover:border-[#00ff9f]/50"
            >
              {preview ? (
                <span className="inline-flex items-center gap-1">
                  <Pencil className="h-3.5 w-3.5" /> Edit
                </span>
              ) : (
                <span className="inline-flex items-center gap-1">
                  <Eye className="h-3.5 w-3.5" /> Preview
                </span>
              )}
            </button>
            <button
              onClick={onClose}
              className="p-1 text-gray-500 hover:text-gray-300"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        <div className="p-4 space-y-4 overflow-y-auto max-h-[60vh]">
          <div>
            <label className="block text-xs text-gray-500 font-mono uppercase tracking-wide mb-1">
              Title *
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Note title"
              className="w-full px-3 py-2 bg-[#1a1a1a] border border-[#333] rounded text-sm font-mono text-gray-300 placeholder-gray-600 focus:outline-none focus:border-[#00ff9f]"
            />
          </div>

          <div>
            <label className="block text-xs text-gray-500 font-mono uppercase tracking-wide mb-1">
              Content (Markdown)
            </label>
            {!preview ? (
              <div className="relative">
                {toneToolbarPos && selectedText && !rewriteResult && (
                  <ToneToolbar
                    selectedText={selectedText}
                    position={{ top: -44, left: 0 }}
                    onRewrite={handleToneRewrite}
                    onClose={() => {
                      setToneToolbarPos(null);
                      setSelectedText('');
                    }}
                  />
                )}
                <textarea
                  ref={textareaRef}
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  onMouseUp={handleTextSelect}
                  onKeyUp={handleTextSelect}
                  placeholder="Write note content in markdown..."
                  rows={12}
                  className="w-full px-3 py-2 bg-[#1a1a1a] border border-[#333] rounded text-sm font-mono text-gray-300 placeholder-gray-600 focus:outline-none focus:border-[#00ff9f] resize-none"
                />
                {rewriteResult && (
                  <div className="mt-3">
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
              </div>
            ) : (
              <div className="p-3 bg-[#111] border border-[#333] rounded min-h-[180px] prose prose-invert prose-sm max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {content || '_Nothing to preview yet_'}
                </ReactMarkdown>
              </div>
            )}
          </div>

          <div>
            <label className="block text-xs text-gray-500 font-mono uppercase tracking-wide mb-1">
              Tags
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    handleAddTag();
                  }
                }}
                placeholder="Add tag and press Enter"
                className="flex-1 px-3 py-2 bg-[#1a1a1a] border border-[#333] rounded text-sm font-mono text-gray-300 placeholder-gray-600 focus:outline-none focus:border-[#00ff9f]"
              />
              <button
                onClick={handleAddTag}
                className="px-3 py-2 text-xs font-mono border border-[#00ff9f]/30 text-[#00ff9f] rounded hover:bg-[#00ff9f]/10"
              >
                Add
              </button>
            </div>
            {tags.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
                {tags.map((tag) => (
                  <button
                    key={tag}
                    onClick={() =>
                      setTags((prev) => prev.filter((t) => t !== tag))
                    }
                    className="px-2 py-1 bg-[#1a1a1a] border border-[#333] rounded text-xs font-mono text-gray-300 hover:border-red-400 hover:text-red-300"
                  >
                    {tag}
                  </button>
                ))}
              </div>
            )}
          </div>

          {availableDocuments.length > 0 && (
            <div>
              <label className="block text-xs text-gray-500 font-mono uppercase tracking-wide mb-2">
                Link Documents
              </label>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {availableDocuments.map((doc) => (
                  <label
                    key={doc.document_id || doc.id}
                    className="flex items-center gap-2 px-3 py-2 border border-[#333] rounded text-sm text-gray-300"
                  >
                    <input
                      type="checkbox"
                      checked={linkedDocumentIds.includes(doc.document_id)}
                      onChange={() => toggleDocumentLink(doc.document_id)}
                    />
                    <span className="truncate font-mono text-xs">
                      {doc.document?.title ||
                        doc.document?.filename ||
                        doc.document_id}
                    </span>
                  </label>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 p-4 border-t border-[#1a1a1a]">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-mono text-gray-400 hover:text-gray-300 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={!canSave}
            className="flex items-center gap-2 px-4 py-2 bg-[#00ff9f]/10 text-[#00ff9f] border border-[#00ff9f]/30 rounded font-mono text-sm hover:bg-[#00ff9f]/20 transition-colors disabled:opacity-50"
          >
            <Save className="h-4 w-4" />
            {saving ? 'Saving...' : 'Save Note'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default NoteEditor;
