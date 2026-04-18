'use client';

import React from 'react';
import { Check, Pencil, X, Quote, BarChart3 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import type { SectionType } from '@/types/scispace';

interface InsertPreviewProps {
  generated: string;
  citationsUsed: string[];
  sectionType?: SectionType | null;
  confidence: number;
  onAccept: (text: string) => void;
  onEditFirst: (text: string) => void;
  onDiscard: () => void;
}

const sectionLabels: Record<
  string,
  { label: string; color: string; bg: string }
> = {
  introduction: {
    label: 'Introduction',
    color: 'text-brand-cyan',
    bg: 'bg-brand-cyan/10 border-brand-cyan/30',
  },
  methodology: {
    label: 'Methodology',
    color: 'text-helios',
    bg: 'bg-helios/10 border-helios/30',
  },
  results: {
    label: 'Results',
    color: 'text-sol',
    bg: 'bg-sol/10 border-sol/30',
  },
  discussion: {
    label: 'Discussion',
    color: 'text-purple-400',
    bg: 'bg-purple-400/10 border-purple-400/30',
  },
  conclusion: {
    label: 'Conclusion',
    color: 'text-brand-cyan',
    bg: 'bg-brand-cyan/10 border-brand-cyan/30',
  },
  abstract: {
    label: 'Abstract',
    color: 'text-helios',
    bg: 'bg-helios/10 border-helios/30',
  },
  custom: {
    label: 'Custom',
    color: 'text-gray-400',
    bg: 'bg-gray-400/10 border-gray-400/30',
  },
};

function getConfidenceColor(confidence: number): string {
  if (confidence >= 0.8) return 'text-sol';
  if (confidence >= 0.6) return 'text-helios';
  return 'text-red-400';
}

export const InsertPreview: React.FC<InsertPreviewProps> = ({
  generated,
  citationsUsed,
  sectionType,
  confidence,
  onAccept,
  onEditFirst,
  onDiscard,
}) => {
  const section = sectionType ? sectionLabels[sectionType] : null;

  return (
    <div className="overflow-hidden rounded-lg border border-[#1a1a1a] bg-[#0a0a0a]">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#1a1a1a] px-4 py-3">
        <div className="flex items-center gap-3">
          <h3 className="font-mono text-sm font-bold text-gray-200">
            Generated Content
          </h3>
          {section && (
            <Badge className={cn('border text-xs', section.bg, section.color)}>
              {section.label}
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-4">
          {citationsUsed.length > 0 && (
            <div className="flex items-center gap-1.5 text-xs text-gray-500">
              <Quote className="h-3 w-3" />
              <span>
                {citationsUsed.length} citation
                {citationsUsed.length !== 1 ? 's' : ''}
              </span>
            </div>
          )}
          <div
            className={cn(
              'flex items-center gap-1.5 text-xs',
              getConfidenceColor(confidence)
            )}
          >
            <BarChart3 className="h-3 w-3" />
            <span>{Math.round(confidence * 100)}%</span>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-h-[400px] overflow-y-auto p-4">
        <div className="whitespace-pre-wrap font-mono text-sm leading-relaxed text-gray-300">
          {generated}
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-end gap-2 border-t border-[#1a1a1a] px-4 py-3">
        <Button
          variant="ghost"
          size="sm"
          className="gap-1.5 text-gray-400 hover:bg-[#1a1a1a] hover:text-gray-200"
          onClick={onDiscard}
          aria-label="Discard generated content"
        >
          <X className="h-3.5 w-3.5" />
          Discard
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="gap-1.5 text-helios hover:bg-helios/10 hover:text-helios"
          onClick={() => onEditFirst(generated)}
          aria-label="Edit before inserting"
        >
          <Pencil className="h-3.5 w-3.5" />
          Edit First
        </Button>
        <Button
          size="sm"
          className="gap-1.5 bg-sol/10 text-sol hover:bg-sol/20"
          onClick={() => onAccept(generated)}
          aria-label="Accept and insert"
        >
          <Check className="h-3.5 w-3.5" />
          Accept
        </Button>
      </div>
    </div>
  );
};

export default InsertPreview;
