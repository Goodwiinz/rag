'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Wand2, LayoutList, ListTree, X, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { writeText } from '@/services/scispaceService';
import type { WriteResponse } from '@/types/scispace';

interface WriterToolbarProps {
  cursorContext: string;
  position: { top: number; left: number };
  documentIds?: string[];
  onInsert: (result: WriteResponse) => void;
  onOutlineRequest: () => void;
  onClose: () => void;
}

type WriterButton = {
  action: 'complete' | 'generate_section' | 'outline';
  label: string;
  icon: React.ElementType;
};

const writerButtons: WriterButton[] = [
  { action: 'complete', label: 'Complete', icon: Wand2 },
  { action: 'generate_section', label: 'Section', icon: LayoutList },
  { action: 'outline', label: 'Outline', icon: ListTree },
];

export const WriterToolbar: React.FC<WriterToolbarProps> = ({
  cursorContext,
  position,
  documentIds,
  onInsert,
  onOutlineRequest,
  onClose,
}) => {
  const [loadingAction, setLoadingAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
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

  const handleAction = async (action: WriterButton['action']) => {
    if (action === 'outline') {
      onOutlineRequest();
      return;
    }

    setLoadingAction(action);
    setError(null);

    try {
      const result = await writeText({
        action,
        cursor_context: cursorContext,
        document_ids: documentIds,
      });
      onInsert(result);
    } catch {
      setError('Generation failed. Try again.');
    } finally {
      setLoadingAction(null);
    }
  };

  return (
    <div
      ref={toolbarRef}
      className="absolute z-50 flex items-center gap-1 rounded-lg border border-[#1a1a1a] bg-[#0a0a0a] px-2 py-1.5 shadow-lg shadow-black/50"
      style={{ top: position.top, left: position.left }}
    >
      {writerButtons.map(({ action, label, icon: Icon }) => {
        const isLoading = loadingAction === action;
        return (
          <Button
            key={action}
            variant="ghost"
            size="sm"
            className={cn(
              'h-8 gap-1.5 px-2.5 text-xs text-gray-300 hover:bg-[#1a1a1a] hover:text-gray-100',
              isLoading && 'pointer-events-none opacity-70'
            )}
            disabled={loadingAction !== null}
            onClick={() => handleAction(action)}
            aria-label={`${label} text`}
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

export default WriterToolbar;
