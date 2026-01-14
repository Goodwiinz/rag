import { Search, Filter, X, ChevronDown, CheckCircle } from 'lucide-react';
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
      {/* Search and Filter Row */}
      <div className="flex flex-col md:flex-row gap-4 bg-[var(--terminal-surface)] p-1 rounded-xl border border-[var(--terminal-border)]">
        <div className="flex-1 relative group">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--terminal-text-dim)] group-focus-within:text-[var(--phosphor-green)] transition-colors" />
          <Input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search documents by name, content, or id..."
            className="w-full pl-10 pr-4 py-2 border-none bg-transparent font-mono text-sm text-[var(--terminal-text)] focus-visible:ring-0 placeholder:text-[var(--terminal-text-muted)] h-auto"
          />
          {searchQuery && (
            <Button
              variant="ghost"
              size="icon"
              onClick={() => onSearchChange('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 h-6 w-6 text-[var(--terminal-text-dim)] hover:text-[var(--terminal-text)]"
            >
              <X className="w-3 h-3" />
            </Button>
          )}
        </div>

        <div className="w-[1px] bg-[var(--terminal-border)] my-1 hidden md:block" />

        <DropdownMenu open={showFilters} onOpenChange={setShowFilters}>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              className="w-full md:w-auto justify-between gap-3 px-4 font-mono text-xs text-[var(--terminal-text-dim)] hover:bg-[var(--terminal-elevated)] hover:text-[var(--terminal-text)]"
            >
              <div className="flex items-center gap-2">
                <Filter className="w-3.5 h-3.5" />
                <span>{statusFilter === 'all' ? 'ALL STATUS' : statusFilter.toUpperCase()}</span>
              </div>
              <ChevronDown className={cn("w-3.5 h-3.5 transition-transform", showFilters && "rotate-180")} />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48 bg-[var(--terminal-surface)] border-[var(--terminal-border)]">
            {statuses.map((status) => (
              <DropdownMenuItem
                key={status}
                onClick={() => {
                  onStatusChange(status);
                  setShowFilters(false);
                }}
                className={cn(
                  "font-mono text-xs cursor-pointer flex items-center justify-between",
                  statusFilter === status 
                    ? "text-[var(--phosphor-green)] focus:text-[var(--phosphor-green)] bg-[var(--phosphor-green)]/10" 
                    : "text-[var(--terminal-text-dim)] focus:text-[var(--terminal-text)]"
                )}
              >
                {status.toUpperCase()}
                {statusFilter === status && <CheckCircle className="w-3 h-3" />}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Selection Bar */}
      {selectedCount > 0 && (
        <div className="flex items-center justify-between p-2 px-4 rounded-lg bg-[var(--phosphor-green)]/10 border border-[var(--phosphor-green)]/20 animate-in slide-in-from-top-2 fade-in duration-200">
          <div className="flex items-center gap-3">
            <Badge variant="outline" className="border-[var(--phosphor-green)] text-[var(--phosphor-green)] font-mono">
              {selectedCount} Selected
            </Badge>
            <Button
              variant="link"
              size="sm"
              onClick={onClearSelection}
              className="text-[var(--terminal-text-dim)] hover:text-[var(--terminal-text)] font-mono text-xs h-auto p-0"
            >
              Clear Selection
            </Button>
          </div>
          <Button
            variant="destructive"
            size="sm"
            onClick={onBulkDelete}
            disabled={isBulkDeleting}
            className="h-8 font-mono text-xs"
          >
            {isBulkDeleting ? 'Deleting...' : 'Delete Selected'}
          </Button>
        </div>
      )}
    </div>
  );
}
