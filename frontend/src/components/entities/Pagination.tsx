/**
 * Pagination Component
 * Terminal Observatory themed pagination controls
 */

import React from 'react';
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  pageSize: number;
  totalItems: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
  pageSizeOptions?: number[];
}

export const Pagination: React.FC<PaginationProps> = ({
  currentPage,
  totalPages,
  pageSize,
  totalItems,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [25, 50, 100, 200],
}) => {
  const startItem = (currentPage - 1) * pageSize + 1;
  const endItem = Math.min(currentPage * pageSize, totalItems);

  const canGoPrevious = currentPage > 1;
  const canGoNext = currentPage < totalPages;

  // Generate page numbers to display
  const getPageNumbers = (): (number | 'ellipsis')[] => {
    const pages: (number | 'ellipsis')[] = [];
    const maxVisiblePages = 5;

    if (totalPages <= maxVisiblePages) {
      // Show all pages if total is small
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i);
      }
    } else {
      // Always show first page
      pages.push(1);

      if (currentPage > 3) {
        pages.push('ellipsis');
      }

      // Show pages around current page
      const start = Math.max(2, currentPage - 1);
      const end = Math.min(totalPages - 1, currentPage + 1);

      for (let i = start; i <= end; i++) {
        pages.push(i);
      }

      if (currentPage < totalPages - 2) {
        pages.push('ellipsis');
      }

      // Always show last page
      if (totalPages > 1) {
        pages.push(totalPages);
      }
    }

    return pages;
  };

  if (totalItems === 0) return null;

  return (
    <div className="flex items-center justify-between px-6 py-3 border-t border-[var(--terminal-border)] bg-[var(--terminal-bg)]/50">
      {/* Left: Page size selector */}
      <div className="flex items-center gap-3">
        <span
          id="rows-per-page-label"
          className="text-[10px] font-mono text-[var(--terminal-text-muted)] uppercase tracking-widest"
        >
          Rows:
        </span>
        <Select
          value={pageSize.toString()}
          onValueChange={(value) => onPageSizeChange(parseInt(value))}
        >
          <SelectTrigger
            aria-labelledby="rows-per-page-label"
            className="w-20 h-8 bg-[var(--terminal-bg)] border-[var(--terminal-border)] font-mono text-xs"
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent className="bg-[var(--terminal-surface)] border-[var(--terminal-border)]">
            {pageSizeOptions.map((size) => (
              <SelectItem
                key={size}
                value={size.toString()}
                className="font-mono text-xs focus:bg-[var(--terminal-elevated)]"
              >
                {size}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Center: Page info */}
      <div className="text-[10px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-widest">
        Showing {startItem.toLocaleString()}-{endItem.toLocaleString()} of{' '}
        {totalItems.toLocaleString()} Records
      </div>

      {/* Right: Page navigation */}
      <div className="flex items-center gap-1">
        {/* First page */}
        <Button
          variant="ghost"
          size="icon"
          onClick={() => onPageChange(1)}
          disabled={!canGoPrevious}
          aria-label="Go to first page"
          className="h-8 w-8 text-[var(--terminal-text-dim)] hover:text-[var(--phosphor-green)] hover:bg-[var(--phosphor-green)]/10 disabled:opacity-30"
        >
          <ChevronsLeft className="h-4 w-4" />
        </Button>

        {/* Previous page */}
        <Button
          variant="ghost"
          size="icon"
          onClick={() => onPageChange(currentPage - 1)}
          disabled={!canGoPrevious}
          aria-label="Go to previous page"
          className="h-8 w-8 text-[var(--terminal-text-dim)] hover:text-[var(--phosphor-green)] hover:bg-[var(--phosphor-green)]/10 disabled:opacity-30"
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>

        {/* Page numbers */}
        <div className="flex items-center gap-1 mx-2">
          {getPageNumbers().map((page, index) =>
            page === 'ellipsis' ? (
              <span
                key={`ellipsis-${index}`}
                className="px-2 text-[var(--terminal-text-dim)] font-mono text-xs"
              >
                ...
              </span>
            ) : (
              <Button
                key={page}
                variant="ghost"
                size="sm"
                onClick={() => onPageChange(page)}
                aria-label={`Page ${page}`}
                aria-current={page === currentPage ? 'page' : undefined}
                className={cn(
                  'h-8 w-8 font-mono text-xs',
                  page === currentPage
                    ? 'bg-[var(--phosphor-green)]/20 text-[var(--phosphor-green)] border border-[var(--phosphor-green)]/30'
                    : 'text-[var(--terminal-text-dim)] hover:text-[var(--phosphor-green)] hover:bg-[var(--phosphor-green)]/10'
                )}
              >
                {page}
              </Button>
            )
          )}
        </div>

        {/* Next page */}
        <Button
          variant="ghost"
          size="icon"
          onClick={() => onPageChange(currentPage + 1)}
          disabled={!canGoNext}
          aria-label="Go to next page"
          className="h-8 w-8 text-[var(--terminal-text-dim)] hover:text-[var(--phosphor-green)] hover:bg-[var(--phosphor-green)]/10 disabled:opacity-30"
        >
          <ChevronRight className="h-4 w-4" />
        </Button>

        {/* Last page */}
        <Button
          variant="ghost"
          size="icon"
          onClick={() => onPageChange(totalPages)}
          disabled={!canGoNext}
          aria-label="Go to last page"
          className="h-8 w-8 text-[var(--terminal-text-dim)] hover:text-[var(--phosphor-green)] hover:bg-[var(--phosphor-green)]/10 disabled:opacity-30"
        >
          <ChevronsRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
};
