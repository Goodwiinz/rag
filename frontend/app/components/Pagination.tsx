'use client';

import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { IconButton } from '@/components/ui/icon-button';

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  pageSize: number;
  totalItems: number;
  onPageChange: (page: number) => void;
  onPageSizeChange?: (pageSize: number) => void;
  className?: string;
}

export function Pagination({
  currentPage,
  totalPages,
  pageSize,
  totalItems,
  onPageChange,
  onPageSizeChange,
  className,
}: PaginationProps) {
  // Generate page numbers to display
  const getPageNumbers = () => {
    const pages = [];
    const maxVisiblePages = 5;
    
    if (totalPages <= maxVisiblePages) {
      for (let i = 1; i <= totalPages; i++) pages.push(i);
    } else {
      if (currentPage <= 3) {
        for (let i = 1; i <= 4; i++) pages.push(i);
        pages.push('...');
        pages.push(totalPages);
      } else if (currentPage >= totalPages - 2) {
        pages.push(1);
        pages.push('...');
        for (let i = totalPages - 3; i <= totalPages; i++) pages.push(i);
      } else {
        pages.push(1);
        pages.push('...');
        for (let i = currentPage - 1; i <= currentPage + 1; i++) pages.push(i);
        pages.push('...');
        pages.push(totalPages);
      }
    }
    return pages;
  };

  if (totalPages <= 1) return null;

  return (
    <div className={cn("flex flex-col sm:flex-row items-center justify-between gap-4 py-4", className)}>
      <div className="flex items-center gap-2 text-xs font-mono text-[var(--terminal-text-dim)]">
        <span>SHOWING</span>
        <span className="text-[var(--terminal-text)] font-bold">
          {Math.min((currentPage - 1) * pageSize + 1, totalItems)}
        </span>
        <span>TO</span>
        <span className="text-[var(--terminal-text)] font-bold">
          {Math.min(currentPage * pageSize, totalItems)}
        </span>
        <span>OF</span>
        <span className="text-[var(--terminal-text)] font-bold">{totalItems}</span>
      </div>

      <div className="flex items-center gap-2">
        <IconButton
          onClick={() => onPageChange(1)}
          disabled={currentPage === 1}
          className="p-2 h-auto w-auto rounded-lg border border-[var(--terminal-border)] hover:bg-[var(--terminal-surface)] disabled:opacity-30 disabled:hover:bg-transparent transition-all"
          label="First Page"
          icon={<ChevronsLeft className="w-4 h-4 text-[var(--terminal-text)]" />}
        />
        
        <IconButton
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage === 1}
          className="p-2 h-auto w-auto rounded-lg border border-[var(--terminal-border)] hover:bg-[var(--terminal-surface)] disabled:opacity-30 disabled:hover:bg-transparent transition-all"
          label="Previous Page"
          icon={<ChevronLeft className="w-4 h-4 text-[var(--terminal-text)]" />}
        />

        <div className="flex items-center gap-1 bg-[var(--terminal-surface)] rounded-lg border border-[var(--terminal-border)] p-1">
          {getPageNumbers().map((page, idx) => (
            page === '...' ? (
              <span key={`ellipsis-${idx}`} className="px-2 text-[var(--terminal-text-dim)]">...</span>
            ) : (
              <button
                key={page}
                onClick={() => onPageChange(page as number)}
                className={cn(
                  "min-w-[32px] h-8 rounded-md font-mono text-xs font-bold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--phosphor-green)]",
                  currentPage === page
                    ? "bg-[var(--phosphor-green)] text-[var(--terminal-bg)] shadow-[0_0_10px_var(--phosphor-green-glow)]"
                    : "text-[var(--terminal-text-dim)] hover:text-[var(--terminal-text)] hover:bg-[var(--terminal-elevated)]"
                )}
              >
                {page}
              </button>
            )
          ))}
        </div>

        <IconButton
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage === totalPages}
          className="p-2 h-auto w-auto rounded-lg border border-[var(--terminal-border)] hover:bg-[var(--terminal-surface)] disabled:opacity-30 disabled:hover:bg-transparent transition-all"
          label="Next Page"
          icon={<ChevronRight className="w-4 h-4 text-[var(--terminal-text)]" />}
        />

        <IconButton
          onClick={() => onPageChange(totalPages)}
          disabled={currentPage === totalPages}
          className="p-2 h-auto w-auto rounded-lg border border-[var(--terminal-border)] hover:bg-[var(--terminal-surface)] disabled:opacity-30 disabled:hover:bg-transparent transition-all"
          label="Last Page"
          icon={<ChevronsRight className="w-4 h-4 text-[var(--terminal-text)]" />}
        />
      </div>
    </div>
  );
}
