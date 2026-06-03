import { Search, Filter, X, ChevronDown, Check } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';
import { useState } from 'react';

interface DocumentFiltersProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  statusFilter: string;
  onStatusChange: (status: string) => void;
  selectedCount: number;
  onClearSelection: () => void;
  onBulkDelete: () => void;
  isBulkDeleting: boolean;
}

const STATUS_LABELS: Record<string, string> = {
  all: 'All statuses',
  indexed: 'Indexed',
  processing: 'Processing',
  queued: 'Queued',
  failed: 'Failed',
};

export function DocumentFilters({
  searchQuery,
  onSearchChange,
  statusFilter,
  onStatusChange,
  selectedCount,
  onClearSelection,
  onBulkDelete,
  isBulkDeleting,
}: DocumentFiltersProps) {
  const [showFilters, setShowFilters] = useState(false);
  const statuses = ['all', 'indexed', 'processing', 'queued', 'failed'];

  return (
    <div className="space-y-4">
      {/* Search and filter row */}
      <div className="flex flex-col md:flex-row gap-3 md:items-center rounded-xl border border-border bg-card p-2 shadow-sm">
        <div className="flex-1 relative group">
          <Search
            aria-hidden="true"
            className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground group-focus-within:text-primary transition-colors"
          />
          <Input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search by name, content, or id"
            aria-label="Search documents"
            className="w-full pl-10 pr-10 border-none bg-transparent text-sm text-foreground shadow-none focus-visible:ring-0 placeholder:text-muted-foreground h-9"
          />
          {searchQuery && (
            <Button
              variant="ghost"
              size="icon"
              onClick={() => onSearchChange('')}
              aria-label="Clear search"
              className="absolute right-1.5 top-1/2 -translate-y-1/2 h-7 w-7 text-muted-foreground hover:text-foreground"
            >
              <X aria-hidden="true" className="w-3.5 h-3.5" />
            </Button>
          )}
        </div>

        <div className="hidden md:block w-px self-stretch bg-border my-1" />

        <DropdownMenu open={showFilters} onOpenChange={setShowFilters}>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              className="w-full md:w-auto justify-between gap-3 text-sm text-muted-foreground hover:text-foreground"
            >
              <span className="flex items-center gap-2">
                <Filter aria-hidden="true" className="w-4 h-4" />
                <span>{STATUS_LABELS[statusFilter] ?? statusFilter}</span>
              </span>
              <ChevronDown
                aria-hidden="true"
                className={cn(
                  'w-4 h-4 transition-transform duration-200',
                  showFilters && 'rotate-180'
                )}
              />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            {statuses.map((status) => (
              <DropdownMenuItem
                key={status}
                onClick={() => {
                  onStatusChange(status);
                  setShowFilters(false);
                }}
                className={cn(
                  'text-sm cursor-pointer flex items-center justify-between',
                  statusFilter === status && 'text-primary'
                )}
              >
                {STATUS_LABELS[status] ?? status}
                {statusFilter === status && (
                  <Check aria-hidden="true" className="w-4 h-4" />
                )}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Selection bar */}
      {selectedCount > 0 && (
        <div className="flex items-center justify-between gap-3 px-4 py-2 rounded-xl border border-primary/30 bg-primary/5">
          <div className="flex items-center gap-3">
            <Badge
              variant="outline"
              className="border-primary/40 text-primary tabular-nums"
            >
              {selectedCount} selected
            </Badge>
            <Button
              variant="link"
              size="sm"
              onClick={onClearSelection}
              className="text-muted-foreground hover:text-foreground text-sm h-auto p-0"
            >
              Clear selection
            </Button>
          </div>
          <Button
            variant="destructive"
            size="sm"
            onClick={onBulkDelete}
            disabled={isBulkDeleting}
            className="h-8"
          >
            {isBulkDeleting ? 'Deleting…' : 'Delete selected'}
          </Button>
        </div>
      )}
    </div>
  );
}
