'use client';

import React from 'react';
import { Table2, Crop, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { ExtractedTablePreview } from '@/components/documents/ExtractedTablePreview';
import { CropExtractOverlay } from '@/components/documents/CropExtractOverlay';
import type { ExtractedTable, ExtractRegionResponse } from '@/types/scispace';

interface DocumentTablesTabProps {
  isPdf: boolean;
  isIndexed: boolean;
  tables: ExtractedTable[];
  tablesLoading: boolean;
  regionResult: ExtractRegionResponse | null;
  cropActive: boolean;
  tablesContainerRef: React.RefObject<HTMLDivElement | null>;
  documentId: string;
  onFetchTables: () => void;
  onSetTables: React.Dispatch<React.SetStateAction<ExtractedTable[]>>;
  onSetRegionResult: React.Dispatch<React.SetStateAction<ExtractRegionResponse | null>>;
  onSetCropActive: React.Dispatch<React.SetStateAction<boolean>>;
}

export function DocumentTablesTab({
  isPdf,
  isIndexed,
  tables,
  tablesLoading,
  regionResult,
  cropActive,
  tablesContainerRef,
  documentId,
  onFetchTables,
  onSetTables,
  onSetRegionResult,
  onSetCropActive,
}: DocumentTablesTabProps) {
  return (
    <div ref={tablesContainerRef as React.Ref<HTMLDivElement>} className="py-6 space-y-6 relative">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h3 className="text-sm font-medium text-foreground flex items-center gap-2">
          <Table2 aria-hidden="true" className="w-4 h-4 text-primary" />
          Extracted tables and formulas
        </h3>
        {isPdf && (
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => onSetCropActive(true)}
              className="px-3 py-1.5 rounded-lg text-xs font-medium border border-border bg-card text-muted-foreground hover:text-foreground hover:bg-muted transition-colors inline-flex items-center gap-2 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            >
              <Crop aria-hidden="true" className="w-3.5 h-3.5" />
              Crop extract
            </button>
            <button
              type="button"
              onClick={onFetchTables}
              disabled={tablesLoading || !isIndexed}
              title={!isIndexed ? 'Tables can be extracted once the document is indexed' : undefined}
              className={cn(
                'px-3 py-1.5 rounded-lg text-xs font-medium inline-flex items-center gap-2 transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
                tablesLoading || !isIndexed
                  ? 'bg-muted text-muted-foreground cursor-not-allowed'
                  : 'bg-primary/10 border border-primary/30 text-primary hover:bg-primary/20'
              )}
            >
              {tablesLoading ? (
                <Loader2 aria-hidden="true" className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Table2 aria-hidden="true" className="w-3.5 h-3.5" />
              )}
              {tablesLoading ? 'Extracting\u2026' : 'Extract tables'}
            </button>
          </div>
        )}
      </div>

      {isPdf ? (
        <>
          {regionResult && (
            <div>
              <h4 className="text-xs font-medium text-muted-foreground mb-2">
                Crop extraction result
              </h4>
              <ExtractedTablePreview
                documentId={documentId}
                regionResult={regionResult}
                onClose={() => onSetRegionResult(null)}
              />
            </div>
          )}

          {tablesLoading ? (
            <div className="space-y-4">
              <div className="h-40 rounded-lg border border-border bg-card animate-pulse" />
              <div className="h-40 rounded-lg border border-border bg-card animate-pulse" />
              <span className="sr-only" role="status">Extracting tables\u2026</span>
            </div>
          ) : tables.length > 0 ? (
            <div className="space-y-4">
              {tables.map((table, idx) => (
                <ExtractedTablePreview
                  key={idx}
                  documentId={documentId}
                  table={table}
                  onClose={() => onSetTables((prev) => prev.filter((_, i) => i !== idx))}
                />
              ))}
            </div>
          ) : (
            <div className="text-center py-12 rounded-xl border border-dashed border-border bg-card/50">
              <Table2 aria-hidden="true" className="w-10 h-10 text-muted-foreground mx-auto mb-4" />
              <p className="text-sm font-medium text-foreground mb-1">No tables yet</p>
              <p className="text-xs text-muted-foreground">
                {isIndexed
                  ? 'Run extraction to find tables in this document.'
                  : 'Tables become available once the document is indexed.'}
              </p>
            </div>
          )}

          <CropExtractOverlay
            active={cropActive}
            pageNumber={1}
            documentId={documentId}
            containerRef={tablesContainerRef}
            onCancel={() => onSetCropActive(false)}
            onExtracted={(data) => {
              onSetRegionResult(data);
              onSetCropActive(false);
            }}
          />
        </>
      ) : (
        <div className="text-center py-12 rounded-xl border border-dashed border-border bg-card/50">
          <Table2 aria-hidden="true" className="w-10 h-10 text-muted-foreground mx-auto mb-4" />
          <p className="text-sm font-medium text-foreground mb-1">Table extraction needs a PDF</p>
          <p className="text-xs text-muted-foreground">Upload a PDF document to use this feature.</p>
        </div>
      )}
    </div>
  );
}
