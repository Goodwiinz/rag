import React, { memo, useMemo, useCallback, useState, useRef } from 'react';
import { useVirtualScroll, useDebounce, useThrottle } from '@/utils/performance';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ChevronUpIcon, ChevronDownIcon } from 'lucide-react';

interface Column<T> {
  key: keyof T;
  title: string;
  sortable?: boolean;
  width?: string;
  render?: (value: any, row: T) => React.ReactNode;
}

interface OptimizedDataTableProps<T> {
  data: T[];
  columns: Column<T>[];
  itemHeight?: number;
  maxHeight?: number;
  searchable?: boolean;
  sortable?: boolean;
  onRowClick?: (row: T) => void;
  className?: string;
}

const ROW_HEIGHT = 48;
const DEFAULT_MAX_HEIGHT = 400;

function OptimizedDataTableComponent<T>({
  data,
  columns,
  itemHeight = ROW_HEIGHT,
  maxHeight = DEFAULT_MAX_HEIGHT,
  searchable = true,
  sortable = true,
  onRowClick,
  className = '',
}: OptimizedDataTableProps<T>) {
  const [sortConfig, setSortConfig] = useState<{
    key: keyof T;
    direction: 'asc' | 'desc';
  } | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedRow, setSelectedRow] = useState<string | null>(null);

  // Debounce search term
  const debouncedSearchTerm = useDebounce(searchTerm, 300);

  // Memoize filtered and sorted data
  const processedData = useMemo(() => {
    let filtered = data;

    // Filter data based on search term
    if (debouncedSearchTerm) {
      filtered = data.filter((row) =>
        columns.some((column) => {
          const value = row[column.key];
          return value?.toString().toLowerCase().includes(debouncedSearchTerm.toLowerCase());
        })
      );
    }

    // Sort data if sort config is set
    if (sortConfig) {
      filtered = [...filtered].sort((a, b) => {
        const aValue = a[sortConfig.key];
        const bValue = b[sortConfig.key];

        if (aValue === null || aValue === undefined) return 1;
        if (bValue === null || bValue === undefined) return -1;

        if (aValue < bValue) return sortConfig.direction === 'asc' ? -1 : 1;
        if (aValue > bValue) return sortConfig.direction === 'asc' ? 1 : -1;
        return 0;
      });
    }

    return filtered;
  }, [data, columns, debouncedSearchTerm, sortConfig]);

  // Virtual scrolling
  const {
    containerRef,
    visibleItems,
    offsetY,
    totalHeight,
    handleScroll,
  } = useVirtualScroll(processedData, itemHeight, maxHeight);

  // Throttled scroll handler
  const throttledScroll = useThrottle(handleScroll, 16);

  // Sort handler
  const handleSort = useCallback((key: keyof T) => {
    setSortConfig((current) => {
      if (!current || current.key !== key) {
        return { key, direction: 'asc' };
      }
      if (current.direction === 'asc') {
        return { key, direction: 'desc' };
      }
      return null;
    });
  }, []);

  // Row click handler
  const handleRowClick = useCallback((row: T, index: number) => {
    const rowIndex = data.indexOf(row);
    setSelectedRow(rowIndex.toString());
    onRowClick?.(row);
  }, [data, onRowClick]);

  // Memoize render functions
  const renderCell = useCallback((column: Column<T>, value: any, row: T) => {
    if (column.render) {
      return column.render(value, row);
    }
    return value?.toString() || '';
  }, []);

  const renderRow = useCallback((row: T, index: number, isVisible: boolean) => {
    const rowIndex = processedData.indexOf(row);
    const isSelected = selectedRow === rowIndex.toString();

    return (
      <div
        key={`row-${rowIndex}`}
        className={`flex items-center border-b border-gray-200 cursor-pointer hover:bg-gray-50 transition-colors ${
          isSelected ? 'bg-blue-50' : ''
        }`}
        style={{
          height: `${itemHeight}px`,
          position: 'absolute',
          top: `${index * itemHeight}px`,
          width: '100%',
        }}
        onClick={() => handleRowClick(row, rowIndex)}
        role="row"
        aria-selected={isSelected}
        tabIndex={isSelected ? 0 : -1}
      >
        {columns.map((column, columnIndex) => (
          <div
            key={`cell-${columnIndex}`}
            className="px-4 py-2 text-sm truncate"
            style={{
              width: column.width || 'auto',
              flex: column.width ? 'none' : 1,
            }}
            role="cell"
          >
            {renderCell(column, row[column.key], row)}
          </div>
        ))}
      </div>
    );
  }, [columns, itemHeight, selectedRow, handleRowClick, renderCell]);

  // Memoize visible rows
  const visibleRows = useMemo(() => {
    return visibleItems.map((item, index) =>
      renderRow(item, index, true)
    );
  }, [visibleItems, renderRow]);

  return (
    <div className={`optimized-data-table ${className}`}>
      {/* Search and controls */}
      {searchable && (
        <div className="p-4 border-b border-gray-200">
          <Input
            type="text"
            placeholder="Search..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="max-w-sm"
            aria-label="Search table data"
          />
          {processedData.length !== data.length && (
            <p className="mt-2 text-sm text-gray-500">
              Showing {processedData.length} of {data.length} results
            </p>
          )}
        </div>
      )}

      {/* Table header */}
      <div className="flex items-center bg-gray-50 border-b border-gray-200 font-medium text-gray-700">
        {columns.map((column, index) => (
          <div
            key={`header-${index}`}
            className="px-4 py-2 text-sm flex items-center"
            style={{
              width: column.width || 'auto',
              flex: column.width ? 'none' : 1,
            }}
            role="columnheader"
          >
            <span>{column.title}</span>
            {sortable && column.sortable && (
              <button
                onClick={() => handleSort(column.key)}
                className="ml-2 p-1 hover:bg-gray-200 rounded"
                aria-label={`Sort by ${column.title}`}
                aria-sort={
                  sortConfig?.key === column.key
                    ? sortConfig.direction === 'asc'
                      ? 'ascending'
                      : 'descending'
                    : 'none'
                }
              >
                {sortConfig?.key === column.key ? (
                  sortConfig.direction === 'asc' ? (
                    <ChevronUpIcon className="h-4 w-4" />
                  ) : (
                    <ChevronDownIcon className="h-4 w-4" />
                  )
                ) : (
                  <div className="h-4 w-4 opacity-50">
                    <ChevronUpIcon className="h-2 w-2" />
                    <ChevronDownIcon className="h-2 w-2 -mt-1" />
                  </div>
                )}
              </button>
            )}
          </div>
        ))}
      </div>

      {/* Virtual scrolling container */}
      <div
        ref={containerRef}
        className="relative overflow-auto"
        style={{ height: `${maxHeight}px` }}
        onScroll={throttledScroll}
        role="table"
        aria-label="Data table"
      >
        {/* Total height spacer */}
        <div style={{ height: `${totalHeight}px`, position: 'relative' }}>
          {/* Visible rows */}
          <div style={{ transform: `translateY(${offsetY}px)` }}>
            {visibleRows}
          </div>
        </div>
      </div>

      {/* Empty state */}
      {processedData.length === 0 && (
        <div className="flex items-center justify-center h-32 text-gray-500">
          {debouncedSearchTerm ? 'No results found' : 'No data available'}
        </div>
      )}
    </div>
  );
}

// Export memoized component
export const OptimizedDataTable = memo(OptimizedDataTableComponent) as typeof OptimizedDataTableComponent;

// Export types
export type { Column, OptimizedDataTableProps };