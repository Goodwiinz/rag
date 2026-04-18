'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  GraduationCap,
  Lightbulb,
  Minimize2,
  Maximize2,
  X,
  Loader2,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { rewriteText } from '@/services/scispaceService';
import type { ToneOption, RewriteResponse } from '@/types/scispace';

interface ToneToolbarProps {
  selectedText: string;
  position: { top: number; left: number };
  onRewrite: (result: RewriteResponse) => void;
  onClose: () => void;
}

const toneButtons: {
  tone: ToneOption;
  label: string;
  icon: React.ElementType;
}[] = [
  { tone: 'academic', label: 'Academic', icon: GraduationCap },
  { tone: 'simplified', label: 'Simplified', icon: Lightbulb },
  { tone: 'concise', label: 'Concise', icon: Minimize2 },
  { tone: 'expanded', label: 'Expanded', icon: Maximize2 },
];

export const ToneToolbar: React.FC<ToneToolbarProps> = ({
  selectedText,
  position,
  onRewrite,
  onClose,
}) => {
  const [loadingTone, setLoadingTone] = useState<ToneOption | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [preserveCitations, setPreserveCitations] = useState(true);
  const toolbarRef = useRef<HTMLDivElement>(null);

  const handleClickOutside = useCallback(
    (event: MouseEvent) => {
      if (
        toolbarRef.current &&
        !toolbarRef.current.contains(event.target as Node)
      ) {
        onClose();
      }
    },
    [onClose]
  );

  useEffect(() => {
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [handleClickOutside]);

  const handleRewrite = async (tone: ToneOption) => {
    setLoadingTone(tone);
    setError(null);

    try {
      const result = await rewriteText({
        text: selectedText,
        tone,
        preserve_citations: preserveCitations,
      });
      onRewrite(result);
    } catch {
      setError('Rewrite failed. Try again.');
    } finally {
      setLoadingTone(null);
    }
  };

  return (
    <div
      ref={toolbarRef}
      className="absolute z-50 flex items-center gap-1 rounded-lg border border-[#1a1a1a] bg-[#0a0a0a] px-2 py-1.5 shadow-lg shadow-black/50"
      style={{ top: position.top, left: position.left }}
    >
      {toneButtons.map(({ tone, label, icon: Icon }) => {
        const isLoading = loadingTone === tone;
        return (
          <Button
            key={tone}
            variant="ghost"
            size="sm"
            className={cn(
              'h-8 gap-1.5 px-2.5 text-xs text-gray-300 hover:bg-[#1a1a1a] hover:text-gray-100',
              isLoading && 'pointer-events-none opacity-70'
            )}
            disabled={loadingTone !== null}
            onClick={() => handleRewrite(tone)}
            aria-label={`Rewrite as ${label}`}
          >
            {isLoading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Icon className="h-3.5 w-3.5" />
            )}
            <span>{label}</span>
          </Button>
        );
      })}

      <div className="mx-1 h-5 w-px bg-[#1a1a1a]" />

      <label className="flex cursor-pointer items-center gap-1.5">
        <Checkbox
          checked={preserveCitations}
          onCheckedChange={(checked) => setPreserveCitations(checked === true)}
          className="h-3.5 w-3.5 border-gray-600 data-[state=checked]:border-[#00d4ff] data-[state=checked]:bg-[#00d4ff]"
        />
        <span className="select-none text-[10px] text-gray-500">Citations</span>
      </label>

      <div className="mx-1 h-5 w-px bg-[#1a1a1a]" />

      <Button
        variant="ghost"
        size="sm"
        className="h-7 w-7 p-0 text-gray-500 hover:bg-[#1a1a1a] hover:text-gray-300"
        onClick={onClose}
        aria-label="Close toolbar"
      >
        <X className="h-3.5 w-3.5" />
      </Button>

      {error && (
        <span className="absolute -bottom-6 left-0 whitespace-nowrap text-xs text-red-400">
          {error}
        </span>
      )}
    </div>
  );
};

export default ToneToolbar;
