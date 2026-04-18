'use client';

import { FileText, Globe, HeartPulse, Search, Database } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import type { SourceConnectorType } from '@/types/scispace';
import { cn } from '@/lib/utils';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Checkbox } from '@/components/ui/checkbox';

interface SourceDefinition {
  id: SourceConnectorType;
  label: string;
  icon: LucideIcon;
}

const SOURCES: SourceDefinition[] = [
  { id: 'arxiv', label: 'ArXiv Preprints', icon: FileText },
  { id: 'semantic_scholar', label: 'Semantic Scholar', icon: Search },
  { id: 'crossref', label: 'Crossref', icon: Globe },
  { id: 'pubmed', label: 'PubMed', icon: HeartPulse },
];

export interface SourceSelectorProps {
  selected: SourceConnectorType[];
  onChange: (sources: SourceConnectorType[]) => void;
  disabled?: boolean;
}

export function SourceSelector({
  selected,
  onChange,
  disabled = false,
}: SourceSelectorProps) {
  const handleToggle = (id: SourceConnectorType) => {
    if (selected.includes(id)) {
      if (selected.length <= 1) return;
      onChange(selected.filter((s) => s !== id));
    } else {
      onChange([...selected, id]);
    }
  };

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          disabled={disabled}
          className={cn(
            'flex items-center gap-2 px-3 py-1.5 rounded border text-xs font-mono transition-colors',
            'bg-black/30 border-[#1a1a1a] text-gray-300',
            'hover:bg-white/5 hover:border-brand-cyan/40',
            'disabled:opacity-50 disabled:cursor-not-allowed'
          )}
        >
          <Database className="h-3.5 w-3.5 text-brand-cyan" />
          <span>Sources ({selected.length})</span>
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className="w-56 bg-[#0a0a0a] border-[#1a1a1a] p-2"
      >
        <div className="space-y-1">
          {SOURCES.map((source) => {
            const isSelected = selected.includes(source.id);
            const isLastSelected = isSelected && selected.length <= 1;

            return (
              <button
                key={source.id}
                onClick={() => handleToggle(source.id)}
                disabled={isLastSelected}
                className={cn(
                  'flex items-center gap-2.5 w-full px-2.5 py-2 rounded text-left text-sm font-mono transition-colors',
                  isSelected
                    ? 'text-gray-200 bg-white/5'
                    : 'text-gray-500 hover:bg-white/5 hover:text-gray-300',
                  isLastSelected && 'cursor-not-allowed opacity-60'
                )}
              >
                <Checkbox
                  checked={isSelected}
                  onCheckedChange={() => handleToggle(source.id)}
                  disabled={isLastSelected}
                  className={cn(
                    'h-3.5 w-3.5 rounded-sm border',
                    isSelected
                      ? 'border-brand-cyan data-[state=checked]:bg-brand-cyan data-[state=checked]:text-black'
                      : 'border-[#333]'
                  )}
                  onClick={(e) => e.stopPropagation()}
                />
                <source.icon
                  className={cn(
                    'h-3.5 w-3.5 shrink-0',
                    isSelected ? 'text-brand-cyan' : 'text-gray-600'
                  )}
                />
                <span className="truncate">{source.label}</span>
              </button>
            );
          })}
        </div>
      </PopoverContent>
    </Popover>
  );
}

export default SourceSelector;
