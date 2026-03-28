'use client';

import React, { useState, useCallback, useEffect, useRef } from 'react';
import { Loader2, Scissors, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { extractRegion } from '@/services/scispaceService';
import type { ExtractRegionResponse } from '@/types/scispace';
import { Button } from '@/components/ui/button';

interface CropExtractOverlayProps {
  documentId: string;
  pageNumber: number;
  containerRef: React.RefObject<HTMLElement | null>;
  active: boolean;
  onExtracted: (result: ExtractRegionResponse) => void;
  onCancel: () => void;
}

interface SelectionRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export const CropExtractOverlay: React.FC<CropExtractOverlayProps> = ({
  documentId,
  pageNumber,
  containerRef,
  active,
  onExtracted,
  onCancel,
}) => {
  const [startPoint, setStartPoint] = useState<{ x: number; y: number } | null>(
    null
  );
  const [currentPoint, setCurrentPoint] = useState<{
    x: number;
    y: number;
  } | null>(null);
  const [selection, setSelection] = useState<SelectionRect | null>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);
  const [selectionFinalized, setSelectionFinalized] = useState(false);
  const overlayRef = useRef<HTMLDivElement>(null);

  const resetState = useCallback(() => {
    setStartPoint(null);
    setCurrentPoint(null);
    setSelection(null);
    setIsDrawing(false);
    setSelectionFinalized(false);
    setIsExtracting(false);
  }, []);

  useEffect(() => {
    if (!active) {
      resetState();
    }
  }, [active, resetState]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && active) {
        onCancel();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [active, onCancel]);

  const getRelativePosition = useCallback(
    (e: React.MouseEvent) => {
      const container = containerRef.current;
      if (!container) return { x: 0, y: 0 };
      const rect = container.getBoundingClientRect();
      return {
        x: Math.max(0, Math.min(e.clientX - rect.left, rect.width)),
        y: Math.max(0, Math.min(e.clientY - rect.top, rect.height)),
      };
    },
    [containerRef]
  );

  const computeRect = useCallback(
    (
      p1: { x: number; y: number },
      p2: { x: number; y: number }
    ): SelectionRect => ({
      x: Math.min(p1.x, p2.x),
      y: Math.min(p1.y, p2.y),
      width: Math.abs(p2.x - p1.x),
      height: Math.abs(p2.y - p1.y),
    }),
    []
  );

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (selectionFinalized || isExtracting) return;
      e.preventDefault();
      const pos = getRelativePosition(e);
      setStartPoint(pos);
      setCurrentPoint(pos);
      setIsDrawing(true);
      setSelection(null);
    },
    [getRelativePosition, selectionFinalized, isExtracting]
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!isDrawing || !startPoint) return;
      e.preventDefault();
      const pos = getRelativePosition(e);
      setCurrentPoint(pos);
      setSelection(computeRect(startPoint, pos));
    },
    [isDrawing, startPoint, getRelativePosition, computeRect]
  );

  const handleMouseUp = useCallback(
    (e: React.MouseEvent) => {
      if (!isDrawing || !startPoint) return;
      e.preventDefault();
      const pos = getRelativePosition(e);
      const rect = computeRect(startPoint, pos);
      if (rect.width > 5 && rect.height > 5) {
        setSelection(rect);
        setSelectionFinalized(true);
      } else {
        setSelection(null);
      }
      setIsDrawing(false);
    },
    [isDrawing, startPoint, getRelativePosition, computeRect]
  );

  const handleExtract = useCallback(async () => {
    if (!selection || !containerRef.current) return;
    setIsExtracting(true);

    try {
      const container = containerRef.current;
      const containerRect = container.getBoundingClientRect();
      const scaleX = containerRect.width > 0 ? 1 : 1;
      const scaleY = containerRect.height > 0 ? 1 : 1;

      const result = await extractRegion(documentId, {
        page: pageNumber,
        x1: Math.round(selection.x * scaleX),
        y1: Math.round(selection.y * scaleY),
        x2: Math.round((selection.x + selection.width) * scaleX),
        y2: Math.round((selection.y + selection.height) * scaleY),
      });
      onExtracted(result);
      resetState();
    } catch {
      setIsExtracting(false);
    }
  }, [
    selection,
    containerRef,
    documentId,
    pageNumber,
    onExtracted,
    resetState,
  ]);

  if (!active) return null;

  const displayRect =
    selection ||
    (startPoint && currentPoint ? computeRect(startPoint, currentPoint) : null);

  return (
    <div
      ref={overlayRef}
      className="absolute inset-0 z-50 cursor-crosshair bg-black/40"
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
    >
      <div className="absolute right-2 top-2 flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={(e) => {
            e.stopPropagation();
            onCancel();
          }}
          className="h-7 gap-1.5 border-border bg-black/80 px-2.5 text-xs text-muted-foreground hover:border-red-500/30 hover:text-white"
          aria-label="Cancel crop selection"
        >
          <X className="h-3 w-3" />
          Cancel
        </Button>
      </div>

      {!selectionFinalized && !displayRect && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="rounded-lg border border-[#00d4ff]/30 bg-black/80 px-4 py-2">
            <span className="text-sm text-[#00d4ff]">
              Click and drag to select a region
            </span>
          </div>
        </div>
      )}

      {displayRect && displayRect.width > 0 && displayRect.height > 0 && (
        <>
          <div
            className="absolute border-2 border-dashed border-[#00d4ff] bg-[#00d4ff]/10"
            style={{
              left: displayRect.x,
              top: displayRect.y,
              width: displayRect.width,
              height: displayRect.height,
            }}
          >
            <span className="absolute -top-5 left-0 rounded bg-black/80 px-1.5 py-0.5 text-[10px] font-mono text-[#00d4ff]">
              ({Math.round(displayRect.x)}, {Math.round(displayRect.y)})
            </span>
            <span className="absolute -bottom-5 right-0 rounded bg-black/80 px-1.5 py-0.5 text-[10px] font-mono text-[#00d4ff]">
              ({Math.round(displayRect.x + displayRect.width)},{' '}
              {Math.round(displayRect.y + displayRect.height)})
            </span>
          </div>

          {selectionFinalized && (
            <div
              className="absolute z-10"
              style={{
                left: displayRect.x + displayRect.width - 80,
                top: displayRect.y + displayRect.height + 8,
              }}
            >
              <Button
                size="sm"
                onClick={(e) => {
                  e.stopPropagation();
                  handleExtract();
                }}
                disabled={isExtracting}
                className={cn(
                  'h-8 gap-1.5 px-3 text-xs font-medium',
                  'bg-[#00d4ff] text-black hover:bg-[#00d4ff]/80',
                  'shadow-lg shadow-[#00d4ff]/20'
                )}
                aria-label="Extract selected region"
              >
                {isExtracting ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Extracting...
                  </>
                ) : (
                  <>
                    <Scissors className="h-3.5 w-3.5" />
                    Extract
                  </>
                )}
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default CropExtractOverlay;
