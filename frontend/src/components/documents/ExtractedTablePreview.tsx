'use client';

import React, { useMemo, useCallback } from 'react';
import { X, Copy, Download, Table2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ExtractedTable, ExtractRegionResponse } from '@/types/scispace';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { MathDisplay } from './MathDisplay';

interface ExtractedTablePreviewProps {
  documentId: string;
  table?: ExtractedTable;
  regionResult?: ExtractRegionResponse;
  onClose: () => void;
}

function parseCsvToRows(csv: string): string[][] {
  return csv
    .trim()
    .split('\n')
    .map((line) => line.split(',').map((cell) => cell.trim()));
}

function parseMarkdownToRows(md: string): string[][] {
  return md
    .trim()
    .split('\n')
    .filter((line) => !line.match(/^\s*\|?\s*[-:]+[-|:\s]*$/))
    .map((line) =>
      line
        .replace(/^\|/, '')
        .replace(/\|$/, '')
        .split('|')
        .map((cell) => cell.trim())
    );
}

function rowsToCsv(rows: string[][]): string {
  return rows.map((row) => row.join(',')).join('\n');
}

function rowsToMarkdown(rows: string[][]): string {
  if (rows.length === 0) return '';
  const header = `| ${rows[0].join(' | ')} |`;
  const separator = `| ${rows[0].map(() => '---').join(' | ')} |`;
  const body = rows
    .slice(1)
    .map((row) => `| ${row.join(' | ')} |`)
    .join('\n');
  return [header, separator, body].join('\n');
}

export const ExtractedTablePreview: React.FC<ExtractedTablePreviewProps> = ({
  documentId,
  table,
  regionResult,
  onClose,
}) => {
  const rows = useMemo<string[][]>(() => {
    if (table) return table.rows;
    if (!regionResult) return [];

    if (regionResult.format === 'csv') {
      return parseCsvToRows(regionResult.content);
    }
    if (regionResult.format === 'markdown') {
      return parseMarkdownToRows(regionResult.content);
    }
    return [];
  }, [table, regionResult]);

  const isLatex = regionResult?.format === 'latex';
  const pageNumber = table?.page ?? regionResult?.page;
  const method = table?.method ?? (regionResult ? 'region-extract' : undefined);

  const handleCopyCsv = useCallback(() => {
    const csv = rowsToCsv(rows);
    navigator.clipboard.writeText(csv);
  }, [rows]);

  const handleCopyMarkdown = useCallback(() => {
    const md = rowsToMarkdown(rows);
    navigator.clipboard.writeText(md);
  }, [rows]);

  const handleDownloadCsv = useCallback(() => {
    const csv = rowsToCsv(rows);
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `table-${documentId}-page${pageNumber ?? 0}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }, [rows, documentId, pageNumber]);

  return (
    <div className="rounded-lg border border-border bg-black/30 p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Table2 className="h-4 w-4 text-brand-cyan" />
          <span className="text-sm font-medium text-muted-foreground">
            Table from page {pageNumber ?? '?'}
          </span>
          {regionResult && (
            <Badge
              className={cn(
                'border-transparent text-xs',
                regionResult.confidence >= 0.8
                  ? 'bg-sol/10 text-sol'
                  : regionResult.confidence >= 0.5
                    ? 'bg-helios/10 text-helios'
                    : 'bg-red-500/10 text-red-400'
              )}
            >
              {Math.round(regionResult.confidence * 100)}% confidence
            </Badge>
          )}
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={onClose}
          className="h-7 w-7 text-muted-foreground hover:text-white"
          aria-label="Close table preview"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>

      {isLatex ? (
        <div className="my-3 rounded-lg border border-border bg-black/50 p-4">
          <MathDisplay content={regionResult!.content} format="latex" block />
        </div>
      ) : (
        <div className="overflow-auto rounded-lg border border-border">
          <Table>
            <TableHeader>
              {rows.length > 0 && (
                <TableRow className="border-border hover:bg-transparent">
                  {rows[0].map((cell, i) => (
                    <TableHead
                      key={i}
                      className="bg-black/50 text-xs font-semibold text-brand-cyan"
                    >
                      {cell}
                    </TableHead>
                  ))}
                </TableRow>
              )}
            </TableHeader>
            <TableBody>
              {rows.slice(1).map((row, ri) => (
                <TableRow key={ri} className="border-border hover:bg-white/5">
                  {row.map((cell, ci) => (
                    <TableCell
                      key={ci}
                      className="text-xs text-muted-foreground"
                    >
                      {cell}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <div className="mt-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {!isLatex && (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={handleCopyCsv}
                className="h-7 gap-1.5 border-border bg-transparent px-2.5 text-xs text-muted-foreground hover:border-brand-cyan/30 hover:text-white"
              >
                <Copy className="h-3 w-3" />
                Copy CSV
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleCopyMarkdown}
                className="h-7 gap-1.5 border-border bg-transparent px-2.5 text-xs text-muted-foreground hover:border-brand-cyan/30 hover:text-white"
              >
                <Copy className="h-3 w-3" />
                Copy Markdown
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleDownloadCsv}
                className="h-7 gap-1.5 border-border bg-transparent px-2.5 text-xs text-muted-foreground hover:border-brand-cyan/30 hover:text-white"
              >
                <Download className="h-3 w-3" />
                Download CSV
              </Button>
            </>
          )}
        </div>
        {method && (
          <Badge
            className="border-border bg-black/50 text-xs text-muted-foreground"
            variant="outline"
          >
            {method}
          </Badge>
        )}
      </div>
    </div>
  );
};

export default ExtractedTablePreview;
