'use client';

import { useState } from 'react';
import { ArrowDown, ArrowUp, Plus, X } from 'lucide-react';
import type { ExtractionColumn } from '@/types/scispace';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';

const PRESET_COLUMNS: ExtractionColumn[] = [
  {
    name: 'Methodology',
    description: 'Research methodology used in the study',
  },
  { name: 'Sample Size', description: 'Number of participants or data points' },
  { name: 'Key Findings', description: 'Primary results and conclusions' },
  { name: 'Limitations', description: 'Study limitations and constraints' },
  { name: 'Year', description: 'Year of publication' },
  { name: 'Participants', description: 'Description of study participants' },
];

interface ColumnEditorProps {
  columns: ExtractionColumn[];
  onChange: (columns: ExtractionColumn[]) => void;
  maxColumns?: number;
}

export function ColumnEditor({
  columns,
  onChange,
  maxColumns = 20,
}: ColumnEditorProps) {
  const [presetOpen, setPresetOpen] = useState(false);

  const updateColumn = (
    index: number,
    field: keyof ExtractionColumn,
    value: string
  ) => {
    const next = columns.map((col, i) =>
      i === index ? { ...col, [field]: value } : col
    );
    onChange(next);
  };

  const addColumn = () => {
    if (columns.length >= maxColumns) return;
    onChange([...columns, { name: '', description: '' }]);
  };

  const removeColumn = (index: number) => {
    if (columns.length <= 1) return;
    onChange(columns.filter((_, i) => i !== index));
  };

  const moveColumn = (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= columns.length) return;
    const next = [...columns];
    [next[index], next[target]] = [next[target], next[index]];
    onChange(next);
  };

  const addPreset = (preset: ExtractionColumn) => {
    if (columns.length >= maxColumns) return;
    const exists = columns.some(
      (col) => col.name.toLowerCase() === preset.name.toLowerCase()
    );
    if (exists) return;
    onChange([...columns, { ...preset }]);
    setPresetOpen(false);
  };

  return (
    <div className="space-y-3">
      <Label className="text-xs text-muted-foreground">
        Extraction columns
      </Label>

      <div className="space-y-2">
        {columns.map((col, index) => (
          <div
            key={index}
            className="flex items-start gap-2 rounded-md border border-border bg-muted/50 p-3"
          >
            <div className="flex flex-col gap-1">
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 text-muted-foreground hover:text-primary"
                disabled={index === 0}
                onClick={() => moveColumn(index, -1)}
                aria-label="Move column up"
              >
                <ArrowUp className="h-3 w-3" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 text-muted-foreground hover:text-primary"
                disabled={index === columns.length - 1}
                onClick={() => moveColumn(index, 1)}
                aria-label="Move column down"
              >
                <ArrowDown className="h-3 w-3" />
              </Button>
            </div>

            <div className="flex-1 space-y-1.5">
              <Input
                value={col.name}
                onChange={(e) => updateColumn(index, 'name', e.target.value)}
                placeholder="Column name"
                className="h-8 bg-background border-border text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring"
              />
              <Input
                value={col.description ?? ''}
                onChange={(e) =>
                  updateColumn(index, 'description', e.target.value)
                }
                placeholder="Description (optional)"
                className="h-8 bg-background border-border text-xs text-foreground placeholder:text-muted-foreground focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring"
              />
            </div>

            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 text-muted-foreground hover:text-red-400"
              disabled={columns.length <= 1}
              onClick={() => removeColumn(index)}
              aria-label="Remove column"
            >
              <X className="h-3 w-3" />
            </Button>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          className="border-primary/30 text-primary hover:bg-primary/10 text-xs"
          disabled={columns.length >= maxColumns}
          onClick={addColumn}
        >
          <Plus className="h-3 w-3 mr-1" />
          Add Column
        </Button>

        <DropdownMenu open={presetOpen} onOpenChange={setPresetOpen}>
          <DropdownMenuTrigger asChild>
            <Button
              variant="outline"
              size="sm"
              className="border-primary/30 text-primary hover:bg-primary/10 text-xs"
              disabled={columns.length >= maxColumns}
            >
              Add Preset
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="bg-popover border-border"
            align="start"
          >
            {PRESET_COLUMNS.map((preset) => {
              const exists = columns.some(
                (col) => col.name.toLowerCase() === preset.name.toLowerCase()
              );
              return (
                <DropdownMenuItem
                  key={preset.name}
                  disabled={exists}
                  onClick={() => addPreset(preset)}
                  className={cn(
                    'text-xs cursor-pointer',
                    exists ? 'text-foreground' : 'text-muted-foreground'
                  )}
                >
                  {preset.name}
                  {exists && (
                    <span className="ml-auto text-[10px] text-foreground">
                      added
                    </span>
                  )}
                </DropdownMenuItem>
              );
            })}
          </DropdownMenuContent>
        </DropdownMenu>

        <span className="ml-auto text-[10px] text-foreground">
          {columns.length}/{maxColumns}
        </span>
      </div>
    </div>
  );
}

export default ColumnEditor;
