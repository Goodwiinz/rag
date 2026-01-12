'use client';

/**
 * Export Dialog Component
 * 
 * Modal dialog for exporting threads in various formats.
 * Supports single and batch export with customizable options.
 */

import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Loader2, Download, FileText, FileJson, FileCode, File } from 'lucide-react';
import {
  exportThread,
  exportBatch,
  previewExport,
  formatFileSize,
  ExportFormat,
  ExportOptions,
  ExportPreview,
} from '@/services/export-service';

interface ExportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  threadIds: string[];
  threadTitle?: string;
}

const FORMAT_ICONS: Record<ExportFormat, React.ElementType> = {
  markdown: FileText,
  html: FileCode,
  json: FileJson,
  pdf: File,
};

const FORMAT_LABELS: Record<ExportFormat, string> = {
  markdown: 'Markdown (.md)',
  html: 'HTML (.html)',
  json: 'JSON (.json)',
  pdf: 'PDF (.pdf)',
};

export function ExportDialog({
  open,
  onOpenChange,
  threadIds,
  threadTitle,
}: ExportDialogProps) {
  const [format, setFormat] = useState<ExportFormat>('markdown');
  const [options, setOptions] = useState<ExportOptions>({
    includeSystemMessages: false,
    includeCitations: true,
    includeMetadata: true,
    includeFeedback: false,
  });
  const [preview, setPreview] = useState<ExportPreview | null>(null);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isBatch = threadIds.length > 1;

  // Load preview when dialog opens or format changes
  useEffect(() => {
    if (open && threadIds.length === 1) {
      setLoading(true);
      setError(null);
      previewExport(threadIds[0], format)
        .then(setPreview)
        .catch((err) => setError(err.message))
        .finally(() => setLoading(false));
    }
  }, [open, threadIds, format]);

  const handleExport = async () => {
    setExporting(true);
    setError(null);

    try {
      if (isBatch) {
        await exportBatch({
          threadIds,
          format,
          options,
          asZip: true,
        });
      } else {
        await exportThread(threadIds[0], format, options);
      }
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed');
    } finally {
      setExporting(false);
    }
  };

  const FormatIcon = FORMAT_ICONS[format];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px] bg-[#141414] border-[#333] text-[#e4e4e7]">
        <DialogHeader>
          <DialogTitle className="text-[#00ff9f] flex items-center gap-2">
            <Download className="h-5 w-5" />
            Export {isBatch ? `${threadIds.length} Threads` : 'Thread'}
          </DialogTitle>
          <DialogDescription className="text-[#a1a1aa]">
            {isBatch
              ? 'Export selected threads as a ZIP archive.'
              : threadTitle || 'Export this thread to a file.'}
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-4">
          {/* Format Selection */}
          <div className="grid gap-2">
            <Label htmlFor="format" className="text-[#e4e4e7]">
              Format
            </Label>
            <Select value={format} onValueChange={(v) => setFormat(v as ExportFormat)}>
              <SelectTrigger className="bg-[#0a0a0a] border-[#333] text-[#e4e4e7]">
                <SelectValue>
                  <span className="flex items-center gap-2">
                    <FormatIcon className="h-4 w-4 text-[#00d4ff]" />
                    {FORMAT_LABELS[format]}
                  </span>
                </SelectValue>
              </SelectTrigger>
              <SelectContent className="bg-[#141414] border-[#333]">
                {(Object.keys(FORMAT_LABELS) as ExportFormat[]).map((fmt) => {
                  const Icon = FORMAT_ICONS[fmt];
                  return (
                    <SelectItem
                      key={fmt}
                      value={fmt}
                      className="text-[#e4e4e7] focus:bg-[#1a1a1a] focus:text-[#00ff9f]"
                    >
                      <span className="flex items-center gap-2">
                        <Icon className="h-4 w-4" />
                        {FORMAT_LABELS[fmt]}
                      </span>
                    </SelectItem>
                  );
                })}
              </SelectContent>
            </Select>
          </div>

          {/* Preview Stats */}
          {!isBatch && preview && (
            <div className="rounded-lg bg-[#0a0a0a] border border-[#333] p-3 text-sm">
              <div className="grid grid-cols-2 gap-2 text-[#a1a1aa]">
                <span>Messages:</span>
                <span className="text-[#e4e4e7]">{preview.messageCount}</span>
                <span>Citations:</span>
                <span className="text-[#e4e4e7]">{preview.citationCount}</span>
                <span>Est. Size:</span>
                <span className="text-[#00d4ff]">
                  {formatFileSize(preview.estimatedSizeBytes)}
                </span>
              </div>
            </div>
          )}

          {/* Export Options */}
          <div className="space-y-3">
            <Label className="text-[#e4e4e7]">Options</Label>
            
            <div className="flex items-center justify-between">
              <Label htmlFor="citations" className="text-sm text-[#a1a1aa]">
                Include citations
              </Label>
              <Switch
                id="citations"
                checked={options.includeCitations}
                onCheckedChange={(checked) =>
                  setOptions({ ...options, includeCitations: checked })
                }
                className="data-[state=checked]:bg-[#00ff9f]"
              />
            </div>

            <div className="flex items-center justify-between">
              <Label htmlFor="metadata" className="text-sm text-[#a1a1aa]">
                Include metadata (timestamps, model info)
              </Label>
              <Switch
                id="metadata"
                checked={options.includeMetadata}
                onCheckedChange={(checked) =>
                  setOptions({ ...options, includeMetadata: checked })
                }
                className="data-[state=checked]:bg-[#00ff9f]"
              />
            </div>

            <div className="flex items-center justify-between">
              <Label htmlFor="system" className="text-sm text-[#a1a1aa]">
                Include system messages
              </Label>
              <Switch
                id="system"
                checked={options.includeSystemMessages}
                onCheckedChange={(checked) =>
                  setOptions({ ...options, includeSystemMessages: checked })
                }
                className="data-[state=checked]:bg-[#00ff9f]"
              />
            </div>

            <div className="flex items-center justify-between">
              <Label htmlFor="feedback" className="text-sm text-[#a1a1aa]">
                Include feedback ratings
              </Label>
              <Switch
                id="feedback"
                checked={options.includeFeedback}
                onCheckedChange={(checked) =>
                  setOptions({ ...options, includeFeedback: checked })
                }
                className="data-[state=checked]:bg-[#00ff9f]"
              />
            </div>
          </div>

          {/* Error Display */}
          {error && (
            <div className="rounded-lg bg-red-500/10 border border-red-500/30 p-3 text-sm text-red-400">
              {error}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            className="border-[#333] text-[#a1a1aa] hover:bg-[#1a1a1a] hover:text-[#e4e4e7]"
          >
            Cancel
          </Button>
          <Button
            onClick={handleExport}
            disabled={exporting || loading}
            className="bg-[#00ff9f] text-[#0a0a0a] hover:bg-[#00ff9f]/90"
          >
            {exporting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Exporting...
              </>
            ) : (
              <>
                <Download className="mr-2 h-4 w-4" />
                Export
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default ExportDialog;
