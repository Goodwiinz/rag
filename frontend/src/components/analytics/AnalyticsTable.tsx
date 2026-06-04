'use client';

import { useState, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Search,
  Filter,
  Download,
  ChevronDown,
  ChevronUp,
  ChevronLeft,
  ChevronRight,
  MoreHorizontal,
  Eye,
  Edit,
  Trash,
  Copy,
  ExternalLink,
  Calendar,
  FileText,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface Column<T> {
  key: keyof T;
  title: string;
  sortable?: boolean;
  filterable?: boolean;
  width?: string;
  render?: (value: any, row: T, index: number) => React.ReactNode;
  className?: string;
}

interface AnalyticsTableProps<T> {
  title: string;
  description?: string;
  data: T[];
  columns: Column<T>[];
  loading?: boolean;
  pagination?: {
    page: number;
    pageSize: number;
    total: number;
    onPageChange: (page: number) => void;
    onPageSizeChange: (pageSize: number) => void;
  };
  search?: {
    placeholder?: string;
    onSearch: (query: string) => void;
  };
  filters?: {
    options: Array<{ value: string; label: string; count?: number }>;
    onFilter: (value: string) => void;
  };
  actions?: {
    onExport?: () => void;
    onRefresh?: () => void;
  };
  rowActions?: {
    label: string;
    icon: any;
    onClick: (row: T, index: number) => void;
    variant?: 'default' | 'destructive';
  }[];
  emptyState?: {
    icon?: any;
    title: string;
    description: string;
    action?: {
      label: string;
      onClick: () => void;
    };
  };
  className?: string;
}

export function AnalyticsTable<T extends Record<string, any>>({
  title,
  description,
  data,
  columns,
  loading = false,
  pagination,
  search,
  filters,
  actions,
  rowActions,
  emptyState,
  className,
}: AnalyticsTableProps<T>) {
  const [sortColumn, setSortColumn] = useState<keyof T | null>(null);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedFilter, setSelectedFilter] = useState<string>('all');

  // Filter and sort data
  const processedData = useMemo(() => {
    let filtered = [...data];

    // Apply search filter
    if (searchQuery) {
      filtered = filtered.filter((row) =>
        Object.values(row).some((value) =>
          String(value).toLowerCase().includes(searchQuery.toLowerCase())
        )
      );
    }

    // Apply column filter
    if (selectedFilter !== 'all') {
      filtered = filtered.filter((row) =>
        Object.values(row).some((value) => String(value) === selectedFilter)
      );
    }

    // Apply sorting
    if (sortColumn) {
      filtered.sort((a, b) => {
        const aValue = a[sortColumn];
        const bValue = b[sortColumn];

        if (aValue === null || aValue === undefined) return 1;
        if (bValue === null || bValue === undefined) return -1;

        let comparison = 0;
        if (typeof aValue === 'number' && typeof bValue === 'number') {
          comparison = aValue - bValue;
        } else {
          comparison = String(aValue).localeCompare(String(bValue));
        }

        return sortDirection === 'asc' ? comparison : -comparison;
      });
    }

    return filtered;
  }, [data, searchQuery, selectedFilter, sortColumn, sortDirection]);

  // Handle column sort
  const handleSort = (column: keyof T) => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(column);
      setSortDirection('desc');
    }
  };

  // Get paginated data
  const paginatedData = useMemo(() => {
    if (!pagination) return processedData;

    const startIndex = (pagination.page - 1) * pagination.pageSize;
    const endIndex = startIndex + pagination.pageSize;
    return processedData.slice(startIndex, endIndex);
  }, [processedData, pagination]);

  // Handle search with debounce
  const handleSearch = (value: string) => {
    setSearchQuery(value);
    search?.onSearch(value);
  };

  return (
    <Card className={cn('overflow-hidden', className)}>
      {/* Header */}
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <CardTitle className="text-lg font-semibold">{title}</CardTitle>
            {description && (
              <p className="text-sm text-muted-foreground">{description}</p>
            )}
          </div>

          {actions && (
            <div className="flex items-center gap-2">
              {actions.onRefresh && (
                <Button variant="outline" size="sm" onClick={actions.onRefresh}>
                  <Download className="h-4 w-4 mr-2" />
                  Refresh
                </Button>
              )}
              {actions.onExport && (
                <Button variant="outline" size="sm" onClick={actions.onExport}>
                  <Download className="h-4 w-4 mr-2" />
                  Export
                </Button>
              )}
            </div>
          )}
        </div>

        {/* Filters and Search */}
        <div className="flex flex-col sm:flex-row gap-4 mt-4">
          {/* Search */}
          {search && (
            <div className="relative flex-1 max-w-sm">
              <Search
                aria-hidden="true"
                className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
              />
              <Input
                placeholder={search.placeholder || 'Search...'}
                aria-label="Search"
                value={searchQuery}
                onChange={(e) => handleSearch(e.target.value)}
                className="pl-10"
              />
            </div>
          )}

          {/* Column Filter */}
          {filters && (
            <Select
              value={selectedFilter}
              onValueChange={(value) => {
                setSelectedFilter(value);
                filters.onFilter(value);
              }}
            >
              <SelectTrigger className="w-[180px]">
                <Filter aria-hidden="true" className="h-4 w-4 mr-2" />
                <SelectValue placeholder="Filter" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                {filters.options.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                    {option.count !== undefined && (
                      <Badge variant="secondary" className="ml-2">
                        {option.count}
                      </Badge>
                    )}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}

          <div className="flex-1" />
        </div>
      </CardHeader>

      {/* Table */}
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                {columns.map((column) => (
                  <TableHead
                    key={String(column.key)}
                    style={{ width: column.width }}
                    className={cn(
                      'whitespace-nowrap',
                      column.sortable && 'cursor-pointer hover:bg-muted/50',
                      column.className
                    )}
                    onClick={() => column.sortable && handleSort(column.key)}
                  >
                    <div className="flex items-center gap-2">
                      {column.title}
                      {column.sortable &&
                        sortColumn === column.key &&
                        (sortDirection === 'asc' ? (
                          <ChevronUp className="h-4 w-4" />
                        ) : (
                          <ChevronDown className="h-4 w-4" />
                        ))}
                    </div>
                  </TableHead>
                ))}
                {rowActions && rowActions.length > 0 && (
                  <TableHead className="w-[50px]">
                    <span className="sr-only">Actions</span>
                  </TableHead>
                )}
              </TableRow>
            </TableHeader>

            <TableBody>
              {loading ? (
                // Loading skeleton
                Array.from({ length: 5 }).map((_, index) => (
                  <TableRow key={index}>
                    {columns.map((column) => (
                      <TableCell key={String(column.key)}>
                        <div className="h-4 w-full bg-muted rounded animate-pulse" />
                      </TableCell>
                    ))}
                    {rowActions && (
                      <TableCell>
                        <div className="h-8 w-8 bg-muted rounded animate-pulse" />
                      </TableCell>
                    )}
                  </TableRow>
                ))
              ) : paginatedData.length === 0 ? (
                // Empty state
                <TableRow>
                  <TableCell
                    colSpan={columns.length + (rowActions ? 1 : 0)}
                    className="h-24 text-center"
                  >
                    <div className="flex flex-col items-center gap-2">
                      {emptyState?.icon && (
                        <emptyState.icon className="h-12 w-12 text-muted-foreground" />
                      )}
                      <p className="font-medium">
                        {emptyState?.title || 'No data found'}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {emptyState?.description ||
                          'Try adjusting your filters or search query'}
                      </p>
                      {emptyState?.action && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={emptyState.action.onClick}
                        >
                          {emptyState.action.label}
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ) : (
                // Data rows
                paginatedData.map((row, index) => (
                  <TableRow key={index} className="hover:bg-muted/50">
                    {columns.map((column) => (
                      <TableCell
                        key={String(column.key)}
                        className={cn(column.className)}
                      >
                        {column.render
                          ? column.render(row[column.key], row, index)
                          : String(row[column.key] || '-')}
                      </TableCell>
                    ))}
                    {rowActions && rowActions.length > 0 && (
                      <TableCell>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-8 w-8 p-0"
                              aria-label="More actions"
                            >
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            {rowActions.map((action, actionIndex) => (
                              <DropdownMenuItem
                                key={actionIndex}
                                onClick={() => action.onClick(row, index)}
                                className={cn(
                                  action.variant === 'destructive' &&
                                    'text-[var(--nous-mars)]'
                                )}
                              >
                                <action.icon className="h-4 w-4 mr-2" />
                                {action.label}
                              </DropdownMenuItem>
                            ))}
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    )}
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>

        {/* Pagination */}
        {pagination && (
          <div className="flex items-center justify-between p-4 border-t">
            <div className="text-sm text-muted-foreground">
              Showing {(pagination.page - 1) * pagination.pageSize + 1} to{' '}
              {Math.min(
                pagination.page * pagination.pageSize,
                pagination.total
              )}{' '}
              of {pagination.total} results
            </div>

            <div className="flex items-center gap-4">
              {/* Page Size Selector */}
              <Select
                value={String(pagination.pageSize)}
                onValueChange={(value) =>
                  pagination.onPageSizeChange(Number(value))
                }
              >
                <SelectTrigger className="h-8 w-[70px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="10">10</SelectItem>
                  <SelectItem value="25">25</SelectItem>
                  <SelectItem value="50">50</SelectItem>
                  <SelectItem value="100">100</SelectItem>
                </SelectContent>
              </Select>

              {/* Page Navigation */}
              <div className="flex items-center gap-1">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => pagination.onPageChange(pagination.page - 1)}
                  disabled={pagination.page === 1}
                  className="h-8 w-8 p-0"
                  aria-label="Previous page"
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>

                <span className="text-sm px-2">
                  Page {pagination.page} of{' '}
                  {Math.ceil(pagination.total / pagination.pageSize)}
                </span>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => pagination.onPageChange(pagination.page + 1)}
                  disabled={
                    pagination.page ===
                    Math.ceil(pagination.total / pagination.pageSize)
                  }
                  className="h-8 w-8 p-0"
                  aria-label="Next page"
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// Preset table configurations
export const createDocumentAnalyticsTable = () => {
  const columns = [
    {
      key: 'filename',
      title: 'Document',
      sortable: true,
      render: (value: string, row: any) => (
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded bg-muted text-primary">
            <FileText aria-hidden="true" className="h-4 w-4" />
          </div>
          <span className="font-medium">{value}</span>
        </div>
      ),
    },
    {
      key: 'type',
      title: 'Type',
      sortable: true,
      render: (value: string) => (
        <Badge variant="secondary">{value.toUpperCase()}</Badge>
      ),
    },
    {
      key: 'size',
      title: 'Size',
      sortable: true,
      render: (value: number) => formatFileSize(value),
    },
    {
      key: 'uploadedAt',
      title: 'Uploaded',
      sortable: true,
      render: (value: string) => (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Calendar aria-hidden="true" className="h-3 w-3" />
          {formatDate(value)}
        </div>
      ),
    },
    {
      key: 'status',
      title: 'Status',
      sortable: true,
      render: (value: string) => (
        <Badge
          variant={
            value === 'completed'
              ? 'default'
              : value === 'processing'
                ? 'secondary'
                : value === 'failed'
                  ? 'destructive'
                  : 'outline'
          }
        >
          {value}
        </Badge>
      ),
    },
  ];

  return { columns };
};

export const createSearchAnalyticsTable = () => {
  const columns = [
    {
      key: 'query',
      title: 'Query',
      sortable: true,
      render: (value: string) => (
        <span className="font-medium truncate max-w-[200px] block">
          {value}
        </span>
      ),
    },
    {
      key: 'type',
      title: 'Type',
      sortable: true,
      render: (value: string) => <Badge variant="outline">{value}</Badge>,
    },
    {
      key: 'results',
      title: 'Results',
      sortable: true,
    },
    {
      key: 'clickRate',
      title: 'Click rate',
      sortable: true,
      render: (value: number) => `${(value * 100).toFixed(1)}%`,
    },
    {
      key: 'lastSearched',
      title: 'Last searched',
      sortable: true,
      render: (value: string) => formatDate(value),
    },
  ];

  return { columns };
};

// Utility functions
function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffTime = Math.abs(now.getTime() - date.getTime());
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays} days ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
  if (diffDays < 365) return `${Math.floor(diffDays / 30)} months ago`;
  return `${Math.floor(diffDays / 365)} years ago`;
}

export default AnalyticsTable;
