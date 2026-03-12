'use client';

/**
 * ChatContextBar — "Chatting with:" label + horizontally scrollable
 * toggleable context chips with icons and tooltips.
 */

import React from 'react';
import { FileText, StickyNote, BookOpen } from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import type { ContextChip, ContextChipKind } from '@/types/chat-widget';

interface ChatContextBarProps {
  chips: ContextChip[];
  onToggleChip: (kind: ContextChipKind) => void;
  onToggleAll: (enabled: boolean) => void;
}

const CHIP_ICONS: Record<ContextChip['icon'], React.ElementType> = {
  'file-text': FileText,
  'sticky-note': StickyNote,
  'book-open': BookOpen,
};

export function ChatContextBar({
  chips,
  onToggleChip,
  onToggleAll,
}: ChatContextBarProps) {
  const allEnabled = chips.every((c) => c.active);

  return (
    <div className="px-3 py-2 border-b border-border">
      <div className="flex items-center gap-2">
        <span className="text-[11px] text-muted-foreground whitespace-nowrap shrink-0">
          Chatting with:
        </span>
        <div className="flex items-center gap-1.5 overflow-x-auto scrollbar-none">
          <TooltipProvider delayDuration={300}>
            {/* "All" bulk toggle chip */}
            <button
              onClick={() => onToggleAll(!allEnabled)}
              aria-label={
                allEnabled ? 'Disable all context' : 'Enable all context'
              }
              aria-pressed={allEnabled}
              className={`flex items-center px-2 py-1 rounded-full text-[11px] whitespace-nowrap transition-colors border ${
                allEnabled
                  ? 'bg-primary/10 text-primary border-primary/30'
                  : 'bg-muted/50 text-muted-foreground border-transparent hover:border-border'
              }`}
            >
              All
            </button>
            {chips.map((chip) => {
              const Icon = CHIP_ICONS[chip.icon];
              return (
                <Tooltip key={chip.kind}>
                  <TooltipTrigger asChild>
                    <button
                      onClick={() => onToggleChip(chip.kind)}
                      aria-label={`${chip.active ? 'Disable' : 'Enable'} ${chip.label} context`}
                      aria-pressed={chip.active}
                      className={`flex items-center gap-1 px-2 py-1 rounded-full text-[11px] whitespace-nowrap transition-colors border ${
                        chip.active
                          ? 'bg-primary/10 text-primary border-primary/30'
                          : 'bg-muted/50 text-muted-foreground border-transparent hover:border-border'
                      }`}
                    >
                      <Icon className="h-3 w-3" />
                      <span>{chip.label}</span>
                      {chip.count > 0 && (
                        <span
                          className={`ml-0.5 text-[10px] ${
                            chip.active
                              ? 'text-primary/70'
                              : 'text-muted-foreground/60'
                          }`}
                        >
                          ({chip.count})
                        </span>
                      )}
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side="bottom">
                    {chip.active ? 'Click to exclude' : 'Click to include'}{' '}
                    {chip.label.toLowerCase()} in context
                  </TooltipContent>
                </Tooltip>
              );
            })}
          </TooltipProvider>
        </div>
      </div>
    </div>
  );
}
