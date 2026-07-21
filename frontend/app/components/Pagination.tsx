'use client';

import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react';
import { cn } from '@/lib/utils';

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
      <div className="flex items-center gap-2 text-xs font-mono text-(--nous-fg-3)">
        <span>SHOWING</span>
        <span className="text-(--nous-fg-1) font-bold">
          {Math.min((currentPage - 1) * pageSize + 1, totalItems)}
        </span>
        <span>TO</span>
        <span className="text-(--nous-fg-1) font-bold">
          {Math.min(currentPage * pageSize, totalItems)}
        </span>
        <span>OF</span>
        <span className="text-(--nous-fg-1) font-bold">{totalItems}</span>
      </div>

      <nav aria-label="Pagination" className="flex items-center gap-2">
        <button
          onClick={() => onPageChange(1)}
          disabled={currentPage === 1}
          className="p-2 rounded-lg border border-(--nous-border-1) hover:bg-(--nous-bg-2) disabled:opacity-30 disabled:hover:bg-transparent transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]"
          title="First Page"
          aria-label="First Page"
        >
          <ChevronsLeft className="w-4 h-4 text-(--nous-fg-1)" />
        </button>
        
        <button
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage === 1}
          className="p-2 rounded-lg border border-(--nous-border-1) hover:bg-(--nous-bg-2) disabled:opacity-30 disabled:hover:bg-transparent transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]"
          title="Previous Page"
          aria-label="Previous Page"
        >
          <ChevronLeft className="w-4 h-4 text-(--nous-fg-1)" />
        </button>

        <div className="flex items-center gap-1 bg-(--nous-bg-2) rounded-lg border border-(--nous-border-1) p-1">
          {getPageNumbers().map((page, idx) => (
            page === '...' ? (
              <span key={`ellipsis-${idx}`} className="px-2 text-(--nous-fg-3)">...</span>
            ) : (
              <button
                key={page}
                onClick={() => onPageChange(page as number)}
                aria-label={`Page ${page}`}
                aria-current={currentPage === page ? 'page' : undefined}
                className={cn(
                  "min-w-[32px] h-8 rounded-md font-mono text-xs font-bold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]",
                  currentPage === page
                    ? "bg-(--nous-sol) text-(--nous-bg-1) shadow-[0_0_10px_var(--nous-sol-glow)]"
                    : "text-(--nous-fg-3) hover:text-(--nous-fg-1) hover:bg-(--nous-bg-3)"
                )}
              >
                {page}
              </button>
            )
          ))}
        </div>

        <button
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage === totalPages}
          className="p-2 rounded-lg border border-(--nous-border-1) hover:bg-(--nous-bg-2) disabled:opacity-30 disabled:hover:bg-transparent transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]"
          title="Next Page"
          aria-label="Next Page"
        >
          <ChevronRight className="w-4 h-4 text-(--nous-fg-1)" />
        </button>

        <button
          onClick={() => onPageChange(totalPages)}
          disabled={currentPage === totalPages}
          className="p-2 rounded-lg border border-(--nous-border-1) hover:bg-(--nous-bg-2) disabled:opacity-30 disabled:hover:bg-transparent transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]"
          title="Last Page"
          aria-label="Last Page"
        >
          <ChevronsRight className="w-4 h-4 text-(--nous-fg-1)" />
        </button>
      </nav>
    </div>
  );
}
