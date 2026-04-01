'use client';

import React, { useState } from 'react';
import { ListTree, Loader2, X, Copy, Check } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { generateOutline } from '@/services/scispaceService';
import type {
  OutlineResponse,
  OutlineSection,
  SectionType,
} from '@/types/scispace';
import toast from 'react-hot-toast';

interface OutlineDialogProps {
  isOpen: boolean;
  documents?: Array<{ id: string; title: string }>;
  onInsertOutline: (sections: OutlineSection[]) => void;
  onClose: () => void;
}

const styleOptions = [
  { value: 'academic' as const, label: 'Academic' },
  { value: 'technical' as const, label: 'Technical' },
  { value: 'summary' as const, label: 'Summary' },
];

const sectionTypeOptions: { value: SectionType; label: string }[] = [
  { value: 'introduction', label: 'Introduction' },
  { value: 'methodology', label: 'Methodology' },
  { value: 'results', label: 'Results' },
  { value: 'discussion', label: 'Discussion' },
  { value: 'conclusion', label: 'Conclusion' },
  { value: 'abstract', label: 'Abstract' },
];

export const OutlineDialog: React.FC<OutlineDialogProps> = ({
  isOpen,
  documents = [],
  onInsertOutline,
  onClose,
}) => {
  const [question, setQuestion] = useState('');
  const [style, setStyle] = useState<'academic' | 'technical' | 'summary'>(
    'academic'
  );
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [selectedSections, setSelectedSections] = useState<SectionType[]>([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<OutlineResponse | null>(null);

  if (!isOpen) return null;

  const toggleDocId = (id: string) => {
    setSelectedDocIds((prev) =>
      prev.includes(id) ? prev.filter((d) => d !== id) : [...prev, id]
    );
  };

  const toggleSectionType = (type: SectionType) => {
    setSelectedSections((prev) =>
      prev.includes(type) ? prev.filter((s) => s !== type) : [...prev, type]
    );
  };

  const handleGenerate = async () => {
    if (!question.trim() || question.trim().length < 10) return;
    setLoading(true);
    try {
      const res = await generateOutline({
        research_question: question.trim(),
        style,
        document_ids: selectedDocIds.length > 0 ? selectedDocIds : undefined,
        section_types:
          selectedSections.length > 0 ? selectedSections : undefined,
      });
      setResult(res);
    } catch {
      toast.error('Failed to generate outline');
    } finally {
      setLoading(false);
    }
  };

  const handleCopyMarkdown = () => {
    if (!result) return;
    const md = result.sections
      .map(
        (s) =>
          `## ${s.title}\n\n${s.description}\n\n*Suggested: ~${s.suggested_word_count} words*`
      )
      .join('\n\n---\n\n');
    navigator.clipboard.writeText(md);
    toast.success('Outline copied as markdown');
  };

  const handleClose = () => {
    setResult(null);
    setQuestion('');
    setSelectedDocIds([]);
    setSelectedSections([]);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70">
      <div className="w-full max-w-2xl max-h-[85vh] overflow-hidden rounded-lg border border-[#1a1a1a] bg-[#0a0a0a]">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#1a1a1a] p-4">
          <div className="flex items-center gap-2">
            <ListTree className="h-5 w-5 text-brand-cyan" />
            <h2 className="font-mono text-lg font-bold text-sol">
              Generate Outline
            </h2>
          </div>
          <button
            onClick={handleClose}
            className="p-1 text-gray-500 hover:text-gray-300"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="max-h-[60vh] space-y-4 overflow-y-auto p-4">
          {/* Research Question */}
          <div>
            <label className="mb-1 block font-mono text-xs uppercase tracking-wide text-gray-500">
              Research Question *
            </label>
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="What is your research question? (min 10 characters)"
              rows={3}
              className="w-full resize-none rounded border border-[#333] bg-[#1a1a1a] px-3 py-2 font-mono text-sm text-gray-300 placeholder-gray-600 focus:border-sol focus:outline-none"
            />
          </div>

          {/* Style Selector */}
          <div>
            <label className="mb-1 block font-mono text-xs uppercase tracking-wide text-gray-500">
              Style
            </label>
            <div className="flex gap-2">
              {styleOptions.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setStyle(opt.value)}
                  className={cn(
                    'rounded border px-3 py-1.5 font-mono text-xs transition-colors',
                    style === opt.value
                      ? 'border-sol/50 bg-sol/10 text-sol'
                      : 'border-[#333] text-gray-400 hover:border-sol/30'
                  )}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Section Types */}
          <div>
            <label className="mb-1 block font-mono text-xs uppercase tracking-wide text-gray-500">
              Sections (optional — leave empty for all)
            </label>
            <div className="flex flex-wrap gap-2">
              {sectionTypeOptions.map((opt) => (
                <label
                  key={opt.value}
                  className="flex cursor-pointer items-center gap-1.5"
                >
                  <input
                    type="checkbox"
                    checked={selectedSections.includes(opt.value)}
                    onChange={() => toggleSectionType(opt.value)}
                    className="accent-sol"
                  />
                  <span className="font-mono text-xs text-gray-300">
                    {opt.label}
                  </span>
                </label>
              ))}
            </div>
          </div>

          {/* Document Scope */}
          {documents.length > 0 && (
            <div>
              <label className="mb-2 block font-mono text-xs uppercase tracking-wide text-gray-500">
                Document Scope (optional)
              </label>
              <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                {documents.map((doc) => (
                  <label
                    key={doc.id}
                    className="flex items-center gap-2 rounded border border-[#333] px-3 py-2 text-sm text-gray-300"
                  >
                    <input
                      type="checkbox"
                      checked={selectedDocIds.includes(doc.id)}
                      onChange={() => toggleDocId(doc.id)}
                      className="accent-sol"
                    />
                    <span className="truncate font-mono text-xs">
                      {doc.title}
                    </span>
                  </label>
                ))}
              </div>
            </div>
          )}

          {/* Generate Button */}
          {!result && (
            <Button
              onClick={handleGenerate}
              disabled={loading || question.trim().length < 10}
              className="w-full gap-2 bg-sol/10 text-sol hover:bg-sol/20 disabled:opacity-50"
              aria-label="Generate outline"
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <ListTree className="h-4 w-4" />
              )}
              {loading ? 'Generating...' : 'Generate Outline'}
            </Button>
          )}

          {/* Result */}
          {result && (
            <div className="space-y-3 rounded-lg border border-[#1a1a1a] bg-[#111] p-4">
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs text-gray-500">
                  {result.sections.length} sections ~
                  {result.total_suggested_words.toLocaleString()} words
                </span>
              </div>
              {result.sections.map((section, idx) => (
                <div
                  key={idx}
                  className="rounded border border-[#1a1a1a] bg-[#0a0a0a] p-3"
                >
                  <div className="flex items-center justify-between">
                    <h4 className="font-mono text-sm font-bold text-gray-200">
                      {section.title}
                    </h4>
                    <span className="font-mono text-[10px] text-gray-500">
                      ~{section.suggested_word_count} words
                    </span>
                  </div>
                  <p className="mt-1 text-xs leading-relaxed text-gray-400">
                    {section.description}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 border-t border-[#1a1a1a] p-4">
          <Button
            variant="ghost"
            size="sm"
            className="text-gray-400 hover:bg-[#1a1a1a] hover:text-gray-200"
            onClick={handleClose}
          >
            Cancel
          </Button>
          {result && (
            <>
              <Button
                variant="ghost"
                size="sm"
                className="gap-1.5 text-brand-cyan hover:bg-brand-cyan/10 hover:text-brand-cyan"
                onClick={handleCopyMarkdown}
                aria-label="Copy as markdown"
              >
                <Copy className="h-3.5 w-3.5" />
                Copy as Markdown
              </Button>
              <Button
                size="sm"
                className="gap-1.5 bg-sol/10 text-sol hover:bg-sol/20"
                onClick={() => {
                  onInsertOutline(result.sections);
                  handleClose();
                }}
                aria-label="Insert outline"
              >
                <Check className="h-3.5 w-3.5" />
                Insert Outline
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default OutlineDialog;
